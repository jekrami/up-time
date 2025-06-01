import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

try:
    from trading_system.core.config import LOGS_DIR, PROJECT_ROOT
except ModuleNotFoundError as e:
    print(f"logger.py: Initial import of config failed: {e}. This might be due to PYTHONPATH issues or circular dependencies during setup.")
    # Fallback LOGS_DIR calculation if config can't be imported yet
    # Assumes this file (logger.py) is in PROJECT_ROOT/trading_system/core/
    CURRENT_FILE_DIR = Path(__file__).resolve().parent
    PROJECT_ROOT = CURRENT_FILE_DIR.parent.parent # Should be ai_crypto_trading_system
    LOGS_DIR = PROJECT_ROOT / 'logs'
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"logger.py: Using fallback LOGS_DIR: {LOGS_DIR}")

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def setup_logger(name="trading_system", level_str="INFO", log_to_console=True, log_to_file=True):
    logger = logging.getLogger(name)
    level = getattr(logging, level_str.upper(), logging.INFO)
    logger.setLevel(level)
    if logger.hasHandlers():
        logger.handlers.clear()
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    if log_to_file:
        log_file = LOGS_DIR / f'{name}.log'
        try:
            file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Could not set up file logger at {log_file}: {e}")
    logger.propagate = False
    return logger

# Initialize base_logger when module is loaded
base_logger = setup_logger()
if LOGS_DIR:
    base_logger.info(f"Logger initialized. Logging to console and configured file(s) in: {LOGS_DIR}")
else:
    base_logger.warning("Logger initialized, but LOGS_DIR was not properly determined. File logging may fail.")
