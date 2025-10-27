"""
Data models for both SQLAlchemy (database) and Pydantic (API validation).
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, func
from sqlalchemy.sql import text
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from database import Base


# ============= SQLAlchemy Models (Database Tables) =============

class CountryDB(Base):
    """
    SQLAlchemy model representing the countries table in MySQL.
    """
    __tablename__ = "countries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    capital = Column(String(255), nullable=True)
    region = Column(String(100), nullable=True, index=True)
    population = Column(Integer, nullable=False)
    currency_code = Column(String(10), nullable=True, index=True)
    exchange_rate = Column(Float, nullable=True)
    estimated_gdp = Column(Float, nullable=True)
    flag_url = Column(String(500), nullable=True)
    last_refreshed_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


# ============= Pydantic Models (API Validation) =============

class CountryResponse(BaseModel):
    """Response model for country data."""
    id: int
    name: str
    capital: Optional[str] = None
    region: Optional[str] = None
    population: int
    currency_code: Optional[str] = None
    exchange_rate: Optional[float] = None
    estimated_gdp: Optional[float] = None
    flag_url: Optional[str] = None
    last_refreshed_at: datetime
    
    class Config:
        from_attributes = True


class StatusResponse(BaseModel):
    """Response model for status endpoint."""
    total_countries: int
    last_refreshed_at: Optional[datetime] = None


class RefreshResponse(BaseModel):
    """Response model for refresh endpoint."""
    message: str
    countries_processed: int
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    details: Optional[Any] = None


class ValidationErrorResponse(BaseModel):
    """Validation error response."""
    error: str = "Validation failed"
    details: Dict[str, str]