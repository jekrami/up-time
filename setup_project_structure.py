import os
import sys
from pathlib import Path

# Define project root relative to this script's execution path
# Assuming this script is run from /app (one level above project root)
# Or, more robustly, make paths absolute from a known project structure.
# For this execution, we assume the script is in /app, and we operate on /app/ai_crypto_trading_system
PROJECT_DIR = Path.cwd() / "ai_crypto_trading_system"

# Ensure the main project directory exists if script is run from /app
PROJECT_DIR.mkdir(exist_ok=True)

# 1. Create .env.example and .env files
config_dir = PROJECT_DIR / "config"
config_dir.mkdir(exist_ok=True)

env_example_content = (
    "# Database Configuration\n"
    'DATABASE_URL="sqlite:///./trading_system/data/trading_system.db"\n\n'
    "# API Keys\n"
    'CRYPTOPANIC_API_KEY="YOUR_CRYPTOPANIC_API_KEY_HERE"\n\n'
    "# Ollama Configuration\n"
    'OLLAMA_BASE_URL="http://localhost:11434"\n'
    'OLLAMA_MODEL="llama3"\n\n'
    "# Trading Parameters (examples)\n"
    'DEFAULT_SLIPPAGE_PERCENT="0.001" # 0.1%\n'
    'DEFAULT_TRADING_FEE_PERCENT="0.001" # 0.1%\n'
)
with open(config_dir / ".env.example", "w") as f:
    f.write(env_example_content)
with open(config_dir / ".env", "w") as f:
    f.write(env_example_content.replace("YOUR_CRYPTOPANIC_API_KEY_HERE", "dummy_key_for_now"))

# 2. Create trading_system/core/config.py
# Path adjustments are crucial here.
# The trading_system directory is inside ai_crypto_trading_system
ts_core_dir = PROJECT_DIR / "trading_system" / "core"
ts_core_dir.mkdir(parents=True, exist_ok=True)

# Correct PROJECT_ROOT calculation within config.py
# It should point to ai_crypto_trading_system directory
config_py_content = (
    "import os\n"
    "from dotenv import load_dotenv\n"
    "from pathlib import Path\n\n"
    "# This config.py is in PROJECT_DIR/trading_system/core/\n"
    "# So PROJECT_ROOT is three levels up from this file's directory.\n"
    "PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent\n"
    'CONFIG_DIR = PROJECT_ROOT / "config"\n'
    'ENV_PATH = CONFIG_DIR / ".env"\n\n'
    "if ENV_PATH.exists():\n"
    "    load_dotenv(dotenv_path=ENV_PATH)\n"
    "else:\n"
    # Fallback for .env in project root (less ideal but can be a backup)
    '    ENV_PATH_ROOT_FALLBACK = PROJECT_ROOT / ".env"\n'
    "    if ENV_PATH_ROOT_FALLBACK.exists():\n"
    "        load_dotenv(dotenv_path=ENV_PATH_ROOT_FALLBACK)\n"
    '        print(f"Warning: .env file not found at {ENV_PATH}. Loaded .env from project root: {ENV_PATH_ROOT_FALLBACK}")\n'
    "    else:\n"
    '        print(f"Warning: .env file not found at {ENV_PATH} or {ENV_PATH_ROOT_FALLBACK}. Using default environment variables or expecting them to be set externally.")\n\n'
    # Ensure DATABASE_URL is relative to PROJECT_ROOT correctly
    'DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT / \'trading_system\' / \'data\' / \'trading_system.db\'}")\n'
    'CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY")\n'
    'OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")\n'
    'OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")\n'
    'DEFAULT_SLIPPAGE_PERCENT = float(os.getenv("DEFAULT_SLIPPAGE_PERCENT", "0.001"))\n'
    'DEFAULT_TRADING_FEE_PERCENT = float(os.getenv("DEFAULT_TRADING_FEE_PERCENT", "0.001"))\n\n'
    'DATA_DIR = PROJECT_ROOT / "trading_system" / "data"\n'
    'LOGS_DIR = PROJECT_ROOT / "logs"\n\n' # Logs dir at project root
    "DATA_DIR.mkdir(parents=True, exist_ok=True)\n"
    "LOGS_DIR.mkdir(parents=True, exist_ok=True)\n\n"
    'if not CRYPTOPANIC_API_KEY or CRYPTOPANIC_API_KEY == "dummy_key_for_now":\n'
    '    print(f"Warning: CRYPTOPANIC_API_KEY is not set or is using the dummy key. Please set it in {ENV_PATH} for news fetching.")\n'
)
with open(ts_core_dir / "config.py", "w") as f:
    f.write(config_py_content)

# 3. Create trading_system/core/logger.py
logger_py_content = (
    "import logging\n"
    "import sys\n"
    "from logging.handlers import RotatingFileHandler\n"
    "from pathlib import Path\n\n"
    "try:\n"
    "    from trading_system.core.config import LOGS_DIR, PROJECT_ROOT\n"
    "except ModuleNotFoundError as e:\n"
    '    print(f"logger.py: Initial import of config failed: {e}. This might be due to PYTHONPATH issues or circular dependencies during setup.")\n'
    "    # Fallback LOGS_DIR calculation if config can't be imported yet\n"
    "    # Assumes this file (logger.py) is in PROJECT_ROOT/trading_system/core/\n"
    "    CURRENT_FILE_DIR = Path(__file__).resolve().parent\n"
    "    PROJECT_ROOT = CURRENT_FILE_DIR.parent.parent # Should be ai_crypto_trading_system\n"
    "    LOGS_DIR = PROJECT_ROOT / 'logs'\n"
    "    LOGS_DIR.mkdir(parents=True, exist_ok=True)\n"
    '    print(f"logger.py: Using fallback LOGS_DIR: {LOGS_DIR}")\n\n'
    'LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s"\n'
    'DATE_FORMAT = "%Y-%m-%d %H:%M:%S"\n\n'
    'def setup_logger(name="trading_system", level_str="INFO", log_to_console=True, log_to_file=True):\n'
    "    logger = logging.getLogger(name)\n"
    "    level = getattr(logging, level_str.upper(), logging.INFO)\n"
    "    logger.setLevel(level)\n"
    "    if logger.hasHandlers():\n"
    "        logger.handlers.clear()\n"
    "    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)\n"
    "    if log_to_console:\n"
    "        console_handler = logging.StreamHandler(sys.stdout)\n"
    "        console_handler.setFormatter(formatter)\n"
    "        logger.addHandler(console_handler)\n"
    "    if log_to_file:\n"
    "        log_file = LOGS_DIR / f'{name}.log'\n"
    "        try:\n"
    "            file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)\n"
    "            file_handler.setFormatter(formatter)\n"
    "            logger.addHandler(file_handler)\n"
    "        except Exception as e:\n"
    '            print(f"Warning: Could not set up file logger at {log_file}: {e}")\n'
    "    logger.propagate = False\n"
    "    return logger\n\n"
    "# Initialize base_logger when module is loaded\n"
    "base_logger = setup_logger()\n"
    "if LOGS_DIR:\n" # LOGS_DIR might be None if fallback failed critically, though unlikely with mkdir
    '    base_logger.info(f"Logger initialized. Logging to console and configured file(s) in: {LOGS_DIR}")\n'
    "else:\n"
    '    base_logger.warning("Logger initialized, but LOGS_DIR was not properly determined. File logging may fail.")\n'

)
with open(ts_core_dir / "logger.py", "w") as f:
    f.write(logger_py_content)

# 4. Add .gitignore entries
gitignore_content = (
    "# Environment variables\n"
    "config/.env\n"
    ".env\n\n"
    "# Logs\n"
    "logs/\n"
    "*.log\n\n"
    "# Python cache\n"
    "__pycache__/\n"
    "*.py[cod]\n\n" # .pyo and .pyd too
    "# Poetry\n"
    ".venv/\n"
    "poetry.lock\n\n" # poetry.lock can be committed depending on policy, but often ignored in libs
    "# IDE specific\n"
    ".idea/\n"
    ".vscode/\n"
    "*.sublime-project\n"
    "*.sublime-workspace\n\n"
    "# Data files (example, uncomment if needed)\n"
    "# trading_system/data/trading_system.db\n"
    "# trading_system/data/*.csv\n\n"
    "# Notebook checkpoints\n"
    ".ipynb_checkpoints/\n\n"
    "# Test reports & coverage\n"
    "htmlcov/\n"
    ".pytest_cache/\n"
    ".coverage*\n" # .coverage and .coverage.*
    "nosetests.xml\n"
    "coverage.xml\n\n"
    "# Build artifacts\n"
    "dist/\n"
    "build/\n"
    "*.egg-info/\n"
    "*.egg\n"
)
gitignore_file = PROJECT_DIR / ".gitignore"
try:
    with open(gitignore_file, "r") as f:
        existing_gitignore = f.read()
    new_entries = []
    for line in gitignore_content.splitlines():
        if line.strip() and line.strip() not in existing_gitignore:
            new_entries.append(line)
    if new_entries:
        with open(gitignore_file, "a") as f:
            f.write("\n# Added by trading_system setup\n")
            f.write("\n".join(new_entries) + "\n")
        print(f"Appended new entries to .gitignore at {gitignore_file}")
except FileNotFoundError:
    with open(gitignore_file, "w") as f:
        f.write(gitignore_content)
    print(f"Created .gitignore at {gitignore_file}")


# 5. Create __init__.py files
# These paths are relative to PROJECT_DIR (ai_crypto_trading_system)
package_dirs_relative_to_project_dir = [
    "trading_system",
    "trading_system/core",
    "trading_system/data_ingestion",
    "trading_system/feature_engineering",
    "trading_system/signal_generation",
    "trading_system/strategies",
    "trading_system/backtesting",
    "trading_system/risk_management",
    "trading_system/execution",
    "trading_system/utils",
    "trading_system/tests", # Added tests to __init__.py creation
    "trading_system/config", # Added config to __init__.py creation
    "trading_system/notebooks", # Added notebooks to __init__.py creation
]
for pkg_rel_dir in package_dirs_relative_to_project_dir:
    pkg_abs_dir = PROJECT_DIR / pkg_rel_dir
    pkg_abs_dir.mkdir(parents=True, exist_ok=True)
    (pkg_abs_dir / "__init__.py").touch()
print(f"Created __init__.py files in {PROJECT_DIR}/trading_system and its subdirectories.")

# Final check print
print(f"Setup script finished. Project Name: {PROJECT_DIR.name}")
print(f"Config directory: {config_dir}")
print(f"Trading system core directory: {ts_core_dir}")

# 6. Test import section (will be run by run_in_bash_session)
# For the test import to work, Python needs to find the 'trading_system' package.
# This means 'ai_crypto_trading_system' must be in PYTHONPATH or the script must be run from there.
# The run_in_bash_session will handle cd-ing into the correct directory.

print("Setup script completed. Test imports will be run by the calling environment.")
