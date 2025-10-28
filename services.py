"""
Business logic for fetching, processing, and storing country data.
"""

import httpx
import random
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from fastapi import HTTPException

from models import CountryDB
from config import settings


# ============= External API Functions =============

async def fetch_countries_data() -> List[Dict]:
    """Fetch country data from REST Countries API."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:  # Reduced from 30
            response = await client.get(settings.COUNTRIES_API_URL)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "External data source unavailable",
                "details": "Could not fetch data from REST Countries API - timeout"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "External data source unavailable",
                "details": f"Could not fetch data from REST Countries API: {str(e)}"
            }
        )


async def fetch_exchange_rates() -> Dict[str, float]:
    """Fetch exchange rates from Exchange Rate API."""
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:  # Reduced from 30
            response = await client.get(settings.EXCHANGE_RATE_API_URL)
            response.raise_for_status()
            data = response.json()
            return data.get("rates", {})
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "External data source unavailable",
                "details": "Could not fetch data from Exchange Rate API - timeout"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "External data source unavailable",
                "details": f"Could not fetch data from Exchange Rate API: {str(e)}"
            }
        )


# ============= Data Processing Functions =============

def extract_currency_code(currencies: List[Dict]) -> Optional[str]:
    """
    Extract first currency code from currencies array.
    
    Args:
        currencies: List of currency dictionaries
        
    Returns:
        First currency code or None if empty
    """
    if not currencies or len(currencies) == 0:
        return None
    
    first_currency = currencies[0]
    return first_currency.get("code")


def calculate_estimated_gdp(population: int, exchange_rate: Optional[float]) -> Optional[float]:
    """
    Calculate estimated GDP using formula:
    population × random(1000-2000) ÷ exchange_rate
    
    Args:
        population: Country population
        exchange_rate: Currency exchange rate
        
    Returns:
        Estimated GDP or None if exchange_rate is None
    """
    if exchange_rate is None or exchange_rate == 0:
        return None
    
    multiplier = random.uniform(1000, 2000)
    return (population * multiplier) / exchange_rate


def process_country_data(
    country: Dict,
    exchange_rates: Dict[str, float]
) -> Dict:
    """
    Process raw country data and combine with exchange rate.
    
    Args:
        country: Raw country data from API
        exchange_rates: Dictionary of currency rates
        
    Returns:
        Processed country data ready for database
    """
    # Extract basic fields
    name = country.get("name")
    capital = country.get("capital")
    region = country.get("region")
    population = country.get("population", 0)
    flag_url = country.get("flag")
    currencies = country.get("currencies", [])
    
    # Extract currency code
    currency_code = extract_currency_code(currencies)
    
    # Get exchange rate
    exchange_rate = None
    if currency_code:
        exchange_rate = exchange_rates.get(currency_code)
    
    # Calculate GDP
    estimated_gdp = calculate_estimated_gdp(population, exchange_rate)
    
    return {
        "name": name,
        "capital": capital,
        "region": region,
        "population": population,
        "currency_code": currency_code,
        "exchange_rate": exchange_rate,
        "estimated_gdp": estimated_gdp,
        "flag_url": flag_url
    }


# ============= Database Operations =============

def upsert_country(db: Session, country_data: Dict) -> CountryDB:
    """
    Insert or update country in database.
    Matches by name (case-insensitive).
    
    Args:
        db: Database session
        country_data: Processed country data
        
    Returns:
        CountryDB instance
    """
    # Check if country exists (case-insensitive)
    existing = db.query(CountryDB).filter(
        func.lower(CountryDB.name) == func.lower(country_data["name"])
    ).first()
    
    if existing:
        # Update existing country
        for key, value in country_data.items():
            setattr(existing, key, value)
        existing.last_refreshed_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    else:
        # Insert new country
        new_country = CountryDB(**country_data)
        db.add(new_country)
        db.commit()
        db.refresh(new_country)
        return new_country


def get_all_countries(
    db: Session,
    region: Optional[str] = None,
    currency: Optional[str] = None,
    sort: Optional[str] = None
) -> List[CountryDB]:
    """Get all countries with optional filtering and sorting."""
    query = db.query(CountryDB)
    
    # Apply filters
    if region:
        query = query.filter(func.lower(CountryDB.region) == func.lower(region))
    
    if currency:
        query = query.filter(func.lower(CountryDB.currency_code) == func.lower(currency))
    
    # Apply sorting - FIX: Handle None values properly
    if sort:
        if sort == "gdp_desc":
            # Put nulls last, then sort descending
            query = query.order_by(
                CountryDB.estimated_gdp.desc().nullslast()
            )
        elif sort == "gdp_asc":
            # Put nulls first, then sort ascending
            query = query.order_by(
                CountryDB.estimated_gdp.asc().nullsfirst()
            )
        elif sort == "population_desc":
            query = query.order_by(CountryDB.population.desc())
        elif sort == "population_asc":
            query = query.order_by(CountryDB.population.asc())
        elif sort == "name_asc":
            query = query.order_by(CountryDB.name.asc())
        elif sort == "name_desc":
            query = query.order_by(CountryDB.name.desc())
        else:
            # Default: no invalid sort parameter error
            pass
    
    return query.all()


def get_country_by_name(db: Session, name: str) -> Optional[CountryDB]:
    """
    Get country by name (case-insensitive).
    
    Args:
        db: Database session
        name: Country name
        
    Returns:
        CountryDB instance or None
    """
    return db.query(CountryDB).filter(
        func.lower(CountryDB.name) == func.lower(name)
    ).first()


def delete_country_by_name(db: Session, name: str) -> bool:
    """
    Delete country by name (case-insensitive).
    
    Args:
        db: Database session
        name: Country name
        
    Returns:
        True if deleted, False if not found
    """
    country = get_country_by_name(db, name)
    if country:
        db.delete(country)
        db.commit()
        return True
    return False


def get_database_status(db: Session) -> Tuple[int, Optional[datetime]]:
    """
    Get total countries and last refresh timestamp.
    
    Args:
        db: Database session
        
    Returns:
        Tuple of (total_countries, last_refreshed_at)
    """
    total = db.query(func.count(CountryDB.id)).scalar()
    last_refresh = db.query(func.max(CountryDB.last_refreshed_at)).scalar()
    return total, last_refresh


def get_top_countries_by_gdp(db: Session, limit: int = 5) -> List[CountryDB]:
    """
    Get top countries by estimated GDP.
    
    Args:
        db: Database session
        limit: Number of countries to return
        
    Returns:
        List of top CountryDB instances
    """
    return db.query(CountryDB).filter(
        CountryDB.estimated_gdp.isnot(None)
    ).order_by(
        CountryDB.estimated_gdp.desc()
    ).limit(limit).all()