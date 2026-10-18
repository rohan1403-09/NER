"""Config, database, helpers, auth dependencies."""
import hmac, math, os, sqlite3, threading, time
from collections import defaultdict, deque
from contextlib import closing
from pathlib import Path

import httpx, jwt
from dotenv import load_dotenv
from fastapi import Depends, Header, HTTPException, Request

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET", "")
if len(JWT_SECRET) < 32:
    raise RuntimeError("Set JWT_SECRET (32+ chars) in .env")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
PRODUCTION = os.getenv("ENV", "development") == "production"

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE / "data")); DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE / "uploads")); UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "trailsense.db"

# ---------------- database (stdlib sqlite3) ----------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, email TEXT UNIQUE, password_hash TEXT, name TEXT,
  phone TEXT UNIQUE NOT NULL, location TEXT, lat REAL, lon REAL,
  verified INTEGER DEFAULT 0, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS otps(
  phone TEXT PRIMARY KEY, code_hash TEXT NOT NULL, expires_at INTEGER NOT NULL,
  attempts INTEGER DEFAULT 0, last_sent INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS alerts(
  id INTEGER PRIMARY KEY, level TEXT NOT NULL, title TEXT NOT NULL, body TEXT,
  lat REAL, lon REAL, radius_km REAL, source TEXT, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  alert_id INTEGER, title TEXT, body TEXT, channel TEXT, status TEXT,
  is_read INTEGER DEFAULT 0, created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS reports(
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  category TEXT NOT NULL, description TEXT, lat REAL, lon REAL,
  status TEXT DEFAULT 'pending', created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS media(
  id INTEGER PRIMARY KEY, report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
  kind TEXT, filename TEXT, mime TEXT, size INTEGER);
"""

def conn():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init_db():
    with closing(conn()) as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(SCHEMA)

def query(sql, args=()):
    with closing(conn()) as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]

def one(sql, args=()):
    rows = query(sql, args)
    return rows[0] if rows else None

def run(sql, args=()):
    """Execute a write. Returns (lastrowid, rowcount)."""
    with closing(conn()) as c:
        cur = c.execute(sql, args)
        c.commit()
        return cur.lastrowid, cur.rowcount

now_ms = lambda: int(time.time() * 1000)

# ---------------- helpers ----------------
class UpstreamError(Exception):
    pass

_cache, _cache_lock = {}, threading.Lock()

def fetch_json(url, headers=None, ttl=0):
    """GET JSON from a third-party API with timeout and optional in-memory cache (ttl seconds)."""
    if ttl:
        with _cache_lock:
            hit = _cache.get(url)
            if hit and hit[0] > time.time():
                return hit[1]
    try:
        r = httpx.get(url, headers=headers, timeout=9.0, follow_redirects=True)
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError) as e:
        raise UpstreamError(str(e)) from e
    if ttl:
        with _cache_lock:
            _cache[url] = (time.time() + ttl, data)
    return data

def haversine_km(lat1, lon1, lat2, lon2):
    r = math.pi / 180
    a = math.sin((lat2 - lat1) * r / 2) ** 2 + math.cos(lat1 * r) * math.cos(lat2 * r) * math.sin((lon2 - lon1) * r / 2) ** 2
    return 12742 * math.asin(math.sqrt(a))

import re
def is_phone(p): return bool(re.fullmatch(r"[6-9]\d{9}", str(p or "")))          # Indian mobile
def is_email(e): return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", str(e or ""))) and len(e) <= 254
def valid_coords(lat, lon):
    return lat is not None and lon is not None and abs(lat) <= 90 and abs(lon) <= 180

def err(status, message):
    return HTTPException(status_code=status, detail=message)

# ---------------- rate limiting (in-memory, per IP + path; use Redis if you run several workers) ----------------
_hits = defaultdict(deque)
def rate_limit(limit, window_s):
    def dep(request: Request):
        key = (request.client.host if request.client else "?", request.url.path)
        dq, t = _hits[key], time.time()
        while dq and dq[0] < t - window_s:
            dq.popleft()
        if len(dq) >= limit:
            raise err(429, "Too many requests. Try again later.")
        dq.append(t)
    return Depends(dep)

# ---------------- auth ----------------
def sign_token(user):
    return jwt.encode({"sub": str(user["id"]), "phone": user["phone"], "exp": int(time.time()) + 7 * 86400}, JWT_SECRET, algorithm="HS256")

def current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise err(401, "Login required")
    try:
        data = jwt.decode(authorization[7:], JWT_SECRET, algorithms=["HS256"])
        return {"id": int(data["sub"]), "phone": data["phone"]}
    except (jwt.PyJWTError, KeyError, ValueError):
        raise err(401, "Invalid or expired token")

def require_admin(x_admin_key: str = Header(None)):
    if not ADMIN_API_KEY or not hmac.compare_digest((x_admin_key or "").encode(), ADMIN_API_KEY.encode()):
        raise err(403, "Admin only")
