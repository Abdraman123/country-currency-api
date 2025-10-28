"""
Configuration management for the application.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://hng_user:password@localhost:3306/country_currency"
    )
    
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8080"))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    
    # External APIs
    COUNTRIES_API_URL: str = os.getenv(
        "COUNTRIES_API_URL",
        "https://restcountries.com/v2/all?fields=name,capital,region,population,flag,currencies"
    )
    EXCHANGE_RATE_API_URL: str = os.getenv(
        "EXCHANGE_RATE_API_URL",
        "https://open.er-api.com/v6/latest/USD"
    )

    # Image Cache (works both locally and on DigitalOcean)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # If running on DigitalOcean (detected by environment variable)
    if os.getenv("DYNO") or os.getenv("PORT"):  
        IMAGE_CACHE_DIR = "/tmp/cache"
    else:
        IMAGE_CACHE_DIR = os.path.join(BASE_DIR, "cache")

    IMAGE_FILE_NAME: str = "summary.png"
    IMAGE_PATH: str = os.path.join(IMAGE_CACHE_DIR, IMAGE_FILE_NAME)

    # App Metadata
    APP_NAME: str = "Country Currency API"
    APP_VERSION: str = "1.0.0"


settings = Settings()

# ✅ Create cache directory if it doesn't exist
os.makedirs(settings.IMAGE_CACHE_DIR, exist_ok=True)


def validate_settings():
    """Validate required settings."""
    if "password" in settings.DATABASE_URL:
        print("\n⚠️  WARNING: Using default database password!")
        print("Please update DATABASE_URL in .env file\n")


validate_settings()
