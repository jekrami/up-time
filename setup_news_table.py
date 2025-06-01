import os
import sys
import subprocess
from pathlib import Path

# Ensure project root is in path for imports
PROJECT_ROOT = Path.cwd()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 1. Define SQLAlchemy model for NewsArticle in trading_system/core/models.py
# Append the new model to the existing models.py file.
models_py_path = PROJECT_ROOT / "trading_system" / "core" / "models.py"
news_article_model_content = '''

class NewsArticle(Base):
    __tablename__ = "news_data"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    published_at = Column(DateTime, nullable=False, index=True)
    source_title = Column(String, nullable=False) # e.g., "CoinDesk"
    news_title = Column(String, nullable=False)
    url = Column(String, nullable=False, unique=True) # URL should be unique
    # Storing currencies as a JSON string or comma-separated string.
    # For SQLite, JSON type is available and can be queried.
    # from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON # if using SQLite specific JSON
    # For broader compatibility, String can be used and parsed by application.
    currencies = Column(String) # e.g., "BTC,ETH" or JSON string '["BTC", "ETH"]'

    # To store the original text, or a hash of it to detect duplicates if URL is not perfectly unique
    # across different fetches or slight modifications. A hash of title+url might be good.
    content_hash = Column(String, nullable=True, unique=True, index=True) # MD5 or SHA256 hash of key content

    # Optional fields from Cryptopanic
    domain = Column(String)
    slug = Column(String) # Cryptopanic's internal ID for the post
    votes_positive = Column(Integer, default=0)
    votes_negative = Column(Integer, default=0)
    votes_important = Column(Integer, default=0)
    # Add more fields as needed based on API response structure

    # Unique constraint on URL is often sufficient if URLs are canonical.
    # If not, content_hash (e.g., hash of title + first N chars of article) might be better.
    # For now, unique URL and unique content_hash are good.

    def __repr__(self):
        return f"<NewsArticle(title={self.news_title}, source={self.source_title}, published_at={self.published_at})>"
'''

# Check if model already exists to prevent duplication if script is re-run
# This is a simple check; more robust would be to parse the file content.
if models_py_path.exists():
    with open(models_py_path, "r") as f_read:
        existing_models_content = f_read.read()
    if "class NewsArticle(Base):" in existing_models_content:
        print(f"NewsArticle model already exists in {models_py_path}. Skipping append.")
    else:
        with open(models_py_path, "a") as f_append: # Append to existing models.py
            f_append.write(news_article_model_content)
        print(f"Appended NewsArticle model to {models_py_path}")
else:
    # This case should not happen if previous subtasks ran correctly
    print(f"Warning: {models_py_path} does not exist. Creating it with NewsArticle model.")
    core_dir = models_py_path.parent
    os.makedirs(core_dir, exist_ok=True)
    # Need to add Base definition if creating models.py from scratch here
    # For this subtask, assume models.py exists and has Base defined.
    # If models.py is missing, this script will likely fail later or produce incomplete models.py
    with open(models_py_path, "w") as f_write: # Create if not exists
        # This would need the initial MarketData model + Base definition too if models.py was missing
        # For now, this path assumes models.py is there from previous steps.
        # Simplified: just write the new model if file was missing (less robust)
        base_scaffold = '''from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, MetaData, UniqueConstraint
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

metadata_obj = MetaData()
Base = declarative_base(metadata=metadata_obj)
'''
        with open(models_py_path, "w") as f:
            f.write(base_scaffold + news_article_model_content) # This would overwrite existing if it was just created
        print(f"Created {models_py_path} with NewsArticle model (and basic Base).")


# 2. Alembic should pick up changes to target_metadata automatically.

# 3. Generate a new Alembic migration
print("Generating Alembic migration for news_data table...")
migration_message = "create_news_data_table"
alembic_cfg_path = str(PROJECT_ROOT / "alembic.ini")
rev_cmd = ["poetry", "run", "alembic", "-c", alembic_cfg_path, "revision", "-m", migration_message, "--autogenerate"]
rev_result = subprocess.run(rev_cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)

migration_generated_successfully = False
if rev_result.returncode == 0 and ("Generating" in rev_result.stdout or "done" in rev_result.stdout.lower()):
    # Check for actual file creation
    versions_dir = PROJECT_ROOT / "alembic" / "versions"
    # Check if any .py file contains the migration message in its name or content (more robust)
    migration_files = list(versions_dir.glob(f"*_{migration_message}.py"))
    if migration_files:
        print(f"Alembic revision stdout: {rev_result.stdout}")
        if rev_result.stderr: print(f"Alembic revision stderr (info): {rev_result.stderr}")
        print(f"Migration script {migration_files[0].name} for news_data table generated.")
        migration_generated_successfully = True
    else: # "Generating ... done" but no file with the message. Could be empty migration.
        if "INFO  [alembic.autogenerate.compare] No changes detected." in rev_result.stderr or \
           "INFO  [alembic.autogenerate.compare] No changes detected" in rev_result.stdout: # Check both
            print("Alembic autogenerate detected no changes. This might be okay if schema is already up-to-date.")
            # To be safe, we can proceed if no changes, means table might exist or model not picked up.
            # The later check for table existence will confirm.
            migration_generated_successfully = True # Treat as success for now
        else:
            print(f"Alembic revision command output (no file with message): {rev_result.stdout}")
            print(f"Alembic revision command stderr (no file with message): {rev_result.stderr}")
            raise Exception(f"Alembic revision generation reported success but no migration file found matching message: {migration_message}")
elif "INFO  [alembic.autogenerate.compare] No changes detected." in rev_result.stderr or \
     "INFO  [alembic.autogenerate.compare] No changes detected" in rev_result.stdout:
    print("Alembic autogenerate detected no changes. Assuming schema is up-to-date or model not picked up by current changes.")
    migration_generated_successfully = True # Treat as success for now
else: # Actual error
    print(f"Alembic revision command FAILED. Return code: {rev_result.returncode}")
    print(f"Stdout: {rev_result.stdout}")
    print(f"Stderr: {rev_result.stderr}")
    raise Exception(f"Alembic revision generation failed: {rev_result.stderr} {rev_result.stdout}")


# 4. Run the migration (only if a new migration was generated or if we assume it's okay)
if migration_generated_successfully: # This includes "no changes detected"
    print("Attempting to run migrations to create/update news_data table...")
    db_management_script_path = str(PROJECT_ROOT / "trading_system" / "core" / "db_management.py")
    completed_process = subprocess.run(
        ["poetry", "run", "python", db_management_script_path],
        capture_output=True, text=True, cwd=PROJECT_ROOT
    )

    print("STDOUT from db_management.py:", completed_process.stdout)
    if completed_process.stderr:
        print("STDERR from db_management.py:", completed_process.stderr)

    if completed_process.returncode == 0:
        print("Migrations (including news_data) ran successfully or no new migrations needed.")
        # Verify table creation
        from sqlalchemy import create_engine, inspect
        # Ensure config is loaded for DATABASE_URL, handle .env not found warning
        try:
            from trading_system.core.config import DATABASE_URL
            print(f"Imported DATABASE_URL: {DATABASE_URL} for verification.")
        except ImportError as e:
            print(f"Failed to import DATABASE_URL for verification: {e}")
            raise Exception("Subtask: Failed to import DATABASE_URL for table verification.")

        engine = create_engine(DATABASE_URL)
        inspector = inspect(engine)
        if 'news_data' in inspector.get_table_names():
            print("Verified: 'news_data' table exists in the database.")
        else:
            print("Error: 'news_data' table does NOT exist in the database after migration.")
            raise Exception("Subtask: 'news_data' table not created by migration.")
    else:
        print("Migrations script failed when creating news_data table.")
        raise Exception(f"Subtask: Migrations script failed. STDERR: {completed_process.stderr}")
else:
    print("Skipping migration run because Alembic revision generation did not indicate a new script was made.")


print("Subtask for creating news_data table schema completed successfully.")
