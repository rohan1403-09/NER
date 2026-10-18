from fastapi import APIRouter, Query

from .core import now_ms, query
from . import services

router = APIRouter(prefix="/api/gis", tags=["gis"])
LAT = Query(..., ge=-90, le=90); LON = Query(..., ge=-180, le=180)

@router.get("/geocode")
def geocode(q: str = Query(..., min_length=2, max_length=200)): return services.geocode(q)

@router.get("/reverse")
def reverse(lat: float = LAT, lon: float = LON): return services.reverse(lat, lon)

@router.get("/terrain")
def terrain(lat: float = LAT, lon: float = LON): return services.slope_at(lat, lon)

@router.get("/risk")
def risk(lat: float = LAT, lon: float = LON): return services.assess(lat, lon)

# GeoJSON layers for any web map (Leaflet, Mapbox, OpenLayers, Google Maps data layer)
@router.get("/geojson/reports")
def geo_reports():
    rows = query("SELECT id,category,description,lat,lon,created_at FROM reports WHERE status='verified' AND lat IS NOT NULL")
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
         "properties": {k: r[k] for k in ("id", "category", "description", "created_at")}} for r in rows]}

@router.get("/geojson/alerts")
def geo_alerts():
    rows = query("SELECT * FROM alerts WHERE lat IS NOT NULL AND created_at>?", (now_ms() - 7 * 86400_000,))
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [a["lon"], a["lat"]]},
         "properties": {k: a[k] for k in ("id", "level", "title", "radius_km")}} for a in rows]}
