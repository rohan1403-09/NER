import asyncio, json
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .core import current_user, err, haversine_km, is_phone, now_ms, query, require_admin, run, valid_coords
from . import services

router = APIRouter(prefix="/api/alerts", tags=["alerts"])
LEVELS = ["info", "low", "moderate", "high", "critical"]

class AlertIn(BaseModel):
    level: str = ""; title: str = ""; body: str = ""
    lat: Optional[float] = None; lon: Optional[float] = None; radius_km: Optional[float] = None
class SmsIn(BaseModel):
    phone: str = ""; text: str = ""

@router.get("")
def list_alerts(lat: Optional[float] = None, lon: Optional[float] = None):
    rows = query("SELECT * FROM alerts WHERE created_at>? ORDER BY created_at DESC LIMIT 100", (now_ms() - 7 * 86400_000,))
    if valid_coords(lat, lon):
        rows = [a for a in rows if a["lat"] is None or haversine_km(lat, lon, a["lat"], a["lon"]) <= (a["radius_km"] or 25)]
    return rows

@router.get("/stream")
async def stream():
    """Server-Sent Events: new alerts arrive here in real time."""
    q = services.subscribe()
    async def gen():
        try:
            yield "retry: 5000\n\n"
            while True:
                try:
                    alert = await asyncio.wait_for(q.get(), timeout=25)
                    yield f"data: {json.dumps(alert)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            services.unsubscribe(q)
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@router.post("", status_code=201, dependencies=[Depends(require_admin)])
def publish(b: AlertIn):
    if b.level not in LEVELS: raise err(400, "level must be one of " + ", ".join(LEVELS))
    if not b.title.strip() or len(b.title) > 140: raise err(400, "title required (max 140 chars)")
    if b.lat is not None and (not valid_coords(b.lat, b.lon) or not (b.radius_km and 0 < b.radius_km <= 500)):
        raise err(400, "lat, lon and radius_km (1-500) must be valid")
    return services.create_alert(b.level, b.title.strip(), b.body[:500], b.lat, b.lon, b.radius_km)

@router.post("/message", dependencies=[Depends(require_admin)])
def one_off(b: SmsIn):
    if not is_phone(b.phone) or not b.text.strip(): raise err(400, "phone and text required")
    services.send_sms(b.phone, b.text[:300]); return {"sent": True}

@router.get("/inbox")
def inbox(user=Depends(current_user)):
    return query("SELECT id,alert_id,title,body,channel,status,is_read,created_at FROM messages WHERE user_id=? ORDER BY created_at DESC LIMIT 100", (user["id"],))

@router.post("/inbox/{msg_id}/read")
def mark_read(msg_id: int, user=Depends(current_user)):
    run("UPDATE messages SET is_read=1 WHERE id=? AND user_id=?", (msg_id, user["id"])); return {"ok": True}
