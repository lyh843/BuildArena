import asyncio

from typing import List, Callable, Tuple, Dict
from collections import namedtuple

import os
import xml.etree.ElementTree as ET
import json
from pathlib import Path
import time
import uuid

from autogen_core import CancellationToken
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import TaskResult, Response
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import BaseGroupChat, RoundRobinGroupChat
from autogen_agentchat.messages import TextMessage, BaseChatMessage

from config import SavedMachines
from spatial.build import Machine, Assembly
from spatial.utils import xml_to_dict

from agents import model_clients
from scheduler.task_db import Task, get_config, add_task_objection, update_task_raise_objection
from skill.library import SkillSession, record_event

ProcessContext = namedtuple('ProcessContext', ['context', 'result', 'token_input', 'token_output', 'turn', 'objection'])

machine = Machine(name = "default")
AvailableBlocks = machine.blocks_storage()

def init_agents(agent_config: dict, **kwargs):
    agent = AssistantAgent(
        name=agent_config['name'], 
        model_client=model_clients[agent_config['model']], 
        system_message=agent_config['system_message'].replace("{available_blks}", AvailableBlocks),
        **kwargs,
    )
    return agent

def get_turn(messages: List[BaseChatMessage]):
    """
    Get the turn of the messages for round robin group chat.
    """
    turn = 0
    for i, msg in enumerate(messages):
        last_speaker = msg.source
        next_speaker = messages[i+1].source if i+1 < len(messages) else None
        if last_speaker != next_speaker:
            turn += 1
    return turn

def get_token_input(messages: List[BaseChatMessage]):
    return sum([c.models_usage.prompt_tokens for c in messages if c.models_usage is not None])

def get_token_output(messages: List[BaseChatMessage]):
    return sum([c.models_usage.completion_tokens for c in messages if c.models_usage is not None])

class Objection:
    geometry_instructions = """
Construction objections require verified tool evidence, not inferred geometry.
You may call inspect_geometry and get_block_details yourself: these are read-only
tools, not building operations. Face letters are local labels, not global directions.
Before any build/refine objection, ask the builder to attempt the specific
blueprint operation and correct tool arguments or placement mistakes. Then call
inspect_geometry with relevant block IDs (an empty list inspects all blocks).
Only a real, current engine failure can produce an evidence_id. Include that ID
in raise_objection_build/raise_objection_refine. Any subsequent edit invalidates it.
Match your objection to that exact failed operation and explain attempted repairs.
A failed operation alone does not prove the entire blueprint impossible.
If evidence is missing, invalid or stale, continue investigating and building;
do not announce rejection or finish the conversation. Use the termination marker
only for a verified complete construction or an accepted objection.
"""

    def __init__(self, task: Task, machine: Machine | None = None):
        self.task_id = task.id
        self.parent_id = task.parent_id if task.parent_id else "root"
        self.machine_id = task.bind_machine if task.bind_machine else task.id
        self.stage = "machine" if task.stage in ["build", "refine", "assemble"] else task.stage
        self.working_dir = os.path.join(os.path.dirname(task.db_path), self.stage, self.machine_id)
        self.objection_file_path = os.path.join(self.working_dir, f"objection_{self.task_id}_to_{self.parent_id}.txt")
        self.db_path = task.db_path
        self.objection_raised = False
        self.machine = machine
        self._geometry_evidence = None
        self.geometry_audit_path = Path(self.working_dir) / f"geometry_checks_{task.id}.jsonl"

    async def inspect_geometry(self, block_ids: List[str]) -> dict:
        """Inspect live positions, local faces and collisions before objecting.

        Args:
            block_ids: Relevant existing block IDs; [] returns all blocks.

        Returns:
            Current state and an evidence_id only for a real, current tool failure.
            Invalid IDs/faces are correction requests, not geometry failure evidence.
        """
        self._geometry_evidence = None
        if self.machine is None:
            return {"evidence_id": None, "reason": "no_live_machine"}
        state = self.machine.geometry_snapshot()
        failure = self.machine.geometry_failure
        current_failure = failure and failure.get("state") == state
        selected = set(block_ids) if block_ids else set(state["blocks"])
        # Always show the actual failed operation's targets as well as requested IDs.
        if current_failure:
            params = failure["params"]
            selected.update(str(params[key]) for key in
                            ("base_block", "block_a", "block_b", "block_id") if key in params)
            if "machine_index" in params:
                selected.update(key for key in state["blocks"]
                                if key.startswith(params["machine_index"] + "_"))
            selected.update(key for pair in failure["collision_pairs"] for key in pair)
        collision, pairs = self.machine.in_collision()
        result = {
            "evidence_id": None, "revision": state["revision"],
            "collision_enabled": state["collision_enabled"],
            "blocks": {key: state["blocks"][key] for key in sorted(selected) if key in state["blocks"]},
            "missing_block_ids": sorted(selected - state["blocks"].keys()),
            "current_collision": bool(collision),
            "current_collision_pairs": sorted(sorted(pair) for pair in pairs),
            "failure": None,
            "reason": "no_current_verified_failure",
        }
        if current_failure and state == self.machine.geometry_snapshot():
            result["evidence_id"] = uuid.uuid4().hex
            result["failure"] = {key: value for key, value in failure.items() if key != "state"}
            result["reason"] = "verified_operation_failure"
            self._geometry_evidence = {
                **result, "task_id": self.task_id, "machine_name": self.machine.name,
                "state": state,
            }
        record_event(self.geometry_audit_path, event="geometry_inspection",
                     task_id=self.task_id, result=result)
        return result

    def update_task_objection(self, key_failure: str, objection: str, evidence_id: str = ""):
        evidence = self._geometry_evidence
        if self.stage == "machine":
            reason = None
            if self.objection_raised:
                reason = "objection_already_raised"
            elif not evidence_id or not evidence or evidence_id != evidence["evidence_id"]:
                reason = "missing_or_unknown_evidence"
            elif self.machine is None or evidence["state"] != self.machine.geometry_snapshot():
                reason = "stale_geometry_evidence"
            record_event(self.geometry_audit_path, event="objection_check",
                         task_id=self.task_id, accepted=reason is None, reason=reason,
                         evidence_id=evidence_id, key_failure=key_failure, objection=objection)
            if reason:
                # Never echo model text here: it can contain the team's stop marker.
                return json.dumps({
                    "accepted": False, "reason": reason,
                    "next_step": "Continue building. Correct tool arguments and ask the builder "
                                 "to attempt the specific operation, then call inspect_geometry.",
                })
        os.makedirs(self.working_dir, exist_ok=True)
        with open(self.objection_file_path, "w", encoding="utf-8") as f:
            f.write(f"From: {self.task_id}\nTo: {self.parent_id}\n")
            f.write(f"Key failure: {key_failure}\nObjection: {objection}")
            if self.stage == "machine":
                f.write("\nVerified operation evidence (not proof of global impossibility):\n")
                json.dump(evidence, f, ensure_ascii=False, indent=2)
        # Add one objection count to the parent task
        if self.parent_id:
            add_task_objection(task_id=self.parent_id, db_path=self.db_path)
        # Set the task to raise objection
        update_task_raise_objection(task_id=self.task_id, raise_objection=self.objection_file_path, db_path=self.db_path)
        self.objection_raised = True
        
        return "Objection raised, TERMINATE"
        
    def raise_objection_draft(self, key_failure: str, objection: str) -> str:
        """
        A tool to raise an objection to the structure design plan when it is believed to be incorrect or impossible to be completed during the current process.
        If the plan, instruction, design, decision, or critical information about the structure provided by the previous task is incorrect, constantly preventing the current process from fulfilling its purpose after many attempts, the objection should be raised.
        You only have one chance to raise the objection, so please be careful and precise, after you raise the objection, the current process will be shut down.
        Only raise the objection after you have tried many times to correct the blueprint, but it still does not pass the checklist.
        
        Args:
            key_failure (str): The key failure of the plan or drafter's mistake
            objection (str): The detailed objection to the plan  or drafter's continuous failure
            Explain what effort have you made to try to design the structure as instructed in the plan and helped the drafter to improve the blueprint, and why the current blueprint is impossible to be completed as expected.
            
        Returns:
            str: The command to shut down the current process.
        """
        return self.update_task_objection(key_failure, objection)
    
    def raise_objection_build(self, key_failure: str, objection: str, evidence_id: str = "") -> str:
        """
        A tool to raise an objection to the provided blueprint when it is believed to be incorrect or impossible to be built during the current process.
        If you and the builder have tried many times to build the structure illustrated as the blueprint, but it violates the physical constrains of the building process (block not available, blocks overlap, etc.), the objection should be raised.
        You only have one chance to raise the objection, so please be careful and precise, after you raise the objection, the current process will be shut down.
        DO NOT use this tool to correct the mistake of the builder, it is your responsibility to guide the builder to correct the mistake.
        
        Args:
            key_failure (str): The key failure of the blueprint
            objection (str): The detailed objection to the blueprint
            evidence_id (str): Current verified failure ID returned by inspect_geometry; mandatory for acceptance.
            Explain what effort have you made to try to build the structure as instructed in the blueprint, and why the current blueprint is impossible to be built as expected.
            
        Returns:
            str: The command to shut down the current process.
        """
        return self.update_task_objection(key_failure, objection, evidence_id)
    
    def raise_objection_refine(self, key_failure: str, objection: str, evidence_id: str = "") -> str:
        """
        A tool to raise an objection to the provided machine structure when it is believed to be incorrect or impossible to be corrected and refined during the current process.
        If you and the builder have tried many times to correct the structure illustrated as the blueprint, but it has structural issues that cannot be adjust (missing blocks, misplaced blocks, rotatable blocks with wrong orientation, etc.), the objection should be raised.
        You only have one chance to raise the objection, so please be careful and precise, after you raise the objection, the current process will be shut down.
        DO NOT use this tool to correct the mistake of the builder, it is your responsibility to guide the builder to correct the mistake.
        Only raise the objection after you have tried many times to correct the machine, but it still does not pass the checklist.
        
        Args:
            key_failure (str): The key failure of the machine
            objection (str): The detailed objection to the machine
            evidence_id (str): Current verified failure ID returned by inspect_geometry; mandatory for acceptance.
            Explain what effort have you made to try to correct the machine, and why the current machine is impossible to be corrected and refined as expected.
            
        Returns:
            str: The command to shut down the current process.
        """
        return self.update_task_objection(key_failure, objection, evidence_id)

class MultiAgents():
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        
    def prepare_team(self, participants: List[AssistantAgent], termination_string: str = "TERMINATE", max_turns: int = 50):
        """
        Prepare a team of agents.
        
        Args:
            participants (List[AssistantAgent]): The list of agents to prepare.
            termination_string (str): The string that will be used to terminate the team.
            max_turns (int): The maximum number of turns for the team.
        """
        
        return RoundRobinGroupChat(
            participants=participants, 
            termination_condition=TextMentionTermination(termination_string), 
            max_turns=max_turns
        )
    
    def equip_tools_for_agent(self, agent: AssistantAgent, tools: List[Callable]):
        """Equip the agent with the given tools."""
        agent_w_tools = AssistantAgent(
            name=agent.name,
            model_client=agent._model_client,
            system_message=agent._system_messages[0].content,
            reflect_on_tool_use=agent._reflect_on_tool_use, 
            tools=tools, 
        )
        
        return agent_w_tools
    
    async def run_team_stream(self, team: BaseGroupChat, task: str | BaseChatMessage | List[BaseChatMessage]) -> TaskResult:
        stream = team.run_stream(task=task)
        async for message in stream:
            await asyncio.sleep(5)  # Add delay to slow down the process
            if isinstance(message, TaskResult):
                if self.verbose:
                    print("Task Finished")
                result = message
            else:
                if self.verbose:
                    print(message.source,": \n", message.content)
                pass
        
        return result

    async def plan(self, task: Task) -> ProcessContext:
        if self.verbose:
            print(">>> Plan Stage: \n")
            
        config = get_config(task.bind_config, task.db_path).config
        settings = config.get("skills", {})
        attempt_id = uuid.uuid4().hex
        log_path = Path(task.db_path).parent / "plan" / f"planner_{task.id}.jsonl"
        agent_config = dict(config["agents"]["planner"])
        options = {}
        if settings.get("enabled", False):
            skills = SkillSession(settings, task_id=task.id, log_path=log_path,
                                  attempt_id=attempt_id)
            agent_config["system_message"] += "\n" + skills.instructions
            options = {"tools": [skills.search_skills, skills.read_skill],
                       "reflect_on_tool_use": True,
                       "max_tool_iterations": settings.get("max_tool_iterations", 4)}
        planner = init_agents(agent_config, **options)
        full_context = [TextMessage(content=task.content, source="user")]
        started = time.monotonic()
        log = dict(task_id=task.id, attempt_id=attempt_id, role="planner")
        record_event(log_path, **log, event="planner_start",
                     skills_enabled=bool(settings.get("enabled", False)))
        await planner.on_reset(CancellationToken())
        try:
            for attempt in range(2):
                final_text = ""
                # Persist tool/model events as they arrive, including before a failed retry.
                async for message in planner.on_messages_stream(
                    [full_context[-1]], CancellationToken()
                ):
                    if isinstance(message, Response):
                        message = message.chat_message
                        final_text = message.content
                    full_context.append(message)
                    record_event(log_path, **log, event="message",
                                 message=message.model_dump(mode="json"))
                try:
                    start = final_text.index("<building_plan>")
                    end = final_text.index("</building_plan>", start) + len("</building_plan>")
                    result = xml_to_dict(ET.fromstring(final_text[start:end]))
                    if (not isinstance(result, dict)
                            or not isinstance(result.get("sub_structures"), dict)
                            or not result["sub_structures"]):
                        raise ValueError("Missing nonempty sub_structures")
                    break
                except (ValueError, ET.ParseError) as error:
                    if attempt:
                        raise
                    full_context.append(TextMessage(
                        content=f"The output is not well-formatted, please try again. "
                                f"Error parsing the content: {error}",
                        source="user",
                    ))
            record_event(log_path, **log, event="planner_result", result=result,
                         token_input=get_token_input(full_context),
                         token_output=get_token_output(full_context),
                         elapsed_seconds=time.monotonic() - started)
        except BaseException as error:
            record_event(log_path, **log, event="planner_error", error=type(error).__name__,
                         token_input=get_token_input(full_context),
                         token_output=get_token_output(full_context),
                         elapsed_seconds=time.monotonic() - started)
            raise

        if self.verbose:
            print(result)
        context = ProcessContext(context=full_context, 
                                 result=result, 
                                 token_input=get_token_input(full_context), 
                                 token_output=get_token_output(full_context), 
                                 turn=get_turn(full_context),
                                 objection=None)
        return context
    
    async def draft(self, task: Task) -> ProcessContext: 
        # Initialize objection
        objection = Objection(task)
        
        if self.verbose:
            print(">>> Draft Stage: \n")
        
        config = get_config(task.bind_config, task.db_path).config
        drafter = init_agents(config['agents']['drafter'])
        draft_reviewer = init_agents(config['agents']['draft_reviewer'])
            
        task = task.content

        # Equip the draft_reviewer with the objection tool
        draft_reviewer = self.equip_tools_for_agent(draft_reviewer, [objection.raise_objection_draft])
        
        # Check if the task has raised objection
        # Reset agents
        await drafter.on_reset(CancellationToken())
        await draft_reviewer.on_reset(CancellationToken())
        
        draft_team = self.prepare_team(participants=[drafter, draft_reviewer])
        draft_result = await self.run_team_stream(draft_team, task)

        summary_prompt = "Please format the final version of the blueprint according to the final decision of the reviewer."
        draft_summary = await drafter.on_messages([TextMessage(content=summary_prompt, source="user")], CancellationToken())

        draft_result.messages += [*getattr(draft_summary, "inner_messages", []), draft_summary.chat_message]
        
        turn = get_turn(draft_result.messages)
        token_input = get_token_input(draft_result.messages)
        token_output = get_token_output(draft_result.messages)
        
        if self.verbose:
            print(">>> Blueprint: \n")
            print(draft_summary.chat_message.content)
            print(">>> \n")
        context = ProcessContext(context=draft_result.messages, 
                                 result=draft_summary.chat_message.content, 
                                 token_input=token_input, 
                                 token_output=token_output, 
                                 turn=turn, 
                                 objection=objection.objection_raised)
        return context
    
    async def build(self, task: Task, refine=False, assemble=False) -> ProcessContext:
        # Initialize machine and bind tools to builder
        if not refine:
            machine_id = task.id
            machine = Machine(name=machine_id, save_dir=SavedMachines, db_path=task.db_path) if not assemble else Assembly(name=machine_id, save_dir=SavedMachines, db_path=task.db_path)
        else:
            machine_id = task.parent_id
            machine = Machine(name=f"{machine_id}_rfd", save_dir=SavedMachines, db_path=task.db_path)
            machine = machine.from_file(file_path=os.path.join(os.path.dirname(task.db_path), "machine", machine_id, f"{machine_id}.json"))
        objection = Objection(task, machine)
            
        save_dir = os.path.join(os.path.dirname(task.db_path), "machine", machine_id if not refine else f"{machine_id}_rfd")
        os.makedirs(save_dir, exist_ok=True)
        
        config = get_config(task.bind_config, task.db_path).config
        builder = init_agents(config['agents']['builder'])
        guidance_config = dict(config['agents']['guidance'])
        guidance_config["system_message"] += "\n" + objection.geometry_instructions
        guidance = init_agents(guidance_config)
            
        if self.verbose:
            stage_name = "Assemble" if assemble else "Build" if not refine else "Refine"
            print(f">>> {stage_name} Stage: \n")
        task = task.content
        max_turns = 300
        
        if not refine:
            tools = machine.tools["build"] + machine.tools["refine"] + machine.tools["default"]
        else:
            tools = machine.tools["refine"] + machine.tools["default"]
        
        # Exclusively add "start" function to building tools
        if not assemble:
            tools += machine.tools["build_only"]
            
        builder = self.equip_tools_for_agent(builder, tools)
        guidance = self.equip_tools_for_agent(guidance, [
            machine.get_block_details, objection.inspect_geometry,
            objection.raise_objection_build if not refine else objection.raise_objection_refine,
        ])
        
        await builder.on_reset(CancellationToken())
        await guidance.on_reset(CancellationToken())
        participants = [builder, guidance] if not refine else [guidance, builder]
        build_team = self.prepare_team(participants=participants, max_turns=max_turns)
        build_result = await self.run_team_stream(build_team, task)
        
        # Save machine and preview images under the save_dir
        machine.to_file(output_dir=save_dir)
        bsg_path = os.path.join(save_dir, f"{machine.name}.bsg")

        if self.verbose:
            print(f"Machine saved to {bsg_path}")
            print(">>> \n")
        
        result = {
            "result": machine.get_machine_summary(), 
            "cost": machine.cost, 
            "num_blocks": machine.num_blocks, 
            "has_spinful": machine.has_spinful}
        
        turn = get_turn(build_result.messages)
        token_input = get_token_input(build_result.messages)
        token_output = get_token_output(build_result.messages)
        context = ProcessContext(context=build_result.messages, 
                                 result=result, 
                                 token_input=token_input, 
                                 token_output=token_output, 
                                 turn=turn, 
                                 objection=objection.objection_raised)
        return context

    async def control(self, task: Task, revision: Tuple[List[Dict[str, str]], str] | None = None, gen: int = 1):
        if gen > 1:
            assert revision is not None, "Revision is required for generation > 1"
        # Initialize machine and bind tools to builder
        machine_id = task.bind_machine
        machine = Machine(name=machine_id, save_dir=SavedMachines)
        machine = machine.from_file(file_path=os.path.join(os.path.dirname(task.db_path), "machine", machine_id, f"{machine_id}.json"))
        save_dir = os.path.join(os.path.dirname(task.db_path), "machine", machine_id)
        os.makedirs(save_dir, exist_ok=True)

        if machine.num_blocks <= 1:
            raise ValueError("The machine has no existing blocks to control")

        task_content = task.content
        if self.verbose:
            print(">>> Control Stage: \n")
        
        machine_summary = machine.get_machine_summary()
        control_config = machine.review_control_config()
        available_actions = machine.review_powered_blocks()
        if len(machine._powered_blocks()) == 0:
            raise ValueError("The machine has no powered blocks to control")

        current_machine_state= "\n".join(["Machine Summary: ", machine_summary, "Available Actions: ", available_actions, "Control Config: ", control_config])

        task_messages = []

        if revision:  # Revision content is the previous control summary
            previous_control_messages, simulation_feedback = revision
            for message in previous_control_messages:
                task_messages.append(TextMessage(content=message["content"], source=message["source"]))
            task_messages.append(TextMessage(content=simulation_feedback, source="user"))
            task_messages.append(TextMessage(content="The control info is reset to default.", source="user"))
            task_messages.append(TextMessage(content=current_machine_state, source="user"))
            task_messages.append(TextMessage(content="Please analyze the motion trajectory of the previous control result and design the new control configuration and sequence to optimize the task.", source="user"))
        else:
            task_messages.append(TextMessage(content=task_content, source="user"))
            task_messages.append(TextMessage(content=current_machine_state, source="user"))

        config = get_config(task.bind_config, task.db_path).config
        controller_config = config['agents']['controller']
        controller = init_agents(controller_config)

        await controller.on_reset(CancellationToken())
                    
        control_response = await controller.on_messages(task_messages, CancellationToken())

        control_messages = task_messages + [
            *getattr(control_response, "inner_messages", []), 
            control_response.chat_message
            ]
        
        control_text = control_response.chat_message.content
        json_text = control_text.split("```json")[1].split("```")[0]
        control_protocol = json.loads(json_text)
        file_path = os.path.join(os.path.dirname(task.db_path), "simulation", machine_id, f"{machine_id}_ctrl_{gen}.json")
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(control_protocol, f, ensure_ascii=False, indent=2)

        turn = get_turn(control_messages)
        token_input = get_token_input(control_messages)
        token_output = get_token_output(control_messages)
        context = ProcessContext(context=control_messages, 
                                 result=file_path, 
                                 token_input=token_input, 
                                 token_output=token_output, 
                                 turn=turn, 
                                 objection=None)
        return context
