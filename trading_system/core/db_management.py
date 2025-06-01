import subprocess
import sys
from pathlib import Path

# Resolve PROJECT_ROOT_DB_MGMT based on this script's location
# Assumes this script is in trading_system/core/
# PROJECT_ROOT should be /app, so three levels up from trading_system/core/db_management.py
PROJECT_ROOT_DB_MGMT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT_DB_MGMT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_DB_MGMT))

# Now core.config and core.logger should be importable
from trading_system.core.config import DATABASE_URL
from trading_system.core.logger import base_logger

def run_migrations():
    base_logger.info(f"Running database migrations for DB at: {DATABASE_URL}")
    try:
        if DATABASE_URL.startswith("sqlite:///"):
            db_path_str = DATABASE_URL.split("sqlite:///", 1)[1]
            db_file = Path(db_path_str)
            if not db_file.is_absolute():
                # db_file path in DATABASE_URL like "./trading_system/data/trading_system.db"
                # is relative to PROJECT_ROOT where alembic commands are typically run from.
                db_file = PROJECT_ROOT_DB_MGMT / db_file

            db_file.parent.mkdir(parents=True, exist_ok=True)
            base_logger.info(f"Ensured database directory exists: {db_file.parent}")

        alembic_cfg_path = PROJECT_ROOT_DB_MGMT / "alembic.ini"
        if not alembic_cfg_path.exists():
            base_logger.error(f"Alembic config file not found at {alembic_cfg_path}")
            raise FileNotFoundError(f"Alembic config file not found at {alembic_cfg_path}")

        # Use poetry run to ensure alembic runs in the correct venv
        cmd = ["poetry", "run", "alembic", "-c", str(alembic_cfg_path), "upgrade", "head"]
        base_logger.info(f"Executing migration command: {' '.join(cmd)} from CWD: {PROJECT_ROOT_DB_MGMT}")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=PROJECT_ROOT_DB_MGMT, # Run alembic from project root
            text=True
        )
        stdout, stderr = process.communicate()

        if process.returncode == 0:
            base_logger.info("Database migrations applied successfully.")
            if stdout: base_logger.info("Stdout:\n" + stdout)
        else:
            base_logger.error("Error applying database migrations:")
            if stdout: base_logger.error("Stdout:\n" + stdout)
            if stderr: base_logger.error("Stderr:\n" + stderr)
            raise Exception(f"Migration failed with return code {process.returncode}")
    except Exception as e:
        base_logger.error(f"An exception occurred during migrations: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    try:
        run_migrations()
    except Exception as e:
        print(f"Failed to run migrations: {e}")
        sys.exit(1)
