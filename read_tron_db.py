import argparse
import rocksdict
from core.Tron_pb2 import Account
import base58
import sqlite3
import sys

def setup_database(db_file):
    """Sets up the SQLite database and creates the accounts table."""
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            address TEXT PRIMARY KEY,
            trx_balance REAL
        )
    ''')
    conn.commit()
    return conn

def main():
    parser = argparse.ArgumentParser(description='Read account data from a Tron RocksDB database and export to SQLite.')
    parser.add_argument('db_path', type=str, help='Path to the Tron RocksDB database directory.')
    parser.add_argument('--db-file', type=str, default='tron_balances.db', help='Path to the SQLite database file.')
    parser.add_argument('--min-balance', type=float, default=0, help='Minimum TRX balance to export.')
    args = parser.parse_args()

    try:
        db = rocksdict.Rdict(args.db_path, options=rocksdict.Options(raw_mode=True))
    except Exception as e:
        print(f"Error opening RocksDB database: {e}")
        return

    try:
        cf_names = rocksdict.Rdict.list_cf(args.db_path)
        account_cf_name = None
        if 'account' in cf_names:
            account_cf_name = 'account'
        elif 'default' in cf_names:
            account_cf_name = 'default'
        else:
            print("Error: Could not find 'account' or 'default' column family.")
            print(f"Available column families: {cf_names}")
            db.close()
            return
        account_cf = db.get_column_family(account_cf_name)
        print(f"Using column family: '{account_cf_name}'")
    except Exception as e:
        print(f"Error accessing column family: {e}")
        db.close()
        return

    conn = setup_database(args.db_file)
    c = conn.cursor()

    count = 0
    exported_count = 0
    # Iterate over the key-value pairs in the account column family.
    for key, value in account_cf.items():
        count += 1
        if count % 100000 == 0:
            sys.stdout.write(f"\rProcessed {count} accounts...")
            sys.stdout.flush()

        try:
            account = Account()
            account.ParseFromString(value)

            balance_sun = account.balance
            balance_trx = balance_sun / 1_000_000

            if balance_trx >= args.min_balance:
                address_b58 = base58.b58encode_check(key).decode('utf-8')

                c.execute("INSERT OR REPLACE INTO accounts (address, trx_balance) VALUES (?, ?)",
                          (address_b58, balance_trx))
                exported_count += 1

        except Exception:
            pass

    conn.commit()
    conn.close()
    db.close()

    print(f"\nDone. Processed {count} accounts and exported {exported_count} to '{args.db_file}'.")

if __name__ == '__main__':
    main()
