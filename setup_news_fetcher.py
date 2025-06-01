import os
import sys
import subprocess
from pathlib import Path

# Ensure project root is in path for imports
PROJECT_ROOT = Path.cwd()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Content for trading_system/data_ingestion/news_fetcher.py
# Using a raw string literal r'''...''' for the Python code block
# to minimize issues with backslashes and special characters.
news_fetcher_py_content = r'''import os
import sys
import requests
import hashlib
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pathlib import Path # Added for SCRIPT_DIR

# Adjust path for direct script run or module import
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT_FETCHER = SCRIPT_DIR.parent.parent
if str(PROJECT_ROOT_FETCHER) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FETCHER))

from trading_system.core.models import NewsArticle
from trading_system.core.config import DATABASE_URL, CRYPTOPANIC_API_KEY
from trading_system.core.logger import base_logger

CRYPTOPANIC_BASE_URL = "https://cryptopanic.com/api/v1/posts/"

def calculate_content_hash(title, url):
    if not title or not url:
        return None
    hasher = hashlib.sha256()
    hasher.update(title.encode('utf-8'))
    hasher.update(url.encode('utf-8'))
    return hasher.hexdigest()

def fetch_cryptopanic_news(api_key, currencies=None, page=1): # page param is not used by cryptopanic for this listing
    if not api_key:
        base_logger.error("Cryptopanic API key is not configured.")
        return None

    params = {"auth_token": api_key, "public": "true"}
    if currencies:
        params["currencies"] = ",".join(currencies)

    base_logger.info(f"Fetching news from Cryptopanic. Currencies: {currencies if currencies else 'all'}")
    try:
        # Cryptopanic API might return a 401 if the key is invalid/dummy, even if it's present.
        response = requests.get(CRYPTOPANIC_BASE_URL, params=params, timeout=15)
        if response.status_code == 401: # Unauthorized
             base_logger.error(f"Cryptopanic API request failed with 401 Unauthorized. API Key: '{api_key[:10]}...' might be invalid or have insufficient permissions.")
             return None
        response.raise_for_status() # Raises HTTPError for bad responses (4XX or 5XX)
        data = response.json()
        base_logger.info(f"Fetched {len(data.get('results', []))} news items.")
        return data.get("results", [])
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 400 and "auth_token" in http_err.response.text:
             base_logger.error(f"Cryptopanic API request failed with 400 Bad Request, likely an issue with the API Key (e.g., 'auth_token parameter is missing'). API Key: '{api_key[:10]}...'. Response: {http_err.response.text}")
        else:
            base_logger.error(f"HTTP error fetching news: {http_err} - {http_err.response.text}", exc_info=True)
        return None
    except requests.exceptions.RequestException as e:
        base_logger.error(f"Request error fetching news: {e}", exc_info=True)
        return None
    except ValueError as e: # Includes JSONDecodeError
        base_logger.error(f"Error decoding JSON response from Cryptopanic: {e}", exc_info=True)
        return None

def store_news_articles(news_items):
    if not news_items: # news_items can be None if fetching failed, or empty list
        base_logger.info("No news items provided to store_news_articles.")
        return 0, 0

    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_session: Session = SessionLocal()
    inserted_count, skipped_count = 0, 0

    for item in news_items:
        news_url = item.get("url")
        news_title = item.get("title")
        if not news_url or not news_title:
            base_logger.warning(f"Skipping item due to missing URL or title: {item}")
            skipped_count +=1
            continue

        # Check 1: Existing URL
        if db_session.query(NewsArticle.id).filter_by(url=news_url).scalar() is not None:
            skipped_count += 1
            continue

        # Check 2: Existing Content Hash
        item_hash = calculate_content_hash(news_title, news_url)
        if item_hash and db_session.query(NewsArticle.id).filter_by(content_hash=item_hash).scalar() is not None:
            skipped_count += 1
            continue

        try:
            published_dt_str = item.get("published_at")
            # Ensure timestamp is timezone-aware (UTC)
            published_dt = datetime.fromisoformat(published_dt_str.replace("Z", "+00:00")) if published_dt_str else datetime.now(timezone.utc)

            currencies_list = item.get("currencies", []) # This is a list of dicts
            currency_codes = []
            if currencies_list: # Check if None or empty
                for curr_dict in currencies_list:
                    if isinstance(curr_dict, dict) and curr_dict.get("code"):
                        currency_codes.append(curr_dict.get("code"))

            source_obj = item.get("source", {}) # source is a dict
            news_article = NewsArticle(
                published_at=published_dt,
                source_title=source_obj.get("title", "N/A"), # Default if source or title is missing
                news_title=news_title,
                url=news_url,
                currencies=",".join(currency_codes) if currency_codes else None,
                content_hash=item_hash,
                domain=source_obj.get("domain"), # Can be None
                slug=item.get("slug"), # Can be None
                votes_positive=item.get("votes", {}).get("positive", 0), # votes is a dict
                votes_negative=item.get("votes", {}).get("negative", 0),
                votes_important=item.get("votes", {}).get("important", 0)
            )
            db_session.add(news_article)
            db_session.commit()
            inserted_count += 1
        except Exception as e:
            db_session.rollback()
            skipped_count += 1
            base_logger.error(f"Error storing article '{news_title}': {e}", exc_info=False)

    db_session.close()
    base_logger.info(f"News storing: Inserted {inserted_count}, Skipped {skipped_count} (includes duplicates or items with missing data).")
    return inserted_count, skipped_count

def main_fetch_and_store(currencies=None):
    base_logger.info("News fetcher process started.")
    # Load API key from config (which loads from .env)
    api_key_to_use = CRYPTOPANIC_API_KEY

    if not api_key_to_use or api_key_to_use in ["YOUR_CRYPTOPANIC_API_KEY_HERE", "dummy_key_for_now"]:
        # Fallback: try to get from actual environment variable if config one is placeholder
        env_var_key = os.getenv("CRYPTOPANIC_API_KEY_ACTUAL") # Use a different name to avoid clash with .env var
        if env_var_key and env_var_key not in ["YOUR_CRYPTOPANIC_API_KEY_HERE", "dummy_key_for_now"]:
            api_key_to_use = env_var_key
            base_logger.info("Using CRYPTOPANIC_API_KEY_ACTUAL from environment variable.")
        else:
            base_logger.error("CRYPTOPANIC_API_KEY is not properly configured (e.g., it's a placeholder). Please set it in .env or as CRYPTOPANIC_API_KEY_ACTUAL environment variable.")
            # Print to stdout as well, because logs might not be immediately visible to user running script
            print("Error: CRYPTOPANIC_API_KEY not properly configured. News fetching aborted. Check logs for details.", file=sys.stderr)
            return

    news_items = fetch_cryptopanic_news(api_key=api_key_to_use, currencies=currencies)

    if news_items is not None: # news_items can be an empty list (successful fetch, no news) or None (fetch failed)
        inserted, skipped = store_news_articles(news_items)
        base_logger.info(f"News fetcher process finished. Inserted: {inserted}, Skipped: {skipped}.")
    else:
        base_logger.warning("No news items were fetched or an error occurred during fetching.")

if __name__ == "__main__":
    # Example: Fetch news for BTC and ETH by default if script is run directly.
    main_fetch_and_store(currencies=["BTC", "ETH"])
'''

# Write the script content to file
fetcher_script_path = PROJECT_ROOT / "trading_system" / "data_ingestion" / "news_fetcher.py"
os.makedirs(fetcher_script_path.parent, exist_ok=True)
with open(fetcher_script_path, "w") as f:
    f.write(news_fetcher_py_content)
# Ensure __init__.py exists for the data_ingestion package
Path(fetcher_script_path.parent / "__init__.py").touch()

print(f"Created news fetcher script at: {fetcher_script_path}")

# Test run the script
print("Attempting to run the news fetcher script...")
# We expect this to fail or do nothing if API key is dummy, which is correct for this test.
completed_process = subprocess.run(
    ["poetry", "run", "python", str(fetcher_script_path)],
    capture_output=True, text=True, cwd=PROJECT_ROOT
)

# Print STDOUT and STDERR regardless of return code for debugging
print("News Fetcher STDOUT:", completed_process.stdout)
print("News Fetcher STDERR:", completed_process.stderr) # Script prints API key error to stderr

# Check if the script indicated an API key issue, or if it failed for other reasons.
# The script now prints the API key error to stderr.
if "CRYPTOPANIC_API_KEY not properly configured" in completed_process.stderr:
    print("News fetcher script correctly handled missing/dummy API key and printed error to stderr.")
elif completed_process.returncode != 0:
    print(f"News fetcher script failed with return code {completed_process.returncode}.")
    raise Exception(f"Subtask: News fetcher script encountered an error. STDERR: {completed_process.stderr}")
else:
    # This case means the script ran with returncode 0.
    # It might happen if the dummy API key, by some chance, doesn't cause an immediate error
    # at the requests level but returns empty data or an error handled by the script.
    print("News fetcher script ran with return code 0. Check application logs for details of fetching/storing (likely no data with dummy key).")

print("Subtask for news fetcher script completed.")
