import argparse
import rocksdict
from core.Tron_pb2 import Account
import base58

def main():
    parser = argparse.ArgumentParser(description='Read account data from a Tron RocksDB database.')
    parser.add_argument('db_path', type=str, help='Path to the Tron RocksDB database directory.')
    args = parser.parse_args()

    try:
        # Open the database in read-only mode.
        # raw_mode=True is important because the data is not encoded by rocksdict.
        db = rocksdict.Rdict(args.db_path, options=rocksdict.Options(raw_mode=True))
    except Exception as e:
        print(f"Error opening database: {e}")
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

    print("Address,Balance")
    # Iterate over the key-value pairs in the account column family.
    for key, value in account_cf.items():
        try:
            # The key is the account address in bytes.
            # The value is a serialized Account protobuf message.
            account = Account()
            account.ParseFromString(value)

            # The key from the database is the full 21-byte address.
            # We can directly encode it using base58check.
            address_b58 = base58.b58encode_check(key).decode('utf-8')

            # The balance is in SUN (1 TRX = 1,000,000 SUN).
            balance_sun = account.balance
            balance_trx = balance_sun / 1_000_000

            print(f"{address_b58},{balance_trx}")

        except Exception as e:
            # It's possible some entries are not valid accounts, so we'll just skip them.
            # print(f"Could not parse account with key {key.hex()}: {e}")
            pass

    # Clean up and close the database.
    db.close()

if __name__ == '__main__':
    main()
