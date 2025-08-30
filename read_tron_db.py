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
        # Get the 'account' column family. This is a common name for the account data.
        # If this fails, you may need to list the column families and find the correct one.
        cf_names = rocksdict.Rdict.list_cf(args.db_path)
        if 'account' not in cf_names:
            print("Error: 'account' column family not found.")
            print(f"Available column families: {cf_names}")
            return

        account_cf = db.get_column_family('account')
    except Exception as e:
        print(f"Error accessing 'account' column family: {e}")
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

            # The address is the key, let's encode it in base58.
            # Tron addresses have a prefix of 0x41.
            address_hex = b'\x41' + key
            address_b58 = base58.b58encode_check(address_hex).decode('utf-8')

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
