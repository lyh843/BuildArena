"""Keep geometry and scheduling in WSL; run only desktop automation on Windows."""

from pathlib import Path
import platform
import subprocess

from config import WINDOWS_PROFILE, WINDOWS_PYTHON


def windows_path(path):
    return subprocess.check_output(
        ["wslpath", "-w", str(Path(path).resolve())], text=True
    ).strip()


def run_simulation_sequence(machine_name, output_dir, duration, set_ground=False):
    if not WINDOWS_PYTHON:
        if platform.system() == "Linux":
            raise RuntimeError(
                "Set BUILD_ARENA_WINDOWS_PYTHON and BUILD_ARENA_WINDOWS_PROFILE "
                "before running Besiege from WSL."
            )
        from simulation.operations import run_simulation_sequence as native_run
        return native_run(machine_name, output_dir, duration, set_ground)

    if not WINDOWS_PROFILE or not Path(WINDOWS_PROFILE).is_file():
        raise FileNotFoundError("BUILD_ARENA_WINDOWS_PROFILE must point to a calibrated JSON profile")
    if duration <= 0 or duration > 60:
        raise ValueError("Windows simulations must last between 0 and 60 seconds")
    output = Path(output_dir).resolve()
    machine_file = output / f"{machine_name}.bsg"
    if not machine_file.is_file():
        raise FileNotFoundError(machine_file)
    entry = Path(__file__).with_name("windows_runner.py")
    command = [
        WINDOWS_PYTHON, "-B", windows_path(entry),
        "--profile", windows_path(WINDOWS_PROFILE),
        "--machine-file", windows_path(machine_file),
        "--output-dir", windows_path(output),
        "--duration", str(duration),
    ]
    if set_ground:
        command.append("--set-ground")
    # The native runner bounds its loop and stops physics in finally.
    subprocess.run(command, check=True, timeout=duration + 90)
    csv_file = output / f"simulation_log_{machine_name}.csv"
    if not csv_file.is_file() or csv_file.stat().st_size == 0:
        raise RuntimeError(f"Windows runner did not produce telemetry: {csv_file}")
    return str(csv_file)
