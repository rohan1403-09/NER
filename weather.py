import re
from typing import Optional

from fastapi import APIRouter, Query

from . import services

router = APIRouter(prefix="/api/weather", tags=["weather"])
LAT = Query(..., ge=-90, le=90); LON = Query(..., ge=-180, le=180)

# Values for the dashboard cards (RAINFALL / SOIL MOISTURE) plus the risk level
@router.get("/dashboard")
def dashboard(lat: float = LAT, lon: float = LON):
    r = services.assess(lat, lon)
    return {"rainfallMmPerHr": r["inputs"]["rainfall_mm_per_hr"], "soilMoisturePct": r["inputs"]["soil_moisture_pct"],
            "risk": {"level": r["level"], "score": r["score"]}}

@router.get("/current")
def current(lat: float = LAT, lon: float = LON, cityId: Optional[str] = Query(None, pattern=r"^\d{1,8}$")):
    return {"model": services.conditions(lat, lon), "imd": services.imd_city(cityId)}

@router.get("/imd")
def imd(cityId: Optional[str] = Query(None, pattern=r"^\d{1,8}$")): return services.imd_city(cityId)

@router.get("/satellite/layers")
def layers(date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$")): return services.gibs_layers(date)

@router.get("/satellite/rainfall")
def sat_rain(lat: float = LAT, lon: float = LON):
    return {"source": "NASA POWER / GPM IMERG", "unit": "mm/day", "data": services.imerg_daily(lat, lon)}
