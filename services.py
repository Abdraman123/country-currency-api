import httpx
import random
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Country, RefreshMetadata
from fastapi import HTTPException

COUNTRIES_API = "https://restcountries.com/v2/all?fields=name,capital,region,population,flag,currencies"
EXCHANGE_API = "https://open.er-api.com/v6/latest/USD"

async def fetch_countries_data():
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(COUNTRIES_API)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "External data source unavailable",
                "details": f"Could not fetch data from restcountries.com: {str(e)}"
            }
        )

async def fetch_exchange_rates():
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(EXCHANGE_API)
            response.raise_for_status()
            data = response.json()
            return data.get("rates", {})
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "External data source unavailable",
                "details": f"Could not fetch data from open.er-api.com: {str(e)}"
            }
        )

def calculate_gdp(population: int, exchange_rate: float = None) -> float:
    if exchange_rate is None or exchange_rate == 0:
        return None
    random_multiplier = random.uniform(1000, 2000)
    return (population * random_multiplier) / exchange_rate

def refresh_countries(db: Session, countries_data: list, exchange_rates: dict):
    for country_data in countries_data:
        name = country_data.get("name")
        if not name:
            continue
        
        capital = country_data.get("capital")
        region = country_data.get("region")
        population = country_data.get("population", 0)
        flag_url = country_data.get("flag")
        
        currencies = country_data.get("currencies", [])
        currency_code = None
        exchange_rate = None
        estimated_gdp = 0
        
        if currencies and len(currencies) > 0:
            currency_code = currencies[0].get("code")
            if currency_code and currency_code in exchange_rates:
                exchange_rate = exchange_rates[currency_code]
                estimated_gdp = calculate_gdp(population, exchange_rate)
            else:
                exchange_rate = None
                estimated_gdp = None
        
        existing_country = db.query(Country).filter(
            func.lower(Country.name) == func.lower(name)
        ).first()
        
        if existing_country:
            existing_country.capital = capital
            existing_country.region = region
            existing_country.population = population
            existing_country.currency_code = currency_code
            existing_country.exchange_rate = exchange_rate
            existing_country.estimated_gdp = estimated_gdp
            existing_country.flag_url = flag_url
            existing_country.last_refreshed_at = datetime.utcnow()
        else:
            new_country = Country(
                name=name,
                capital=capital,
                region=region,
                population=population,
                currency_code=currency_code,
                exchange_rate=exchange_rate,
                estimated_gdp=estimated_gdp,
                flag_url=flag_url
            )
            db.add(new_country)
    
    db.commit()
    
    metadata = db.query(RefreshMetadata).first()
    if metadata:
        metadata.last_refreshed_at = datetime.utcnow()
    else:
        metadata = RefreshMetadata()
        db.add(metadata)
    db.commit()

def get_all_countries(db: Session, region: str = None, currency: str = None, sort: str = None):
    query = db.query(Country)
    
    if region:
        query = query.filter(func.lower(Country.region) == func.lower(region))
    
    if currency:
        query = query.filter(func.lower(Country.currency_code) == func.lower(currency))
    
    if sort == "gdp_desc":
        query = query.order_by(Country.estimated_gdp.desc().nullslast())
    elif sort == "gdp_asc":
        query = query.order_by(Country.estimated_gdp.asc().nullslast())
    elif sort == "name_asc":
        query = query.order_by(Country.name.asc())
    elif sort == "name_desc":
        query = query.order_by(Country.name.desc())
    
    return query.all()

def get_country_by_name(db: Session, name: str):
    return db.query(Country).filter(func.lower(Country.name) == func.lower(name)).first()

def delete_country_by_name(db: Session, name: str):
    country = db.query(Country).filter(func.lower(Country.name) == func.lower(name)).first()
    if country:
        db.delete(country)
        db.commit()
        return True
    return False

def get_status(db: Session):
    total = db.query(Country).count()
    metadata = db.query(RefreshMetadata).first()
    last_refreshed = metadata.last_refreshed_at if metadata else None
    
    return {
        "total_countries": total,
        "last_refreshed_at": last_refreshed.isoformat() if last_refreshed else None
    }