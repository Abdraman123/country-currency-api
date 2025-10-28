from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import engine, get_db, Base
from models import Country, RefreshMetadata
import services
from image_generator import generate_summary_image
from typing import Optional
import os

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Country Currency & Exchange API")

@app.get("/")
def root():
    return {"message": "Country Currency & Exchange API", "status": "running"}

@app.post("/countries/refresh")
async def refresh_countries(db: Session = Depends(get_db)):
    try:
        countries_data = await services.fetch_countries_data()
        exchange_rates = await services.fetch_exchange_rates()
        
        services.refresh_countries(db, countries_data, exchange_rates)
        
        top_countries = db.query(Country).filter(
            Country.estimated_gdp.isnot(None)
        ).order_by(Country.estimated_gdp.desc()).limit(5).all()
        
        metadata = db.query(RefreshMetadata).first()
        timestamp = metadata.last_refreshed_at if metadata else None
        
        total_countries = db.query(Country).count()
        generate_summary_image(total_countries, top_countries, timestamp)
        
        return {
            "message": "Countries data refreshed successfully",
            "total_countries": total_countries,
            "last_refreshed_at": timestamp.isoformat() if timestamp else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "Internal server error", "details": str(e)})

@app.get("/countries/image")
def get_summary_image():
    image_path = "cache/summary.png"
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail={"error": "Summary image not found"})
    
    return FileResponse(image_path, media_type="image/png")

@app.get("/status")
def get_status(db: Session = Depends(get_db)):
    return services.get_status(db)

@app.get("/countries")
def get_countries(
    region: Optional[str] = Query(None),
    currency: Optional[str] = Query(None),
    sort: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    countries = services.get_all_countries(db, region=region, currency=currency, sort=sort)
    
    return [
        {
            "id": c.id,
            "name": c.name,
            "capital": c.capital,
            "region": c.region,
            "population": c.population,
            "currency_code": c.currency_code,
            "exchange_rate": c.exchange_rate,
            "estimated_gdp": c.estimated_gdp,
            "flag_url": c.flag_url,
            "last_refreshed_at": c.last_refreshed_at.isoformat() if c.last_refreshed_at else None
        }
        for c in countries
    ]

@app.get("/countries/{name}")
def get_country(name: str, db: Session = Depends(get_db)):
    country = services.get_country_by_name(db, name)
    if not country:
        raise HTTPException(status_code=404, detail={"error": "Country not found"})
    
    return {
        "id": country.id,
        "name": country.name,
        "capital": country.capital,
        "region": country.region,
        "population": country.population,
        "currency_code": country.currency_code,
        "exchange_rate": country.exchange_rate,
        "estimated_gdp": country.estimated_gdp,
        "flag_url": country.flag_url,
        "last_refreshed_at": country.last_refreshed_at.isoformat() if country.last_refreshed_at else None
    }

@app.delete("/countries/{name}")
def delete_country(name: str, db: Session = Depends(get_db)):
    deleted = services.delete_country_by_name(db, name)
    if not deleted:
        raise HTTPException(status_code=404, detail={"error": "Country not found"})
    
    return {"message": f"Country '{name}' deleted successfully"}

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)