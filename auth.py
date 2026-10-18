import bcrypt
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .core import current_user, err, is_email, is_phone, now_ms, one, rate_limit, run, sign_token
from . import services

router = APIRouter(prefix="/api/auth", tags=["auth"])
strict = rate_limit(10, 600)

class Register(BaseModel):
    email: str = ""; password: str = ""; phone: str = ""; location: str = ""
class PhoneIn(BaseModel):
    phone: str = ""; name: str = ""
class Verify(BaseModel):
    phone: str = ""; otp: str = ""; name: str = ""

def _otp_response(phone):
    r = services.send_otp(phone)
    if not r["ok"]:
        raise err(429, f"Please wait {r['retry_after']}s before requesting another OTP")
    return {"otpSent": True, **({"devOtp": r["dev_otp"]} if r["dev_otp"] else {})}

# Sign-in form: email, password, phone, location
@router.post("/register", dependencies=[strict])
def register(b: Register):
    if not is_email(b.email): raise err(400, "Enter a valid email")
    if len(b.password) < 8 or len(b.password) > 72: raise err(400, "Password must be 8-72 characters")
    if not is_phone(b.phone): raise err(400, "Enter a valid 10 digit phone number")
    if not b.location.strip() or len(b.location) > 200: raise err(400, "Enter your location")
    email = b.email.lower()
    if one("SELECT 1 FROM users WHERE verified=1 AND (phone=? OR email=?)", (b.phone, email)):
        raise err(409, "An account with this email or phone already exists. Use Login.")
    lat = lon = None
    try:
        g = services.geocode(b.location)
        if g: lat, lon = g[0]["lat"], g[0]["lon"]
    except Exception:
        pass                                   # location stays unresolved; user can still sign up
    pw = bcrypt.hashpw(b.password.encode(), bcrypt.gensalt(12)).decode()
    run("DELETE FROM users WHERE verified=0 AND (phone=? OR email=?)", (b.phone, email))
    run("INSERT INTO users(email,password_hash,phone,location,lat,lon,created_at) VALUES(?,?,?,?,?,?,?)",
        (email, pw, b.phone, b.location.strip(), lat, lon, now_ms()))
    return _otp_response(b.phone)

# Login form: name + phone, then OTP
@router.post("/login", dependencies=[strict])
def login(b: PhoneIn):
    if not is_phone(b.phone): raise err(400, "Enter a valid 10 digit phone number")
    if not one("SELECT 1 FROM users WHERE phone=? AND verified=1", (b.phone,)):
        return {"otpSent": True}              # same reply, so registered numbers aren't revealed
    return _otp_response(b.phone)

@router.post("/otp/resend", dependencies=[strict])
def resend(b: PhoneIn):
    if not is_phone(b.phone): raise err(400, "Enter a valid 10 digit phone number")
    if not one("SELECT 1 FROM users WHERE phone=?", (b.phone,)):
        return {"otpSent": True}
    return _otp_response(b.phone)

@router.post("/otp/verify", dependencies=[strict])
def verify(b: Verify):
    if not is_phone(b.phone) or not (b.otp.isdigit() and len(b.otp) == 6): raise err(400, "Enter the 6-digit OTP")
    ok, msg = services.verify_otp(b.phone, b.otp)
    if not ok: raise err(401, msg)
    user = one("SELECT * FROM users WHERE phone=?", (b.phone,))
    if not user: raise err(401, "Invalid OTP. Please try again.")
    run("UPDATE users SET verified=1, name=COALESCE(?,name) WHERE id=?", (b.name.strip()[:80] or None, user["id"]))
    return {"token": sign_token(user)}

@router.get("/me")
def me(user=Depends(current_user)):
    u = one("SELECT id,name,email,phone,location,lat,lon FROM users WHERE id=?", (user["id"],))
    if not u: raise err(404, "User not found")
    return u
