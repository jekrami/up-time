from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, MetaData, UniqueConstraint
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
