"""
Main FastAPI application with all endpoints.
"""

from fastapi import FastAPI, HTTPException, Depends, Query, status
from fastapi.responses import JSONResponse, FileResponse
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

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "endpoints": {
            "POST /countries/refresh": "Fetch and cache country data",
            "GET /countries": "Get all countries (supports filters and sorting)",
            "GET /countries/{name}": "Get specific country by name",
            "DELETE /countries/{name}": "Delete a country",
            "GET /status": "Get total countries and last refresh timestamp",
            "GET /countries/image": "Get summary image",
            "/docs": "Interactive API documentation"
        }
    }


@app.post("/countries/refresh", response_model=RefreshResponse, status_code=status.HTTP_200_OK)
async def refresh_countries(db: Session = Depends(get_db)):
    """
    Fetch all countries and exchange rates, then cache them in database.
    Also generates a summary image.
    
    Returns:
        RefreshResponse with number of countries processed
        
    Raises:
        503: If external APIs are unavailable
    """
    try:
        # Fetch data from external APIs
        countries_data = await fetch_countries_data()
        exchange_rates = await fetch_exchange_rates()
        
        # Process and store each country
        countries_processed = 0
        for country in countries_data:
            try:
                # Process country data
                processed_data = process_country_data(country, exchange_rates)
                
                # Store or update in database
                upsert_country(db, processed_data)
                countries_processed += 1
                
            except Exception as e:
                # Log error but continue processing other countries
                print(f"Error processing country {country.get('name')}: {str(e)}")
                continue
        
        # Generate summary image
        try:
            total, last_refresh = get_database_status(db)
            top_countries = get_top_countries_by_gdp(db, limit=5)
            generate_summary_image(total, top_countries, last_refresh or datetime.utcnow())
        except Exception as e:
            print(f"Error generating image: {str(e)}")
            # Don't fail the entire refresh if image generation fails
        
        return RefreshResponse(
            message="Countries data refreshed successfully",
            countries_processed=countries_processed,
            timestamp=datetime.utcnow()
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (from external API failures)
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Internal server error", "details": str(e)}
        )


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
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )