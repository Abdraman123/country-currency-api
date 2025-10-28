"""
Main FastAPI application - CORRECTED VERSION
"""

from fastapi import FastAPI, HTTPException, Depends, Query, status
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
import asyncio

from database import engine, get_db, Base
from models import CountryDB, CountryResponse, StatusResponse, RefreshResponse
from services import (
    fetch_countries_data, fetch_exchange_rates, process_country_data,
    upsert_country, get_all_countries, get_country_by_name,
    delete_country_by_name, get_database_status, get_top_countries_by_gdp
)
from image_generator import generate_summary_image, get_image_path
from config import settings

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="RESTful API for country data"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ROOT
@app.get("/")
def root():
    return {
        "message": "Country Currency API",
        "version": "1.0.0",
        "docs": "/docs"
    }


# STATUS - different path, no conflict
@app.get("/status", response_model=StatusResponse)
def get_status(db: Session = Depends(get_db)):
    total, last_refresh = get_database_status(db)
    return StatusResponse(total_countries=total, last_refreshed_at=last_refresh)


# REFRESH - BEFORE /{name}
@app.post("/countries/refresh", response_model=RefreshResponse)
async def refresh_countries(db: Session = Depends(get_db)):
    try:
        countries_data, exchange_rates = await asyncio.gather(
            fetch_countries_data(),
            fetch_exchange_rates()
        )
        
        countries_processed = 0
        for country in countries_data:  # ALL countries, no limit
            try:
                processed_data = process_country_data(country, exchange_rates)
                upsert_country(db, processed_data)
                countries_processed += 1
            except Exception as e:
                print(f"Error: {e}")
                continue
        
        try:
            total, last_refresh = get_database_status(db)
            top_countries = get_top_countries_by_gdp(db, limit=5)
            if top_countries:
                generate_summary_image(total, top_countries, last_refresh or datetime.utcnow())
        except Exception as e:
            print(f"Image error: {e}")
        
        return RefreshResponse(
            message="Countries refreshed",
            countries_processed=countries_processed,
            timestamp=datetime.utcnow()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "Internal error", "details": str(e)})


# IMAGE - BEFORE /{name}
@app.get("/countries/image")
def get_summary_image():
    image_path = get_image_path()
    if not image_path:
        raise HTTPException(status_code=404, detail={"error": "Summary image not found"})
    return FileResponse(image_path, media_type="image/png", filename=settings.IMAGE_FILE_NAME)


# GET ALL - BEFORE /{name}
@app.get("/countries", response_model=List[CountryResponse])
def get_countries(
    region: Optional[str] = Query(None),
    currency: Optional[str] = Query(None),
    sort: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    countries = get_all_countries(db=db, region=region, currency=currency, sort=sort)
    return [CountryResponse.from_orm(c) for c in countries]


# DELETE - can be anywhere
@app.delete("/countries/{name}", status_code=204)
def delete_country(name: str, db: Session = Depends(get_db)):
    deleted = delete_country_by_name(db, name)
    if not deleted:
        raise HTTPException(status_code=404, detail={"error": "Country not found"})
    return None


# GET ONE - MUST BE LAST
@app.get("/countries/{name}", response_model=CountryResponse)
def get_country(name: str, db: Session = Depends(get_db)):
    country = get_country_by_name(db, name)
    if not country:
        raise HTTPException(status_code=404, detail={"error": "Country not found"})
    return CountryResponse.from_orm(country)


if __name__ == "__main__":
    import uvicorn, os
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)