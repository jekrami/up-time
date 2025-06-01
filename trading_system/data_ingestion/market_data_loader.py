import os
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
    filename_pattern = re.compile(r"([A-Z0-9\-]+?)-5\.csv", re.IGNORECASE)


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
