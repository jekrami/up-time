# Tron DB Reader

This script reads a Tron RocksDB database and exports the addresses and TRX balances of all accounts to a SQLite database.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine.

### Prerequisites

*   Python 3.8+
*   A copy of the Tron `output-directory` database. This is the directory that a Tron node uses to store its data.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Usage

To use the script, run it from the command line and provide the path to your Tron database directory.

```bash
python read_tron_db.py /path/to/your/tron/output-directory
```

You can also specify the output SQLite database file and a minimum TRX balance to export.

### Options

*   `--db-file`: Path to the output SQLite database file. Defaults to `tron_balances.db`.
*   `--min-balance`: The minimum TRX balance to export. Accounts with a balance lower than this will be skipped. Defaults to 0.

### Example

```bash
# Export all accounts to the default tron_balances.db
python read_tron_db.py /data/tron/output-directory

# Export accounts with a balance of at least 100 TRX to a custom database file
python read_tron_db.py /data/tron/output-directory --min-balance 100 --db-file my_tron_data.db
```

## How it works

The script uses the `rocksdict` library to read the RocksDB database. It checks for a column family named `account`, and if that is not found, it falls back to `default`. This is because the name of the column family containing account data can vary between different Tron node setups.

The values in the `account` column family are serialized using Google Protocol Buffers (Protobuf). The script uses the `.proto` files from the `java-tron` repository to generate Python classes that can parse this data.

The script iterates through all the key-value pairs in the `account` column family, decodes the data, and saves the address and TRX balance to a SQLite database. The addresses are converted to the standard base58 format for readability.
