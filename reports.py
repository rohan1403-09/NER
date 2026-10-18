"""Photo / video reports of landslides and blocked roads."""
import uuid
from contextlib import closing
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel

from .core import UPLOAD_DIR, conn, current_user, err, now_ms, query, require_admin, run, valid_coords

router = APIRouter(prefix="/api/reports", tags=["reports"])

EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov"}
MAX_IMAGE, MAX_VIDEO, MAX_FILES = 15 * 1024 * 1024, 100 * 1024 * 1024, 5
CATEGORIES = ["landslide", "road_blockage", "other"]

def signature_ok(path, mime):
    """The browser-declared type can be faked, so check the real file signature."""
    with open(path, "rb") as f:
        b = f.read(12)
    if mime == "image/jpeg": return b[:2] == b"\xff\xd8"
    if mime == "image/png": return b[:4] == b"\x89PNG"
    if mime == "image/webp": return b[:4] == b"RIFF" and b[8:12] == b"WEBP"
    if mime == "video/webm": return b[:4] == b"\x1a\x45\xdf\xa3"
    return b[4:8] == b"ftyp"                      # mp4 / mov

def with_media(rows):
    for r in rows:
        r["media"] = [{**m, "url": "/uploads/" + m["filename"]} for m in
                      query("SELECT kind,filename,mime,size FROM media WHERE report_id=?", (r["id"],))]
    return rows

@router.post("", status_code=201)
def create_report(category: str = Form(...), description: str = Form(""), lat: Optional[str] = Form(None), lon: Optional[str] = Form(None),
                  media: List[UploadFile] = File(default=[]), user=Depends(current_user)):
    saved = []                                   # [(path, filename, mime, size)]
    def discard():
        for p, *_ in saved: p.unlink(missing_ok=True)
    try:
        if category not in CATEGORIES: raise err(400, "category must be one of " + ", ".join(CATEGORIES))
        description = description.strip()[:1000]
        try:
            la = float(lat) if lat else None; lo = float(lon) if lon else None
        except ValueError:
            raise err(400, "Invalid coordinates")
        if (la is not None or lo is not None) and not valid_coords(la, lo): raise err(400, "Invalid coordinates")
        media = [m for m in media if m.filename]
        if len(media) > MAX_FILES: raise err(400, f"At most {MAX_FILES} files")
        if not media and not description: raise err(400, "Add a photo, video or description")

        for m in media:
            if m.content_type not in EXT: raise err(400, "Unsupported file type. Use JPG, PNG, WEBP, MP4, WEBM or MOV.")
            is_img = m.content_type.startswith("image/")
            limit = MAX_IMAGE if is_img else MAX_VIDEO
            name = uuid.uuid4().hex + EXT[m.content_type]
            path, size = UPLOAD_DIR / name, 0
            saved.append((path, name, m.content_type, 0))
            with open(path, "wb") as out:
                while chunk := m.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > limit: raise err(400, f"{'Images' if is_img else 'Videos'} must be under {limit // 1024 // 1024} MB")
                    out.write(chunk)
            if not signature_ok(path, m.content_type): raise err(400, "File content does not match its type")
            saved[-1] = (path, name, m.content_type, size)

        with closing(conn()) as c:
            cur = c.execute("INSERT INTO reports(user_id,category,description,lat,lon,created_at) VALUES(?,?,?,?,?,?)",
                            (user["id"], category, description, la, lo, now_ms()))
            for _, name, mime, size in saved:
                c.execute("INSERT INTO media(report_id,kind,filename,mime,size) VALUES(?,?,?,?,?)",
                          (cur.lastrowid, "video" if mime.startswith("video/") else "image", name, mime, size))
            c.commit()
        return {"id": cur.lastrowid, "status": "pending", "message": "Report received. It will appear publicly after verification."}
    except Exception:
        discard(); raise

@router.get("")
def public_reports():
    return with_media(query("SELECT id,category,description,lat,lon,created_at FROM reports WHERE status='verified' ORDER BY created_at DESC LIMIT 100"))

@router.get("/mine")
def mine(user=Depends(current_user)):
    return with_media(query("SELECT id,category,description,lat,lon,status,created_at FROM reports WHERE user_id=? ORDER BY created_at DESC", (user["id"],)))

@router.get("/pending", dependencies=[Depends(require_admin)])
def pending():
    return with_media(query("SELECT * FROM reports WHERE status='pending' ORDER BY created_at"))

class StatusIn(BaseModel):
    status: str = ""

@router.patch("/{report_id}/status", dependencies=[Depends(require_admin)])
def set_status(report_id: int, b: StatusIn):
    if b.status not in ("verified", "rejected"): raise err(400, "status must be verified or rejected")
    _, n = run("UPDATE reports SET status=? WHERE id=?", (b.status, report_id))
    if not n: raise err(404, "Report not found")
    return {"ok": True}
