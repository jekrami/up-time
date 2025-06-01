import os
import sys
import subprocess
from pathlib import Path

# Ensure project root is in path for imports
PROJECT_ROOT = Path.cwd()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 1. Define SQLAlchemy model for market_data
os.makedirs(PROJECT_ROOT / "trading_system/core", exist_ok=True) # Ensure path is relative to PROJECT_ROOT
models_py_content = '''from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, MetaData, UniqueConstraint
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

metadata_obj = MetaData()
Base = declarative_base(metadata=metadata_obj)

class MarketData(Base):
    __tablename__ = "market_data"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    __table_args__ = (UniqueConstraint('timestamp', 'symbol', name='uq_market_data_timestamp_symbol'),)
    def __repr__(self):
        return f"<MarketData(symbol={self.symbol}, timestamp={self.timestamp}, close={self.close})>"

# Example of another model if needed later
# class NewsSentiment(Base):
#     __tablename__ = "news_sentiment"
#     id = Column(Integer, primary_key=True, index=True, autoincrement=True)
#     timestamp = Column(DateTime, default=func.now())
#     source = Column(String) # eg CryptoPanic
#     symbol = Column(String, index=True) # eg BTC, ETH
#     sentiment_score = Column(Float) # eg from Ollama
#     raw_news_data = Column(String) # Store the raw news item text or json
#     llm_summary = Column(String) # Store summary from LLM
#     __table_args__ = (UniqueConstraint('timestamp', 'symbol', 'source', name='uq_news_sentiment_timestamp_symbol_source'),)
'''
with open(PROJECT_ROOT / "trading_system/core/models.py", "w") as f:
    f.write(models_py_content)
(PROJECT_ROOT / "trading_system/core/__init__.py").touch() # Ensure __init__.py exists

# 2. Set up Alembic
print("Initializing Alembic...")
# Use subprocess for better control and error handling
# Ensure alembic directory is created at PROJECT_ROOT
alembic_dir_path = PROJECT_ROOT / "alembic"
init_cmd = ["poetry", "run", "alembic", "init", str(alembic_dir_path.name)] # Pass only dir name for init
init_result = subprocess.run(init_cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)

if init_result.returncode != 0:
    print(f"Alembic init failed: {init_result.stderr}")
    if alembic_dir_path.exists():
        # Using shutil for robust directory removal if needed, but subprocess rm -rf is also fine
        import shutil
        shutil.rmtree(alembic_dir_path)
        print(f"Removed potentially corrupted alembic directory at {alembic_dir_path}")
    # Retry init
    init_result = subprocess.run(init_cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    if init_result.returncode != 0:
        raise Exception(f"Alembic init failed even after retry: {init_result.stderr} {init_result.stdout}")
print(f"Alembic initialized at {alembic_dir_path}. Output: {init_result.stdout}")


print("Configuring Alembic env.py...")
env_py_path = alembic_dir_path / "env.py"
if not env_py_path.exists():
    raise FileNotFoundError(f"Alembic env.py not found at {env_py_path} after init.")
env_py_content = env_py_path.read_text()

# Import DATABASE_URL from our config module
# This needs to be done carefully, ensuring poetry run context or sys.path is set
# For the script itself, sys.path is already set at the beginning.
from trading_system.core.config import DATABASE_URL

# Construct the new env.py content based on simplified logic
lines = env_py_content.splitlines()
new_env_lines = []
imports_added = False
target_metadata_definition_updated = False # Renamed from target_metadata_line_found_and_replaced

for line in lines:
    if "from logging.config import fileConfig" in line and not imports_added:
        new_env_lines.append(line)
        new_env_lines.append("import sys")
        new_env_lines.append("from pathlib import Path")
        new_env_lines.append(f"sys.path.append(str(Path('{PROJECT_ROOT}').resolve()))") # PROJECT_ROOT is from setup_script
        new_env_lines.append("from trading_system.core.models import metadata_obj as target_metadata_imported")
        imports_added = True
        continue

    if "target_metadata = None" in line: # Usually global scope in env.py
        new_env_lines.append("target_metadata = target_metadata_imported")
        target_metadata_definition_updated = True
        continue

    # Remove default sqlalchemy.url from env.py if it exists (main one is in alembic.ini)
    if line.strip() == "sqlalchemy.url = driver://user:pass@localhost/dbname":
        new_env_lines.append(f"# {line.strip()} (NOTE: This should be set in alembic.ini)")
        continue

    new_env_lines.append(line)

if not imports_added:
    print("Warning: Could not find 'from logging.config import fileConfig' to anchor imports in env.py.")
if not target_metadata_definition_updated:
    print("Warning: 'target_metadata = None' not found in env.py, ensure target_metadata is correctly set for autogenerate.")

env_py_content_modified = "\n".join(new_env_lines)

# Since alembic.ini now has the correct URL, and target_metadata is globally set to target_metadata_imported,
# the default context.configure calls in env.py should largely work as is, provided they pick up target_metadata.
# We just need to ensure 'target_metadata=target_metadata' (or our imported one) is in the configure calls.

def ensure_target_metadata_in_configure(fn_def_str, current_env_content):
    fn_start_index = current_env_content.find(fn_def_str)
    if fn_start_index == -1: return current_env_content

    next_fn_def_index = current_env_content.find("def ", fn_start_index + len(fn_def_str))
    if next_fn_def_index == -1: next_fn_def_index = len(current_env_content)

    context_configure_call_idx = current_env_content.find("context.configure(", fn_start_index, next_fn_def_index)
    if context_configure_call_idx != -1:
        end_of_call_idx = current_env_content.find(")", context_configure_call_idx) + 1
        call_str = current_env_content[context_configure_call_idx:end_of_call_idx]

        # If target_metadata is not mentioned, add it.
        # It should use the globally set 'target_metadata' variable.
        if "target_metadata=" not in call_str:
            modified_call_str = call_str.replace("(", "(target_metadata=target_metadata, ", 1)
            current_env_content = current_env_content[:context_configure_call_idx] + modified_call_str + current_env_content[end_of_call_idx:]
    return current_env_content

env_py_content_modified = ensure_target_metadata_in_configure("def run_migrations_offline():", env_py_content_modified)
env_py_content_modified = ensure_target_metadata_in_configure("def run_migrations_online():", env_py_content_modified)

print(f"DEBUG: About to write to env_py_path: {env_py_path.resolve()}")
# print(f"DEBUG: Content to write to env.py:\n----\n{env_py_content_modified}\n----") # Too verbose for now
env_py_path.write_text(env_py_content_modified)
print(f"DEBUG: env.py write attempt finished.")
if env_py_path.exists():
    print(f"DEBUG: {env_py_path} exists after write.")
    # print(f"DEBUG: Content of {env_py_path} after write (read back):\n----\n{env_py_path.read_text()}\n----") # Too verbose
else:
    print(f"DEBUG: ERROR - {env_py_path} does NOT exist after write attempt.")

# This line was erroneously writing back the original content, it's now removed.
print("Alembic env.py configured.")

# 3. Create an initial Alembic migration
print("Generating initial Alembic migration for market_data table...")
# Ensure alembic.ini is used from current PROJECT_ROOT
alembic_cfg_path_str = str(PROJECT_ROOT / "alembic.ini")
revision_cmd = ["poetry", "run", "alembic", "-c", alembic_cfg_path_str, "revision", "-m", "create_market_data_table", "--autogenerate"]
rev_result = subprocess.run(revision_cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)

if rev_result.returncode != 0:
    print(f"Alembic revision command failed! Stdout: {rev_result.stdout}\nStderr: {rev_result.stderr}")
    # It's common for autogenerate to fail if env.py has issues or can't connect to DB/load metadata
    raise Exception(f"Alembic revision generation failed: {rev_result.stderr}")

if "Generating" not in rev_result.stdout and "Detected new table" not in rev_result.stdout : # Check if autogenerate found changes
    print(f"Warning: Alembic autogenerate did not detect changes or new tables. Stdout: {rev_result.stdout}\nStderr: {rev_result.stderr}")
    # Check if a file was created. If not, that's a failure.
    migration_files = list((PROJECT_ROOT / "alembic" / "versions").glob("*.py"))
    if not migration_files or all('empty message for' in mf.name for mf in migration_files): # crude check for empty/failed revision
        raise Exception(f"Alembic revision generation failed to produce a non-empty migration script. Output: {rev_result.stdout} {rev_result.stderr}")

print(f"Alembic revision stdout: {rev_result.stdout}")
if rev_result.stderr: print(f"Alembic revision stderr: {rev_result.stderr}")
print("Migration script generated.")


# 4. Create a script to run migrations
db_management_py_content = '''import subprocess
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
            if stdout: base_logger.info("Stdout:\\n" + stdout)
        else:
            base_logger.error("Error applying database migrations:")
            if stdout: base_logger.error("Stdout:\\n" + stdout)
            if stderr: base_logger.error("Stderr:\\n" + stderr)
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
'''
with open(PROJECT_ROOT / "trading_system/core/db_management.py", "w") as f:
    f.write(db_management_py_content)

print("Created SQLAlchemy model, set up Alembic, generated initial migration, and created db_management.py script.")

# 5. Attempt to run migrations as part of the subtask
print("Attempting to run migrations as part of the subtask...")
from trading_system.core.config import DATA_DIR # DATA_DIR uses PROJECT_ROOT from config.py
# Ensure DATA_DIR (e.g. /app/trading_system/data) exists
# This should be PROJECT_ROOT from config.py / "trading_system" / "data"
data_dir_to_create = PROJECT_ROOT / "trading_system" / "data"
data_dir_to_create.mkdir(parents=True, exist_ok=True)
print(f"Ensured DATA_DIR for database exists at {data_dir_to_create}")


run_script_path = str(PROJECT_ROOT / "trading_system" / "core" / "db_management.py")
# No need to chmod +x if we are running `python script.py`
completed_process = subprocess.run(
    ["poetry", "run", "python", run_script_path],
    capture_output=True, text=True, cwd=PROJECT_ROOT
)
if completed_process.returncode == 0:
    print("Migrations script ran successfully within subtask.")
    print("STDOUT:", completed_process.stdout)
else:
    print("Migrations script failed within subtask.")
    print("STDOUT:", completed_process.stdout)
    print("STDERR:", completed_process.stderr)
    history_result = subprocess.run(["poetry", "run", "alembic", "history"], capture_output=True, text=True, cwd=PROJECT_ROOT)
    print(f"Alembic history: {history_result.stdout}")
    raise Exception(f"Subtask: Migrations script failed during execution. Alembic stderr: {completed_process.stderr}")

print("Subtask completed successfully.")
