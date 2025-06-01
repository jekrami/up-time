import os
from dotenv import load_dotenv
from pathlib import Path

# This config.py is in PROJECT_DIR/trading_system/core/
# So PROJECT_ROOT is three levels up from this file's directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
ENV_PATH = CONFIG_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    ENV_PATH_ROOT_FALLBACK = PROJECT_ROOT / ".env"
    if ENV_PATH_ROOT_FALLBACK.exists():
        load_dotenv(dotenv_path=ENV_PATH_ROOT_FALLBACK)
        print(f"Warning: .env file not found at {ENV_PATH}. Loaded .env from project root: {ENV_PATH_ROOT_FALLBACK}")
    else:
        print(f"Warning: .env file not found at {ENV_PATH} or {ENV_PATH_ROOT_FALLBACK}. Using default environment variables or expecting them to be set externally.")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'trading_system' / 'data' / 'trading_system.db'}")
CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
DEFAULT_SLIPPAGE_PERCENT = float(os.getenv("DEFAULT_SLIPPAGE_PERCENT", "0.001"))
DEFAULT_TRADING_FEE_PERCENT = float(os.getenv("DEFAULT_TRADING_FEE_PERCENT", "0.001"))

DATA_DIR = PROJECT_ROOT / "trading_system" / "data"
LOGS_DIR = PROJECT_ROOT / "logs"

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

if not CRYPTOPANIC_API_KEY or CRYPTOPANIC_API_KEY == "dummy_key_for_now":
    print(f"Warning: CRYPTOPANIC_API_KEY is not set or is using the dummy key. Please set it in {ENV_PATH} for news fetching.")
