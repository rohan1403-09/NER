"""SMS, OTP, GIS, IMD/weather, satellite, risk model, alert dispatch and background monitor."""
import asyncio, hashlib, hmac, logging, math, os, secrets, threading, time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

from .core import (JWT_SECRET, PRODUCTION, fetch_json, haversine_km, now_ms, one, query, run)

log = logging.getLogger("trailsense")

# =============================== SMS ===============================
def send_sms(phone10: str, text: str, kind: str = "alert"):
    provider = os.getenv("SMS_PROVIDER", "console")
    to = "+91" + phone10
    try:
        if provider == "console":
            log.warning("[SMS:console] to %s: %s", to, text)
        elif provider == "twilio":
            sid, token = os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN")
            r = httpx.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", auth=(sid, token),
                           data={"To": to, "From": os.getenv("TWILIO_FROM"), "Body": text}, timeout=9)
            r.raise_for_status()
        elif provider == "msg91":
            # India needs DLT-registered templates; the template must define a variable named VAR1.
            tpl = os.getenv("MSG91_OTP_TEMPLATE_ID" if kind == "otp" else "MSG91_ALERT_TEMPLATE_ID")
            r = httpx.post("https://control.msg91.com/api/v5/flow/", headers={"authkey": os.getenv("MSG91_AUTH_KEY", "")},
                           json={"template_id": tpl, "recipients": [{"mobiles": "91" + phone10, "VAR1": text}]}, timeout=9)
            r.raise_for_status()
        else:
            raise ValueError("Unknown SMS_PROVIDER " + provider)
    except httpx.HTTPError as e:
        raise RuntimeError("SMS provider error: " + str(e)) from e

# =============================== OTP ===============================
OTP_TTL_MS, OTP_COOLDOWN_MS, OTP_MAX_ATTEMPTS = 5 * 60_000, 30_000, 5

def _hash(phone, code):
    return hmac.new(JWT_SECRET.encode(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()

def send_otp(phone):
    now = now_ms()
    row = one("SELECT last_sent FROM otps WHERE phone=?", (phone,))
    if row and now - row["last_sent"] < OTP_COOLDOWN_MS:
        return {"ok": False, "retry_after": math.ceil((OTP_COOLDOWN_MS - (now - row["last_sent"])) / 1000)}
    code = f"{secrets.randbelow(1_000_000):06d}"
    run("""INSERT INTO otps(phone,code_hash,expires_at,attempts,last_sent) VALUES(?,?,?,0,?)
           ON CONFLICT(phone) DO UPDATE SET code_hash=excluded.code_hash, expires_at=excluded.expires_at,
           attempts=0, last_sent=excluded.last_sent""", (phone, _hash(phone, code), now + OTP_TTL_MS, now))
    send_sms(phone, f"Your Trail Sense OTP is {code}. It is valid for 5 minutes. Do not share it.", "otp")
    dev = (not PRODUCTION) and os.getenv("SMS_PROVIDER", "console") == "console"
    return {"ok": True, "dev_otp": code if dev else None}

def verify_otp(phone, code):
    row = one("SELECT * FROM otps WHERE phone=?", (phone,))
    if not row:
        return False, "No OTP requested for this number"
    if now_ms() > row["expires_at"]:
        run("DELETE FROM otps WHERE phone=?", (phone,))
        return False, "OTP expired. Request a new one."
    if row["attempts"] >= OTP_MAX_ATTEMPTS:
        run("DELETE FROM otps WHERE phone=?", (phone,))
        return False, "Too many attempts. Request a new OTP."
    run("UPDATE otps SET attempts=attempts+1 WHERE phone=?", (phone,))
    if not hmac.compare_digest(_hash(phone, code), row["code_hash"]):
        return False, "Invalid OTP. Please try again."
    run("DELETE FROM otps WHERE phone=?", (phone,))
    return True, None

# =============================== GIS ===============================
def _ua():
    return {"User-Agent": os.getenv("GEOCODER_USER_AGENT", "TrailSense/1.0"), "Accept-Language": "en"}

def geocode(q):
    """Nominatim (OpenStreetMap). Public instance allows ~1 request/second, so results are cached."""
    qs = urlencode({"format": "jsonv2", "limit": 5, "countrycodes": "in", "q": q})
    rows = fetch_json("https://nominatim.openstreetmap.org/search?" + qs, _ua(), ttl=600)
    return [{"name": r["display_name"], "lat": float(r["lat"]), "lon": float(r["lon"]), "type": r.get("type")} for r in rows]

def reverse(lat, lon):
    r = fetch_json(f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}", _ua(), ttl=600)
    return {"name": r.get("display_name"), "address": r.get("address", {})}

def elevations(points):
    """Open-Meteo elevation API (Copernicus DEM, ~90 m grid), no key needed."""
    lats = ",".join(f"{p[0]:.5f}" for p in points)
    lons = ",".join(f"{p[1]:.5f}" for p in points)
    return fetch_json(f"https://api.open-meteo.com/v1/elevation?latitude={lats}&longitude={lons}", ttl=86400)["elevation"]

def slope_at(lat, lon, d=250):
    """Slope (degrees) from central differences over a 250 m offset."""
    dlat = d / 111320
    dlon = d / (111320 * math.cos(math.radians(lat)))
    c, n, s, e, w = elevations([(lat, lon), (lat + dlat, lon), (lat - dlat, lon), (lat, lon + dlon), (lat, lon - dlon)])
    dzdy, dzdx = (n - s) / (2 * d), (e - w) / (2 * d)
    return {"elevation": c, "slope_deg": round(math.degrees(math.atan(math.hypot(dzdx, dzdy))), 1)}

# =============================== IMD + weather ===============================
def imd_city(city_id=None):
    """IMD has no single stable public API. This calls the city-weather endpoint from .env;
    verify it on mausam.imd.gov.in. For official district warnings / gridded data, request access via
    IMD's data supply portal and add that URL here."""
    base = os.getenv("IMD_CITY_URL")
    if not base:
        return None
    try:
        return fetch_json(base + str(city_id or os.getenv("IMD_DEFAULT_CITY_ID", "")), ttl=900)
    except Exception as e:
        return {"error": str(e)}

def conditions(lat, lon):
    """Rainfall and soil moisture from Open-Meteo (keyless); feeds the dashboard and the risk model."""
    d = fetch_json("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
                   "&current=temperature_2m,precipitation&hourly=precipitation,soil_moisture_3_to_9cm"
                   "&past_days=3&forecast_days=2&timezone=auto" % (lat, lon), ttl=600)
    times, rain, soil = d["hourly"]["time"], d["hourly"]["precipitation"], d["hourly"]["soil_moisture_3_to_9cm"]
    key = d["current"]["time"][:13] + ":00"
    i = times.index(key) if key in times else min(71, len(times) - 1)
    total = lambda a, b: round(sum(v or 0 for v in rain[max(a, 0):b]), 1)
    sm = soil[i]
    return {
        "temperature_c": d["current"].get("temperature_2m"),
        "rainfall_mm_per_hr": d["current"].get("precipitation") or rain[i] or 0,
        "rain_24h": total(i - 23, i + 1), "rain_72h": total(i - 71, i + 1), "rain_next_24h": total(i + 1, i + 25),
        "soil_moisture_pct": None if sm is None else round(min(100, sm / 0.45 * 100)),
        "source": "open-meteo",
    }

# =============================== satellite ===============================
def gibs_layers(date=None):
    """NASA GIBS tile templates (keyless) for map overlays in Leaflet/OpenLayers/Mapbox."""
    day = date or (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    t = lambda layer, ext: f"https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/{layer}/default/{day}/GoogleMapsCompatible_Level6/{{z}}/{{y}}/{{x}}.{ext}"
    return {"date": day, "layers": [
        {"id": "imerg_rain", "name": "GPM IMERG precipitation rate", "tiles": t("IMERG_Precipitation_Rate", "png")},
        {"id": "true_color", "name": "VIIRS true colour", "tiles": t("VIIRS_SNPP_CorrectedReflectance_TrueColor", "jpg")}]}

def imerg_daily(lat, lon, days=14):
    """NASA POWER daily point data: GPM IMERG satellite rainfall (mm/day). Usually lags a few days."""
    f = lambda dt: dt.strftime("%Y%m%d")
    end = datetime.now(timezone.utc); start = end - timedelta(days=days)
    d = fetch_json("https://power.larc.nasa.gov/api/temporal/daily/point?parameters=IMERG_PRECTOT&community=AG"
                   f"&longitude={lon}&latitude={lat}&start={f(start)}&end={f(end)}&format=JSON", ttl=3 * 3600)
    raw = d["properties"]["parameter"].get("IMERG_PRECTOT", {})
    return [{"date": f"{k[:4]}-{k[4:6]}-{k[6:]}", "mm": v} for k, v in raw.items() if v > -900]   # -999 = missing

# =============================== risk model ===============================
def _tier(v, tiers):
    for lo, pts in tiers:
        if v >= lo:
            return pts
    return 0

def assess(lat, lon):
    """Rule-based landslide score 0-100. A heuristic, not a calibrated model; swap in your ML model later."""
    w = conditions(lat, lon)
    try:
        terrain = slope_at(lat, lon)
    except Exception:
        terrain = None
    week_ago = now_ms() - 7 * 86400_000
    nearby = sum(1 for r in query("SELECT lat,lon FROM reports WHERE status='verified' AND created_at>? AND lat IS NOT NULL", (week_ago,))
                 if haversine_km(lat, lon, r["lat"], r["lon"]) <= 10)
    factors = {
        "rain_24h": _tier(w["rain_24h"], [(100, 35), (50, 26), (25, 16), (10, 8)]),
        "rain_72h": _tier(w["rain_72h"], [(200, 20), (100, 12), (50, 6)]),
        "soil": _tier(w["soil_moisture_pct"] or 0, [(85, 20), (70, 12), (55, 6)]),
        "slope": _tier(terrain["slope_deg"], [(30, 20), (20, 12), (10, 5)]) if terrain else 0,
        "reports": min(15, nearby * 5),
    }
    score = min(100, sum(factors.values()))
    level = "critical" if score >= 75 else "high" if score >= 50 else "moderate" if score >= 25 else "low"
    return {"level": level, "score": score, "factors": factors, "inputs": {**w, **(terrain or {}), "verified_reports_nearby": nearby}}

# =============================== alerts ===============================
SMS_LEVELS = {"high", "critical"}
_subscribers: set = set()
_loop = None

def set_loop(loop):
    global _loop
    _loop = loop

def subscribe():
    q = asyncio.Queue(maxsize=100); _subscribers.add(q); return q

def unsubscribe(q):
    _subscribers.discard(q)

def _publish(alert):
    if _loop:
        for q in list(_subscribers):
            _loop.call_soon_threadsafe(lambda q=q: q.put_nowait(alert) if not q.full() else None)

def create_alert(level, title, body="", lat=None, lon=None, radius_km=None, source="admin"):
    ts = now_ms()
    alert_id, _ = run("INSERT INTO alerts(level,title,body,lat,lon,radius_km,source,created_at) VALUES(?,?,?,?,?,?,?,?)",
                      (level, title, body, lat, lon, radius_km, source, ts))
    alert = dict(id=alert_id, level=level, title=title, body=body, lat=lat, lon=lon, radius_km=radius_km, source=source, created_at=ts)

    users = [u for u in query("SELECT id,phone,lat,lon FROM users WHERE verified=1")
             if lat is None or radius_km is None or (u["lat"] is not None and haversine_km(lat, lon, u["lat"], u["lon"]) <= radius_km)]
    for u in users:
        status = "in-app"
        if level in SMS_LEVELS:
            try:
                send_sms(u["phone"], f"[Trail Sense {level.upper()}] {title}. {body}"[:300]); status = "sms-sent"
            except Exception as e:
                log.error("SMS failed for user %s: %s", u["id"], e); status = "sms-failed"
        run("INSERT INTO messages(user_id,alert_id,title,body,channel,status,created_at) VALUES(?,?,?,?,?,?,?)",
            (u["id"], alert_id, title, body, "sms+app" if level in SMS_LEVELS else "app", status, ts))
    _publish(alert)
    return {"alert": alert, "recipients": len(users)}

# =============================== background monitor ===============================
def _monitor_once():
    cells = query("SELECT ROUND(lat,1) la, ROUND(lon,1) lo FROM users WHERE verified=1 AND lat IS NOT NULL GROUP BY la,lo LIMIT 200")
    for c in cells:
        try:
            r = assess(c["la"], c["lo"])
            if r["level"] not in ("high", "critical"):
                continue
            recent = query("SELECT lat,lon FROM alerts WHERE source='auto' AND created_at>?", (now_ms() - 6 * 3600_000,))
            if any(haversine_km(a["lat"], a["lon"], c["la"], c["lo"]) < 15 for a in recent):
                continue
            i = r["inputs"]
            create_alert(r["level"], f"Landslide risk {r['level'].upper()} in your area",
                         f"Rain 24h: {i['rain_24h']} mm, soil moisture: {i['soil_moisture_pct']}%. Avoid steep slopes and check road status.",
                         c["la"], c["lo"], 15, "auto")
        except Exception as e:
            log.error("Monitor cell %s failed: %s", c, e)
        time.sleep(1.5)       # be polite to free upstream APIs

def start_monitor():
    if os.getenv("MONITOR_ENABLED", "true") == "false":
        return
    every = max(5, int(os.getenv("MONITOR_INTERVAL_MIN", "30"))) * 60
    def loop():
        while True:
            time.sleep(every)
            try: _monitor_once()
            except Exception as e: log.error("Monitor error: %s", e)
    threading.Thread(target=loop, daemon=True).start()
    log.warning("Risk monitor running every %s min", every // 60)
