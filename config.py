import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

API_KEY_OAI = os.getenv("API_KEY_OAI", "")
API_KEY_DS = os.getenv("API_KEY_DS", "")
API_KEY_ANT = os.getenv("API_KEY_ANT", "")
API_KEY_ARC = os.getenv("API_KEY_ARC", "")
API_KEY_XAI = os.getenv("API_KEY_XAI", "")
API_KEY_MS = os.getenv("API_KEY_MS", "")
API_KEY_ALI = os.getenv("API_KEY_ALI", "")
API_KEY_GOOGLE = os.getenv("API_KEY_GOOGLE", "")
ALI_BASE_URL = os.getenv(
    "ALI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
SavedMachines = os.getenv("SavedMachines", "./datacache/SavedMachines")
WINDOWS_PYTHON = os.getenv("BUILD_ARENA_WINDOWS_PYTHON", "")
WINDOWS_PROFILE = os.getenv("BUILD_ARENA_WINDOWS_PROFILE", "")

# Calibrate these positions before running Besiege simulations.
POS_OPEN_FOLDER = (0.202, 0.035)
POS_ENTER_NAME = (0.476, 0.215)
POS_OPEN_MACHINE = (0.638, 0.209)
POS_SET_GROUND = (0.403, 0.0185)
POS_LOG_WINDOW = (0.185, 0.172)
POS_EMPTY_SPACE = (0.034, 0.726)
POS_START_SIMU = (0.021, 0.016)
POS_DELETE = (0.707, 0.038)
POS_CONFIRM = (0.538, 0.586)
