"""Versioned construction recipes and sequential, retry-safe batches."""

import copy
import inspect
import json
import tempfile
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from skill.library import record_event
from spatial.build import Machine


class Operation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    op: str
    params: dict


BUILD_OPERATIONS = {"start", "attach_block_to", "connect_blocks", "twist_block",
                    "shift_block", "add_machine", "shift_machine", "rotate_machine"}
REFERENCE_FIELDS = {"base_block", "block_a", "block_b", "block_id"}


class BatchExecutor:
    def __init__(self, machine, tools, path):
        self.machine, self.path = machine, Path(path)
        self.tools = {tool.__name__: tool for tool in tools if tool.__name__ in BUILD_OPERATIONS}
        self.completed = {}
        self.ids = {}
        self.failure = None

    def state(self):
        return {"completed": list(self.completed), "block_ids": self.ids,
                "num_blocks": self.machine.num_blocks,
                "revision": self.machine.geometry_revision, "failure": self.failure}

    def run(self, operations):
        started = time.monotonic()
        if not 1 <= len(operations) <= 5:
            return {"ok": False, "error": "Batch size must be 1..5"}
        results = []
        for item in operations:
            item = Operation.model_validate(item)
            original = item.model_dump()
            if item.id in self.completed:
                if self.completed[item.id] != original:
                    return {"ok": False, "error": "Completed operation ID reused with different arguments",
                            "operation_id": item.id, "results": results}
                results.append({"id": item.id, "status": "already_completed"})
                continue
            try:
                if item.op not in self.tools:
                    raise ValueError("Operation not allowed: " + item.op)
                params = copy.deepcopy(item.params)
                for field in REFERENCE_FIELDS & params.keys():
                    value = params[field]
                    if isinstance(value, str) and value.startswith("$"):
                        params[field] = self.ids[value[1:]]
                inspect.signature(self.tools[item.op]).bind(**params)
            except (ValueError, TypeError, KeyError) as error:
                self.failure = {"id": item.id, "code": "invalid_arguments", "detail": str(error)}
                break
            previous_ids = set(self.machine.blocks)
            history_size = len(self.machine.operation_history)
            full_size = len(self.machine.operation_history_full)
            try:
                response = self.tools[item.op](**params)
            except Exception as error:
                # A tool may have mutated before failing. Never claim transactional rollback.
                self.failure = {"id": item.id, "code": "tool_exception", "detail": type(error).__name__,
                                "requires_manual_reconciliation": True}
                break
            events = self.machine.operation_history_full[full_size:]
            if (any(event["op"] == "failed" for event in events)
                    or len(self.machine.operation_history) <= history_size):
                self.failure = {
                    "id": item.id, "operation": original, "code": (
                        (self.machine.geometry_failure or {}).get("code", "operation_failed")),
                    "detail": str(response).split("Existing Blocks:")[0][:2000],
                }
                if item.op == "connect_blocks":
                    self.failure["endpoints"] = self.machine.check_connection(
                        params["block_a"], params["face_a"], params["block_b"], params["face_b"])
                target_ids = {str(params[field]) for field in REFERENCE_FIELDS & params.keys()}
                snapshot = self.machine.geometry_snapshot()
                self.failure["actual_blocks"] = {
                    key: value for key, value in snapshot["blocks"].items() if key in target_ids}
                break
            added = sorted(set(self.machine.blocks) - previous_ids)
            if len(added) == 1:
                self.ids[item.id] = added[0]
            self.completed[item.id] = original
            self.failure = None
            results.append({"id": item.id, "status": "completed", "added_block_ids": added})
        result = {"ok": self.failure is None, "results": results, **self.state()}
        record_event(self.path, event="batch_result", operations=[
            Operation.model_validate(item).model_dump() for item in operations], result=result,
                     elapsed_seconds=time.monotonic() - started)
        return result

    async def execute_batch(self, operations: list[Operation]) -> dict:
        """Execute 1..5 sequential operations; $operation_id references its created block.

        Reuse identical IDs on retry. Stops on first failure; successful prefix is retained.
        """
        return self.run(operations)


class Blueprint:
    def __init__(self, path, task, tools, *, executor=None):
        self.path, self.task, self.tools = Path(path), task, tools
        self.version = 0
        self.operations = []
        self.interfaces = ""
        self.executor = executor
        self.approved_version = None
        self.validation = None
        self.expected_blocks = None

    def document(self):
        return {"version": self.version, "interfaces": self.interfaces,
                "operations": self.operations}

    def facts(self):
        return json.dumps({"task": self.task, "blueprint": self.document(),
                           "geometry_conventions": (
                               "Face arguments are capital-letter LOCAL labels, not compass names. "
                               "Read actual_blocks in preflight failures for available labels, face "
                               "centers and normals. Do not guess strings such as south or front."),
                           "operation_signatures": {
                               name: str(inspect.signature(tool)) for name, tool in self.tools.items()},
                           "approved_version": self.approved_version,
                           "progress": self.executor.state() if self.executor else None},
                          ensure_ascii=False)

    def save(self):
        record_event(self.path, event="blueprint_version", blueprint=self.document())

    def validate_operations(self, operations):
        parsed = [Operation.model_validate(op).model_dump() for op in operations]
        if not parsed:
            raise ValueError("Blueprint must not be empty")
        seen = set()
        for op in parsed:
            if op["id"] in seen:
                raise ValueError("Duplicate operation ID: " + op["id"])
            if op["op"] not in self.tools:
                raise ValueError("Unavailable operation: " + op["op"])
            inspect.signature(self.tools[op["op"]]).bind(**op["params"])
            for field in REFERENCE_FIELDS & op["params"].keys():
                value = op["params"][field]
                if isinstance(value, str) and value.startswith("$") and value[1:] not in seen:
                    raise ValueError("Forward or missing reference: " + value)
            seen.add(op["id"])
        return parsed

    async def submit_blueprint(self, operations: list[Operation], interfaces: str) -> dict:
        """Submit the first complete recipe with stable IDs and assembly interface constraints."""
        if self.version:
            return {"ok": False, "error": "Use patch_blueprint after first submission"}
        try:
            self.operations = self.validate_operations(operations)
        except (ValueError, TypeError) as error:
            return {"ok": False, "error": str(error)}
        self.interfaces, self.version = interfaces, 1
        self.save()
        return {"ok": True, "version": self.version, "operations": len(self.operations)}

    async def patch_blueprint(self, base_version: int, replacements: list[Operation],
                              delete_ids: list[str], append: list[Operation], reason: str) -> dict:
        """Patch only named operations at base_version; completed operations and interfaces are locked."""
        if base_version != self.version or not self.version:
            return {"ok": False, "error": "Stale or missing blueprint version"}
        try:
            replace = {op.id: op.model_dump() for op in replacements}
            if len(replace) != len(replacements) or len(set(delete_ids)) != len(delete_ids):
                raise ValueError("Duplicate patch ID")
            existing = {op["id"] for op in self.operations}
            touched = set(replace) | set(delete_ids)
            if not touched <= existing or set(replace) & set(delete_ids):
                raise ValueError("Unknown or conflicting patch ID")
            completed = self.executor.completed if self.executor else {}
            if touched & completed.keys():
                raise ValueError("Completed operations are locked")
            candidate = [replace.get(op["id"], op) for op in self.operations
                         if op["id"] not in delete_ids] + [op.model_dump() for op in append]
            candidate = self.validate_operations(candidate)
            # Preserve the exact executed prefix, not just the set of completed IDs.
            if completed and candidate[:len(completed)] != list(completed.values()):
                raise ValueError("Patch must preserve the executed prefix")
        except (ValueError, TypeError) as error:
            return {"ok": False, "error": str(error)}
        self.operations = candidate
        self.version += 1
        self.approved_version = self.validation = None
        self.save()
        record_event(self.path, event="blueprint_patch", reason=reason, touched=sorted(touched))
        return {"ok": True, "version": self.version}

    async def inspect_blueprint(self, offset: int = 0, limit: int = 5) -> dict:
        """Read canonical operations in pages; full blueprint is stored separately."""
        if offset < 0 or not 1 <= limit <= 20:
            return {"ok": False, "error": "offset >= 0 and limit 1..20 required"}
        return {"version": self.version, "interfaces": self.interfaces,
                "total": len(self.operations), "operations": self.operations[offset:offset + limit]}

    async def validate_blueprint(self) -> dict:
        """Replay the complete recipe in a temporary machine using the actual geometry tools."""
        started = time.monotonic()
        self.approved_version = None
        if not self.version:
            return {"ok": False, "error": "No blueprint submitted"}
        with tempfile.TemporaryDirectory(prefix="buildarena-preflight-") as directory:
            machine = Machine(name="preflight", db_path=str(Path(directory) / "task.db"),
                              save_dir=directory)
            tools = [machine.operations[name] for name in self.tools if name in machine.operations]
            executor = BatchExecutor(machine, tools, Path(directory) / "replay.jsonl")
            result = {"ok": True}
            completed_count = len(self.executor.completed) if self.executor else 0
            for index, operation in enumerate(self.operations, 1):
                result = executor.run([operation])
                if not result["ok"]:
                    break
                if self.executor and index == completed_count:
                    if (machine.geometry_snapshot()["blocks"]
                            != self.executor.machine.geometry_snapshot()["blocks"]):
                        result = {"ok": False, "failure": {
                            "code": "executed_prefix_state_drift",
                            "requires_manual_reconciliation": True}}
                        break
            if result["ok"]:
                self.expected_blocks = machine.geometry_snapshot()["blocks"]
            self.validation = {"version": self.version, **result}
            record_event(self.path, event="blueprint_preflight", result=self.validation,
                         elapsed_seconds=time.monotonic() - started)
            return self.validation

    async def approve_blueprint(self, version: int, review: str) -> dict:
        """Approve this exact version after geometry validation and functional/interface review."""
        if (version != self.version or not self.validation or not self.validation["ok"]
                or self.validation["version"] != version or not review.strip()):
            return {"ok": False, "error": "Current version must pass preflight and receive a review"}
        self.approved_version = version
        record_event(self.path, event="blueprint_approved", version=version, review=review)
        return {"ok": True, "version": version}

    async def execute_next_batch(self, operation_ids: list[str], version: int) -> dict:
        """Execute the next 1..5 approved canonical operations in one call; retries are idempotent."""
        if version != self.approved_version or version != self.version or not self.executor:
            return {"ok": False, "error": "Blueprint version not approved"}
        if not 1 <= len(operation_ids) <= 5 or len(set(operation_ids)) != len(operation_ids):
            return {"ok": False, "error": "Use 1..5 unique IDs"}
        by_id = {op["id"]: op for op in self.operations}
        if not set(operation_ids) <= by_id.keys():
            return {"ok": False, "error": "Unknown operation IDs"}
        pending = [op["id"] for op in self.operations if op["id"] not in self.executor.completed]
        new = [key for key in operation_ids if key not in self.executor.completed]
        if new != pending[:len(new)]:
            return {"ok": False, "error": "Execute the next pending prefix in order"}
        if (self.executor.failure or {}).get("requires_manual_reconciliation"):
            return {"ok": False, "error": "Tool exception requires manual reconciliation"}
        return self.executor.run([by_id[key] for key in operation_ids])

    def complete(self):
        return bool(self.executor and self.approved_version == self.version
                    and self.operations
                    and all(self.executor.completed.get(op["id"]) == op for op in self.operations)
                    and self.executor.machine.geometry_snapshot()["blocks"] == self.expected_blocks
                    and not self.executor.failure and not self.executor.machine.in_collision()[0])
