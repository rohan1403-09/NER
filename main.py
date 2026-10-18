import asyncio, logging, os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .core import PRODUCTION, UPLOAD_DIR, UpstreamError, init_db
from . import alerts, auth, gis, reports, services, weather

logging.basicConfig(level=logging.INFO)
init_db()

app = FastAPI(title="Trail Sense API", docs_url=None if PRODUCTION else "/docs", redoc_url=None, openapi_url=None if PRODUCTION else "/openapi.json")

origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "PATCH"],
                   allow_headers=["Content-Type", "Authorization", "x-admin-key"])

@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Cross-Origin-Resource-Policy"] = "cross-origin"      # lets the frontend show uploaded media
    return resp

# Errors always look like {"error": "..."} so the frontend can show them directly
@app.exception_handler(StarletteHTTPException)
async def http_err(request, exc): return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

@app.exception_handler(RequestValidationError)
async def bad_input(request, exc): return JSONResponse({"error": "Invalid request. Check the values you sent."}, status_code=400)

@app.exception_handler(UpstreamError)
async def upstream(request, exc):
    logging.error("Upstream error: %s", exc)
    return JSONResponse({"error": "A data provider is unavailable. Try again shortly."}, status_code=502)

@app.exception_handler(Exception)
async def crash(request, exc):
    logging.exception("Unhandled error")
    return JSONResponse({"error": "Server error"}, status_code=500)

@app.on_event("startup")
async def startup():
    services.set_loop(asyncio.get_running_loop())
    services.start_monitor()

@app.get("/api/health")
def health(): return {"ok": True}

for r in (auth, alerts, reports, gis, weather):
    app.include_router(r.router)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
