# Tron DB Reader

This script reads a Tron RocksDB database and prints the addresses and balances of all accounts.

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

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

### Example

```bash
python read_tron_db.py /data/tron/output-directory
```

**Example Output:**

```
Address,Balance
T...some_address...,1234.5678
T...another_address...,9876.5432
...
```

## How it works

The script uses the `rocksdict` library to read the RocksDB database. It specifically looks for a column family named `account`, which is where Tron stores its account data.

The values in the `account` column family are serialized using Google Protocol Buffers (Protobuf). The script uses the `.proto` files from the `java-tron` repository to generate Python classes that can parse this data.

The script iterates through all the key-value pairs in the `account` column family, decodes the data, and prints the address and balance for each account. The addresses are converted to the standard base58 format for readability.
