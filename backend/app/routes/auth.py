from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
import hashlib

from backend.app.security import (
    AuthenticatedUser,
    LoginInput,
    PatientRegistration,
    clear_session,
    cookie_kwargs,
    create_session,
    current_user,
)
from backend.app.store import Store, now, store

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_patient(payload: PatientRegistration, response: Response):
    """Create a patient identity and a server-side session; no client-only identity state."""
    patient_id = f"P_{uuid4().hex[:10].upper()}"
    user_id = f"USR_{uuid4().hex}"
    created = now()
    try:
        with store.connection() as db:
            if db.execute("SELECT 1 FROM users WHERE email=?", (payload.email,)).fetchone():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account already exists for this email")
            db.execute(
                "INSERT INTO patients(patient_id,name,age,gender,language,phone,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (patient_id, payload.name, payload.age, payload.gender, payload.language, payload.phone, created, created),
            )
            db.execute(
                "INSERT INTO users(user_id,email,password_hash,role,patient_id,display_name,created_at) VALUES(?,?,?,?,?,?,?)",
                (user_id, payload.email, Store.hash_password(payload.password), "PATIENT", patient_id, payload.name, created),
            )
            store.audit(db, user_id, "PATIENT_REGISTERED", "PATIENT", patient_id)
    except HTTPException:
        raise
    token, expires_at = create_session(user_id)
    response.set_cookie("medikiosk_session", token, **cookie_kwargs(expires_at))
    return {"user": {"user_id": user_id, "role": "PATIENT", "patient_id": patient_id, "display_name": payload.name}, "patient_id": patient_id}


@router.post("/login")
def login(payload: LoginInput, response: Response):
    with store.connection() as db:
        row = db.execute("SELECT * FROM users WHERE email=?", (payload.email,)).fetchone()
        if not row or not Store.check_password(payload.password, row["password_hash"]):
            store.audit(db, None, "LOGIN_FAILED", "AUTH", 'login', {"reason": "invalid_credentials"})
            db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        user = dict(row)
    token, expires_at = create_session(user["user_id"])
    response.set_cookie("medikiosk_session", token, **cookie_kwargs(expires_at))
    return {"user": {key: user[key] for key in ("user_id", "email", "role", "patient_id", "display_name")}, "expires_at": expires_at}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, request: Request):
    # The browser cookie is cleared even if the server-side session has already expired.
    response.delete_cookie("medikiosk_session", path="/")
    with store.connection() as db:
        token_hash = hashlib.sha256(request.cookies.get('medikiosk_session','').encode()).hexdigest()
        session = db.execute('SELECT user_id FROM sessions WHERE token_hash=?', (token_hash,)).fetchone()
        db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))
        if session:
            store.audit(db, session['user_id'], "LOGOUT", "SESSION", session['user_id'])


@router.get("/me")
def me(user: AuthenticatedUser = Depends(current_user)):
    return {"user": user.model_dump()}
