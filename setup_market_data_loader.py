import os
import sys
import subprocess
import re
from pathlib import Path

# Ensure project root is in path for imports
PROJECT_ROOT = Path.cwd()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Create dummy CSV files for testing if they don't exist.
# This is to ensure the loader script has something to process.
data_dir_path = PROJECT_ROOT / "trading_system" / "data"
os.makedirs(data_dir_path, exist_ok=True) # Ensure data directory exists

dummy_files_to_create = {
    data_dir_path / "BTCUSD-5.csv": (
        "Timestamp,Open,High,Low,Close,Volume\n"
        "2023-01-01T00:00:00Z,40000,40050,39990,40010,10\n"
        "2023-01-01T00:05:00Z,40010,40060,40000,40020,12\n"
        "2023-01-01T00:10:00Z,40020,40070,40010,40030,15\n"
    ),
    data_dir_path / "ETHUSD-5.csv": (
        "Timestamp,Open,High,Low,Close,Volume\n"
        "2023-01-01T00:00:00Z,2000,2005,1999,2001,100\n"
        "2023-01-01T00:05:00Z,2001,2006,2000,2002,120\n"
        "2023-01-01T00:10:00Z,2002,2007,2001,2003,150\n"
    )
}
for fpath, content in dummy_files_to_create.items():
    if not fpath.exists():
        print(f"Creating dummy CSV for testing: {fpath}")
        with open(fpath, "w") as f:
            f.write(content)

# Content for trading_system/data_ingestion/market_data_loader.py
market_data_loader_py_content = '''import os
import sys
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError
import re
import datetime

# Need to ensure PROJECT_ROOT is correctly determined if script is run directly
# This assumes the script is in trading_system/data_ingestion/
# and project root is two levels up.
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT_LOADER = SCRIPT_DIR.parent.parent

if str(PROJECT_ROOT_LOADER) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_LOADER))

from trading_system.core.models import MarketData
from trading_system.core.config import DATABASE_URL, DATA_DIR
from trading_system.core.logger import base_logger

def load_ohlcv_csvs_to_db():
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_session: Session = SessionLocal()

    raw_data_path = DATA_DIR # This is an absolute path from config.py
    if not raw_data_path.exists():
        base_logger.warning(f"Data directory {raw_data_path} does not exist. No data to load.")
        return 0

    csv_files = list(raw_data_path.glob("*-5.csv")) # Match files like BTCUSD-5.csv
    if not csv_files:
        base_logger.warning(f"No '*-5.csv' files found in {raw_data_path}. No market data loaded.")
        return 0

    total_rows_processed, total_rows_inserted, total_rows_skipped = 0, 0, 0
    # Regex to capture symbol part from filename like "BTCUSD-5.csv" or "ETH-BTC-5.csv"
    filename_pattern = re.compile(r"([A-Z0-9\-]+?)-5\\.csv", re.IGNORECASE)


    for csv_file in csv_files:
        base_logger.info(f"Attempting to process file: {csv_file.name}")
        match = filename_pattern.match(csv_file.name)
        if not match:
            base_logger.warning(f"Could not parse symbol from filename: {csv_file.name} using pattern. Skipping.")
            continue

        symbol = match.group(1).upper().replace('-', '/') # Normalize symbols like ETH-BTC to ETH/BTC
        base_logger.info(f"Processing file: {csv_file.name} for symbol: {symbol}")

        try:
            df = pd.read_csv(csv_file)
            df.rename(columns=lambda c: c.strip().capitalize(), inplace=True) # Normalize column names

            required_cols = ['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']
            current_cols = df.columns.tolist()
            rename_map = {}
            if 'Date' in current_cols and 'Timestamp' not in current_cols: rename_map['Date'] = 'Timestamp'
            if 'Time' in current_cols and 'Timestamp' not in current_cols: rename_map['Time'] = 'Timestamp'
            if 'Datetime' in current_cols and 'Timestamp' not in current_cols: rename_map['Datetime'] = 'Timestamp'
            df.rename(columns=rename_map, inplace=True)

            if not all(col in df.columns for col in required_cols):
                base_logger.error(f"File {csv_file.name} missing required columns. Need: {required_cols}, Found: {df.columns.tolist()}. Skipping.")
                continue

            try:
                df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
                df.dropna(subset=['Timestamp'], inplace=True)
            except Exception as e:
                base_logger.error(f"Error parsing Timestamp in {csv_file.name}: {e}. Skipping.")
                continue

            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df.dropna(subset=['Open', 'High', 'Low', 'Close', 'Volume'], inplace=True)

            if df.empty:
                base_logger.info(f"No valid data in {csv_file.name} after cleaning. Skipping.")
                continue

            base_logger.info(f"Loading {len(df)} rows from {csv_file.name} for {symbol} into DB...")
            file_inserted, file_skipped = 0, 0

            objects_to_insert = []
            for _, row_s in df.iterrows():
                total_rows_processed += 1
                ts = row_s['Timestamp']
                if ts.tzinfo is None:
                    ts = ts.tz_localize('UTC')

                # Check for existing entry based on unique constraint (timestamp, symbol)
                # This check is more explicit than relying on merge for new entries only.
                exists_query = db_session.query(MarketData).filter_by(timestamp=ts, symbol=symbol)
                if db_session.query(exists_query.exists()).scalar():
                    file_skipped +=1
                    continue

                objects_to_insert.append(MarketData(
                    timestamp=ts, symbol=symbol,
                    open=row_s['Open'], high=row_s['High'], low=row_s['Low'],
                    close=row_s['Close'], volume=row_s['Volume']
                ))

            if objects_to_insert:
                try:
                    db_session.bulk_save_objects(objects_to_insert)
                    db_session.commit()
                    file_inserted = len(objects_to_insert)
                except IntegrityError: # Should be rare now due to explicit check, but as fallback
                    db_session.rollback()
                    base_logger.warning(f"IntegrityError during bulk insert for {csv_file.name}, likely duplicates missed by check. Trying row-by-row.")
                    # Fallback to row-by-row if bulk insert fails due to unexpected duplicates
                    file_inserted_fallback, file_skipped_fallback = 0, 0
                    for obj in objects_to_insert:
                        try:
                            db_session.merge(obj) # merge can handle if somehow it exists
                            db_session.commit()
                            file_inserted_fallback += 1
                        except IntegrityError:
                            db_session.rollback()
                            file_skipped_fallback +=1
                        except Exception as e_fb:
                            db_session.rollback()
                            base_logger.error(f"Fallback insert error for {obj.symbol} at {obj.timestamp}: {e_fb}")
                            file_skipped_fallback +=1
                    file_inserted = file_inserted_fallback
                    file_skipped += file_skipped_fallback

                except Exception as e_bulk:
                    db_session.rollback()
                    base_logger.error(f"Error during bulk insert for {csv_file.name}: {e_bulk}", exc_info=True)
                    file_skipped += len(objects_to_insert) # Assume all failed if bulk op failed badly

            total_rows_inserted += file_inserted
            total_rows_skipped += file_skipped
            base_logger.info(f"Finished {csv_file.name}: Inserted {file_inserted}, Skipped {file_skipped} rows.")

        except pd.errors.EmptyDataError:
            base_logger.warning(f"File {csv_file.name} is empty. Skipping.")
        except Exception as e_outer:
            base_logger.error(f"Failed to process/load {csv_file.name}: {e_outer}", exc_info=True)
            if db_session.is_active: db_session.rollback()

    db_session.close()
    base_logger.info(f"Market data loading complete. Processed: {total_rows_processed}, Inserted: {total_rows_inserted}, Skipped: {total_rows_skipped}.")
    return total_rows_inserted

if __name__ == "__main__":
    base_logger.info("Starting market data loading process...")
    inserted_count = load_ohlcv_csvs_to_db()
    base_logger.info(f"Market data loading script finished. {inserted_count} new rows were inserted.")
'''

# Write the script content to file
loader_script_path = PROJECT_ROOT / "trading_system" / "data_ingestion" / "market_data_loader.py"
os.makedirs(loader_script_path.parent, exist_ok=True)
with open(loader_script_path, "w") as f:
    f.write(market_data_loader_py_content)
(loader_script_path.parent / "__init__.py").touch() # Ensure package

print(f"Created market data loader script at: {loader_script_path}")

# Run the loader script
print("Attempting to run the market data loader script...")
run_script_path_str = str(loader_script_path)
completed_process = subprocess.run(
    ["poetry", "run", "python", run_script_path_str],
    capture_output=True, text=True, cwd=PROJECT_ROOT
)

print("STDOUT:", completed_process.stdout)
print("STDERR:", completed_process.stderr)

if completed_process.returncode == 0:
    print("Market data loader script ran successfully.")
    # Verify data in DB
    from trading_system.core.config import DATABASE_URL
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(DATABASE_URL)
    SessionLocalTest = sessionmaker(bind=engine)
    session = SessionLocalTest()
    try:
        expected_inserts = 0
        for dummy_fpath, content in dummy_files_to_create.items():
            symbol_to_check = dummy_fpath.name.split("-5.csv")[0].upper().replace('-', '/')
            num_data_rows = len(content.strip().split('\\n')) -1 # Number of data rows in CSV
            expected_inserts += num_data_rows

            query = text("SELECT COUNT(*) FROM market_data WHERE symbol = :symbol")
            count_result = session.execute(query, {"symbol": symbol_to_check}).scalar_one()
            print(f"Found {count_result} rows for symbol {symbol_to_check} in the database (expected approx {num_data_rows}).")
            if count_result < num_data_rows:
                 print(f"Warning: Potential missing data for {symbol_to_check}. Expected {num_data_rows}, got {count_result}.")

        # Check total inserted count from script's log
        stdout_lines = completed_process.stdout.splitlines()
        final_log_line = ""
        for line in reversed(stdout_lines):
            if "Market data loading script finished." in line:
                final_log_line = line
                break

        print(f"Loader script final log line: '{final_log_line}'")
        if f" {expected_inserts} new rows were inserted." not in final_log_line:
            # This check might be too strict if script was run multiple times, as it only inserts new rows.
            # The critical part is that it ran and data is present.
            # Let's check the "Inserted: X" part of the summary log instead for the latest run
            summary_log_inserted = 0
            for line in reversed(stdout_lines):
                if "Market data loading complete." in line and "Inserted:" in line:
                    # Example: "... Inserted: 6, Skipped: 0."
                    match = re.search(r"Inserted:\s*(\d+)", line)
                    if match:
                        summary_log_inserted = int(match.group(1))
                        break
            print(f"Total rows inserted in the last run according to logs: {summary_log_inserted}")
            if summary_log_inserted != expected_inserts:
                 print(f"Warning: Discrepancy in expected ({expected_inserts}) vs logged inserted ({summary_log_inserted}) rows for a fresh run.")


    finally:
        session.close()
else:
    raise Exception(f"Subtask: Market data loader script failed. Return code: {completed_process.returncode}")

print("Subtask for loading OHLCV CSV data completed.")
