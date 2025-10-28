"""
Main FastAPI application with all endpoints.
"""

from fastapi import FastAPI, HTTPException, Depends, Query, status
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
import asyncio

from database import engine, get_db, Base
from models import (
    CountryDB,
    CountryResponse,
    StatusResponse,
    RefreshResponse
)
from services import (
    fetch_countries_data,
    fetch_exchange_rates,
    process_country_data,
    upsert_country,
    get_all_countries,
    get_country_by_name,
    delete_country_by_name,
    get_database_status,
    get_top_countries_by_gdp
)
from image_generator import generate_summary_image, get_image_path
from config import settings

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="RESTful API for country data, currencies, and exchange rates"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "endpoints": {
            "POST /countries/refresh": "Fetch and cache country data",
            "GET /countries": "Get all countries",
            "GET /countries/image": "Get summary image",
            "GET /countries/{name}": "Get specific country",
            "DELETE /countries/{name}": "Delete a country",
            "GET /status": "Get status",
            "/docs": "API documentation"
        }
    }


@app.get("/status", response_model=StatusResponse)
def get_status(db: Session = Depends(get_db)):
    """Get total countries and last refresh timestamp."""
    total, last_refresh = get_database_status(db)
    return StatusResponse(
        total_countries=total,
        last_refreshed_at=last_refresh
    )


@app.post("/countries/refresh", response_model=RefreshResponse)
async def refresh_countries(db: Session = Depends(get_db)):
    """Fetch and cache country data."""
    try:
        # Fetch data with strict timeout
        countries_data, exchange_rates = await asyncio.gather(
            fetch_countries_data(),
            fetch_exchange_rates()
        )
        
        # Process all countries
        countries_processed = 0
        for country in countries_data:
            try:
                processed_data = process_country_data(country, exchange_rates)
                upsert_country(db, processed_data)
                countries_processed += 1
            except Exception as e:
                print(f"Error processing {country.get('name', 'unknown')}: {e}")
                continue
        
        # Generate image
        try:
            total, last_refresh = get_database_status(db)
            top_countries = get_top_countries_by_gdp(db, limit=5)
            if top_countries:
                generate_summary_image(total, top_countries, last_refresh or datetime.utcnow())
        except Exception as e:
            print(f"Image generation failed: {e}")
        
        return RefreshResponse(
            message="Countries data refreshed successfully",
            countries_processed=countries_processed,
            timestamp=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "Internal server error", "details": str(e)}
        )


@app.get("/countries/image")
def get_summary_image():
    """Serve the generated summary image."""
    image_path = get_image_path()
    
    if not image_path:
        raise HTTPException(
            status_code=404,
            detail={"error": "Summary image not found"}
        )
    
    return FileResponse(
        image_path,
        media_type="image/png",
        filename=settings.IMAGE_FILE_NAME
    )


@app.get("/countries", response_model=List[CountryResponse])
def get_countries(
    region: Optional[str] = Query(None),
    currency: Optional[str] = Query(None),
    sort: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Get all countries with optional filtering and sorting."""
    countries = get_all_countries(
        db=db,
        region=region,
        currency=currency,
        sort=sort
    )
    
    return [CountryResponse.from_orm(country) for country in countries]


@app.delete("/countries/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_country(name: str, db: Session = Depends(get_db)):
    """Delete a country by name."""
    deleted = delete_country_by_name(db, name)
    
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail={"error": "Country not found"}
        )
    
    return None


@app.get("/countries/{name}", response_model=CountryResponse)
def get_country(name: str, db: Session = Depends(get_db)):
    """Get a specific country by name."""
    country = get_country_by_name(db, name)
    
    if not country:
        raise HTTPException(
            status_code=404,
            detail={"error": "Country not found"}
        )
    
    return CountryResponse.from_orm(country)


@app.on_event("startup")
async def startup_event():
    print(f"\n🚀 {settings.APP_NAME} v{settings.APP_VERSION} starting...")
    print(f"📚 Docs: http://127.0.0.1:{settings.PORT}/docs\n")


if __name__ == "__main__":
    import uvicorn
    import os
    
    port = int(os.getenv("PORT", 8080))
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )