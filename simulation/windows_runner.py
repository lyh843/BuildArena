"""Native Windows endpoint. Start in a stopped game with calibrated Lua panels."""

import argparse
from collections import defaultdict
import csv
from datetime import datetime
import hashlib
import io
import json
import math
from pathlib import Path
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET


def telemetry_rows(text, auxiliary_ids=None):
    rows = []
    for row in csv.reader(io.StringIO(text)):
        row = [value.strip() for value in row]
        if len(row) not in (3, 5) or not row[1].startswith("ID_"):
            continue
        if len(row) == 3 and auxiliary_ids is not None and row[1] not in auxiliary_ids:
            continue
        try:
            numbers = [row[0], *row[2:]]
            if len(row) == 3 and row[2] in ("true", "false"):
                numbers = [row[0]]
            if not all(math.isfinite(float(value)) for value in numbers):
                continue
        except ValueError:
            continue
        rows.append(row)
    return rows


def consolidate_telemetry(rows, duration):
    unique = {tuple(row) for row in rows if 0 <= float(row[0]) <= duration}
    values = defaultdict(set)
    def key(row):
        return float(row[0]), row[1], len(row)
    for row in unique:
        values[key(row)].add(tuple(value if value in ("true", "false") else float(value)
                                   for value in row[2:]))
    # A partially copied final number can be valid syntax but a false position.
    conflicts = {identity for identity, readings in values.items() if len(readings) > 1}
    cleaned = sorted((row for row in unique if key(row) not in conflicts), key=key)
    return cleaned, sorted(conflicts)


def button_state(image):
    pink = cyan = 0
    for count, (red, green, blue) in image.convert("RGB").getcolors(image.width * image.height):
        pink += count * (red > 180 and green < 100 and blue > 40)
        cyan += count * (red < 100 and green > 140 and blue > 140)
    if pink > 20 and cyan < 10:
        return "stopped"
    if cyan > 20 and pink < 10:
        return "running"
    raise RuntimeError("Cannot recognize the play/stop button; check game scene and UI profile")


def usable_capture(image):
    return sum(image.convert("L").resize((64, 40)).histogram()[41:]) >= 256


def run(profile, machine_file, output_dir, duration, set_ground=False):
    # No construction, model, or geometry dependencies belong on this side.
    import pyautogui
    import pyperclip
    import win32gui
    from PIL import ImageGrab

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from simulation.operations import windows_click, windows_focus_window, copy_text

    if not 0 < duration <= 60:
        raise ValueError("Duration must be between 0 and 60 seconds")
    machine_file, output_dir = Path(machine_file), Path(output_dir)
    root = ET.parse(machine_file).getroot()
    source = root.find("./Data/StringArray[@key='lua_data']")
    if source is None or not source.text:
        raise ValueError("Machine has no embedded Lua telemetry")
    expected_ids = set(re.findall(r'"(ID_[^"]+)"', source.text))
    auxiliary_ids = {
        block_id for format_string, block_id in re.findall(
            r'string\.format\("([^"]+)", current_time, "(ID_[^"]+)"', source.text
        ) if format_string.count(",") == 2
    }
    if not expected_ids:
        raise ValueError("Machine has no tracked block IDs")
    lua_file = Path(profile["lua_file"])
    saved = Path(profile["saved_machines"]) / machine_file.name
    if not saved.parent.is_dir() or not lua_file.is_file():
        raise FileNotFoundError("Configured SavedMachines or LuaRoot/main.lua is missing")
    if saved.exists() and saved.read_bytes() != machine_file.read_bytes():
        raise FileExistsError(f"Refusing to overwrite a different saved machine: {saved}")

    title = profile.get("window_name", "Besiege")
    if not windows_focus_window(title):
        raise RuntimeError("Besiege window not found. No input was sent.")
    time.sleep(1)
    hwnd = win32gui.FindWindow(None, title)
    width, height = profile["client_size"]
    points = profile["positions"]

    def check_focus():
        if (not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd)
                or win32gui.GetForegroundWindow() != hwnd):
            raise RuntimeError("Besiege lost focus; automation stopped")
        if win32gui.GetClientRect(hwnd) != (0, 0, width, height):
            raise RuntimeError("Game client size changed; recalibrate the UI profile")

    def capture():
        check_focus()
        x, y = win32gui.ClientToScreen(hwnd, (0, 0))
        for _ in range(10):
            image = ImageGrab.grab(bbox=(x, y, x + width, y + height), all_screens=True)
            if usable_capture(image):
                return image
            time.sleep(0.2)
            check_focus()
        raise RuntimeError("Game capture is black; keep the desktop unlocked and game visible")

    def set_lua_visible(visible):
        x, y = points["lua_indicator"]
        def observed():
            image = capture().crop((x - 3, y - 3, x + 3, y + 3)).convert("RGB")
            return sum(count for count, (r, g, b) in image.getcolors(36)
                       if r > 130 and g < 90 and 40 < b < 140) > 18
        if observed() != visible:
            check_focus()
            # Unity's log text field consumes shortcuts until it loses focus.
            windows_click(*win32gui.ClientToScreen(hwnd, (width - 100, height - 150)))
            time.sleep(0.3)
            pyautogui.hotkey("ctrl", "l", interval=0.08)
            time.sleep(0.5)
        for _ in range(10):
            if observed() == visible:
                return
            time.sleep(0.2)
        raise RuntimeError("Lua panel did not reach the requested visibility")

    def state(expected=None):
        x, y = points["start_stop"]
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            image = capture()
            try:
                current = button_state(image.crop((x - 20, y - 22, x + 20, y + 23)))
            except RuntimeError:
                current = None
            if current is not None and (expected is None or current == expected):
                return current
            time.sleep(0.2)
        output_dir.mkdir(parents=True, exist_ok=True)
        image.save(output_dir / "button_state_failed.png")
        raise RuntimeError(f"Could not confirm game button state: {expected or 'recognized'}")

    def click(name):
        check_focus()
        x, y = points[name]
        if not (0 <= x < width and 0 <= y < height):
            raise ValueError(f"Invalid client position: {name}")
        windows_click(*win32gui.ClientToScreen(hwnd, (x, y)))
        time.sleep(0.3)

    if state() != "stopped":
        raise RuntimeError("Stop the current simulation before running a new sample")
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_file = output_dir / f"simulation_log_{machine_file.stem}.csv"
    if csv_file.exists():
        raise FileExistsError(f"Refusing to overwrite previous telemetry: {csv_file}")
    raw_file = csv_file.with_suffix(".raw.txt")
    if raw_file.exists():
        raise FileExistsError(f"Previous attempt exists; preserve it before retrying: {raw_file}")
    if not saved.exists():
        shutil.copy2(machine_file, saved)
    capture().save(csv_file.with_suffix(".before.png"))
    set_lua_visible(False)

    click("open_folder")
    time.sleep(1)
    click("enter_name")
    time.sleep(0.5)
    check_focus()
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.3)
    pyperclip.copy(machine_file.stem)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.3)
    # Unity's filename field appends a zero-width caret marker when copied.
    if copy_text().strip().removesuffix("\u200b") != machine_file.stem:
        capture().save(csv_file.with_suffix(".filename_failed.png"))
        raise RuntimeError("Machine filename field did not accept the requested filename")
    pyperclip.copy("")
    check_focus()
    click("open_machine")
    time.sleep(3)
    loaded = lua_file.read_text(encoding="utf-8-sig")
    if loaded.strip() != source.text.strip():
        capture().save(csv_file.with_suffix(".load_failed.png"))
        raise RuntimeError("Loaded Lua does not match this BSG; refusing to simulate the wrong machine")
    if set_ground:
        click("set_ground")
        time.sleep(0.5)
    capture().save(csv_file.with_suffix(".loaded.png"))
    set_lua_visible(True)

    def collect():
        click("log")
        check_focus()
        pyperclip.copy("")
        text = copy_text()
        check_focus()
        rows = telemetry_rows(text, auxiliary_ids)
        if not rows:
            raise RuntimeError("No numeric Lua telemetry copied; open the Lua Log and calibrate its position")
        ids = {row[1] for row in rows}
        if not ids <= expected_ids:
            raise RuntimeError(f"Unexpected block IDs in Lua log: {ids - expected_ids}")
        # Persist only validated game telemetry, never arbitrary clipboard content.
        with raw_file.open("a", encoding="utf-8", newline="") as stream:
            csv.writer(stream).writerows(rows)
        return rows

    collected = []
    started = False
    simulation_time = 0.0
    cleanup_warning = None
    try:
        if state() != "stopped":
            raise RuntimeError("Game is no longer stopped")
        started = True
        click("start_stop")
        start = time.monotonic()
        pyautogui.moveTo(*win32gui.ClientToScreen(hwnd, (width - 100, height - 150)))
        time.sleep(0.5)
        state("running")
        while simulation_time < duration:
            if time.monotonic() - start > max(15, duration * 2):
                raise TimeoutError("Game did not produce the requested simulation seconds in time")
            batch = collect()
            collected.extend(batch)
            simulation_time = max(float(row[0]) for row in batch)
            time.sleep(0.2)
    finally:
        if started:
            if not windows_focus_window(title):
                raise RuntimeError("Cannot focus Besiege to stop physics; stop the game manually")
            time.sleep(0.2)
            if state() == "running":
                click("start_stop")
                time.sleep(0.5)
            state("stopped")
            capture().save(csv_file.with_suffix(".stopped.png"))
            try:
                collected.extend(collect())
            finally:
                check_focus()
                try:
                    set_lua_visible(False)
                except RuntimeError as error:
                    cleanup_warning = str(error)
    unique, conflicts = consolidate_telemetry(collected, duration)
    positions = [row for row in unique if len(row) == 5]
    observed_ids = {row[1] for row in positions}
    if not expected_ids <= observed_ids:
        raise RuntimeError(f"Missing position telemetry for blocks: {expected_ids - observed_ids}")
    times = [float(row[0]) for row in positions]
    if min(times) > 1 or max(times) < duration * 0.9:
        raise RuntimeError(f"Incomplete simulation time range: {min(times)}..{max(times)}")
    with csv_file.open("x", newline="", encoding="utf-8") as stream:
        csv.writer(stream).writerows(unique)
    report = {
        "machine": machine_file.stem,
        "machine_sha256": hashlib.sha256(machine_file.read_bytes()).hexdigest(),
        "recorded_at": datetime.now().isoformat(),
        "requested_seconds": duration, "time_range": [min(times), max(times)],
        "unique_rows": len(unique), "tracked_ids": sorted(observed_ids),
        "discarded_conflicting_keys": conflicts,
        "cleanup_warning": cleanup_warning,
        "set_ground": set_ground, "physics_stopped": True, "profile": profile,
    }
    csv_file.with_suffix(".runtime.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Validated {len(unique)} rows: {csv_file}", flush=True)
    return str(csv_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--machine-file", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--set-ground", action="store_true")
    args = parser.parse_args()
    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    run(profile, args.machine_file, args.output_dir, args.duration, args.set_ground)
