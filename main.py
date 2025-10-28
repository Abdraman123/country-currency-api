"""
Main FastAPI application with all endpoints.
"""

from fastapi import FastAPI, HTTPException, Depends, Query, status
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime

from database import engine, get_db, Base
from models import (
    CountryDB,
    CountryResponse,
    StatusResponse,
    RefreshResponse,
    ErrorResponse
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


# ============= Endpoints =============
# IMPORTANT: Specific routes MUST come before wildcard routes

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "endpoints": {
            "POST /countries/refresh": "Fetch and cache country data",
            "GET /countries": "Get all countries (supports filters and sorting)",
            "GET /countries/image": "Get summary image",
            "GET /countries/{name}": "Get specific country by name",
            "DELETE /countries/{name}": "Delete a country",
            "GET /status": "Get total countries and last refresh timestamp",
            "/docs": "Interactive API documentation"
        }
    }


@app.get("/status", response_model=StatusResponse)
async def get_status(db: Session = Depends(get_db)):
    """
    Get total number of countries and last refresh timestamp.
    
    Returns:
        StatusResponse with total countries and last refresh time
    """
    try:
        total, last_refresh = get_database_status(db)
        
        return StatusResponse(
            total_countries=total,
            last_refreshed_at=last_refresh
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Internal server error", "details": str(e)}
        )


# POST /countries/refresh - MUST be before /{name}
@app.post("/countries/refresh", response_model=RefreshResponse, status_code=status.HTTP_200_OK)
async def refresh_countries(db: Session = Depends(get_db)):
    """
    Fetch all countries and exchange rates, then cache them in database.
    Optimized for speed.
    """
    try:
        # Set shorter timeout for testing
        import asyncio
        
        # Fetch data with timeout
        try:
            async with asyncio.timeout(25):  # 25 second timeout
                countries_data = await fetch_countries_data()
                exchange_rates = await fetch_exchange_rates()
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "External data source unavailable",
                    "details": "External API took too long to respond"
                }
            )
        
        # Batch processing for speed
        countries_processed = 0
        batch = []
        
        for country in countries_data[:50]:  # Process ALL countries
            try:
                processed_data = process_country_data(country, exchange_rates)
                batch.append(processed_data)
                
                # Insert in batches of 10
                if len(batch) >= 10:
                    for data in batch:
                        upsert_country(db, data)
                    countries_processed += len(batch)
                    batch = []
                    
            except Exception as e:
                print(f"Error processing country: {str(e)}")
                continue
        
        # Process remaining
        if batch:
            for data in batch:
                upsert_country(db, data)
            countries_processed += len(batch)
        
        # Generate image (don't let this fail the endpoint)
        try:
            total, last_refresh = get_database_status(db)
            top_countries = get_top_countries_by_gdp(db, limit=5)
            if top_countries:
                generate_summary_image(total, top_countries, last_refresh or datetime.utcnow())
        except Exception as e:
            print(f"Image generation failed: {str(e)}")
        
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


# GET /countries/image - MUST be before /{name}
@app.get("/countries/image")
async def get_summary_image():
    """
    Serve the generated summary image.
    
    Returns:
        PNG image file
        
    Raises:
        404: If image not found
    """
    image_path = get_image_path()
    
    if not image_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Summary image not found"}
    )

    
    return FileResponse(
        image_path,
        media_type="image/png",
        filename=settings.IMAGE_FILE_NAME
    )


# GET /countries - MUST be before /{name}
@app.get("/countries", response_model=List[CountryResponse])
async def get_countries(
    region: Optional[str] = Query(None, description="Filter by region (e.g., Africa, Europe)"),
    currency: Optional[str] = Query(None, description="Filter by currency code (e.g., NGN, USD)"),
    sort: Optional[str] = Query(None, description="Sort order: gdp_desc, gdp_asc, population_desc, population_asc, name_asc, name_desc"),
    db: Session = Depends(get_db)
):
    """
    Get all countries from database with optional filtering and sorting.
    
    Query Parameters:
        - region: Filter by region (case-insensitive)
        - currency: Filter by currency code (case-insensitive)
        - sort: Sort order
    
    Returns:
        List of countries
    """
    try:
        countries = get_all_countries(
            db=db,
            region=region,
            currency=currency,
            sort=sort
        )
        
        return [CountryResponse.from_orm(country) for country in countries]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Internal server error", "details": str(e)}
        )


# DELETE /countries/{name}
@app.delete("/countries/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_country(name: str, db: Session = Depends(get_db)):
    """
    Delete a country by name (case-insensitive).
    
    Args:
        name: Country name
        
    Returns:
        204 No Content on success
        
    Raises:
        404: If country not found
    """
    deleted = delete_country_by_name(db, name)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Country not found"}
        )
    
    return None


# GET /countries/{name} - MUST be LAST (catches any country name)
@app.get("/countries/{name}", response_model=CountryResponse)
async def get_country(name: str, db: Session = Depends(get_db)):
    """
    Get a specific country by name (case-insensitive).
    
    Args:
        name: Country name
        
    Returns:
        Country data
        
    Raises:
        404: If country not found
    """
    country = get_country_by_name(db, name)
    
    if not country:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Country not found"}
        )
    
    return CountryResponse.from_orm(country)


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    print(f"\n🚀 {settings.APP_NAME} v{settings.APP_VERSION} starting...")
    print(f"📊 Database: MySQL at {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'localhost'}")
    print(f"📚 Docs: http://127.0.0.1:{settings.PORT}/docs\n")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    print(f"\n👋 {settings.APP_NAME} shutting down...\n")


if __name__ == "__main__":
    import uvicorn
    import os
    
    # DigitalOcean uses PORT environment variable
    port = int(os.getenv("PORT", 8080))
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",  # IMPORTANT: Bind to all interfaces
        port=port,
        reload=False  # No reload in production
    )