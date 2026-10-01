from __future__ import annotations

import json
from typing import Any

import requests
import streamlit as st

try:
    import firebase_admin
    from firebase_admin import credentials, firestore, messaging
except ImportError:
    firebase_admin = None
    credentials = None
    firestore = None
    messaging = None

AUTH_BASE = "https://identitytoolkit.googleapis.com/v1/accounts"


def _secrets() -> dict[str, Any]:
    if "firebase" not in st.secrets:
        return {}
    return dict(st.secrets["firebase"])


def firebase_available() -> bool:
    cfg = _secrets()
    return bool(cfg.get("api_key"))


def _auth_request(endpoint: str, payload: dict) -> dict:
    cfg = _secrets()
    if not cfg.get("api_key"):
        raise RuntimeError("Firebase is not configured. Add [firebase] secrets first.")
    response = requests.post(
        f"{AUTH_BASE}:{endpoint}?key={cfg['api_key']}",
        json=payload,
        timeout=15,
    )
    data = response.json()
    if response.status_code >= 400:
        code = data.get("error", {}).get("message", "Firebase authentication failed.")
        friendly = {
            "EMAIL_EXISTS": "An account with this email already exists.",
            "INVALID_PASSWORD": "Invalid email or password.",
            "EMAIL_NOT_FOUND": "Invalid email or password.",
            "WEAK_PASSWORD": "Password must be at least 6 characters.",
            "TOO_MANY_ATTEMPTS_TRY_LATER": "Too many attempts. Please try again later.",
        }.get(code, code)
        raise RuntimeError(friendly)
    return data


def _get_admin_app():
    if firebase_admin is None:
        raise RuntimeError("firebase-admin is not installed.")

    if firebase_admin._apps:
        return firebase_admin.get_app()

    cfg = _secrets()
    service_account = cfg.get("service_account")
    if not service_account:
        raise RuntimeError(
            "Firebase service account is missing. Add firebase.service_account as JSON."
        )
    if isinstance(service_account, str):
        service_account = json.loads(service_account)

    cred = credentials.Certificate(service_account)
    return firebase_admin.initialize_app(cred)


def _save_profile(uid: str, name: str, email: str, fcm_token: str = "") -> None:
    try:
        app = _get_admin_app()
        db = firestore.client(app)
        payload = {"uid": uid, "name": name, "email": email}
        if fcm_token:
            payload["fcm_token"] = fcm_token
        db.collection("users").document(uid).set(payload, merge=True)
    except Exception:
        # Authentication remains usable if Firestore/FCM is not configured.
        pass


def register_user(name: str, email: str, password: str, fcm_token: str = "") -> dict:
    if not name.strip():
        raise ValueError("Name is required.")
    data = _auth_request(
        "signUp",
        {"email": email.strip(), "password": password, "returnSecureToken": True},
    )
    user = {
        "uid": data["localId"],
        "name": name.strip(),
        "email": data.get("email", email.strip()),
        "id_token": data["idToken"],
        "refresh_token": data.get("refreshToken", ""),
    }
    _save_profile(user["uid"], user["name"], user["email"], fcm_token)
    return user


def login_user(email: str, password: str) -> dict:
    data = _auth_request(
        "signInWithPassword",
        {"email": email.strip(), "password": password, "returnSecureToken": True},
    )
    user = {
        "uid": data["localId"],
        "name": data.get("displayName") or data.get("email", email).split("@")[0],
        "email": data.get("email", email),
        "id_token": data["idToken"],
        "refresh_token": data.get("refreshToken", ""),
    }
    _save_profile(user["uid"], user["name"], user["email"])
    return user


def send_login_notification(fcm_token: str, display_name: str) -> bool:
    if not fcm_token or firebase_admin is None:
        return False
    try:
        app = _get_admin_app()
        message = messaging.Message(
            notification=messaging.Notification(
                title="Aura login successful",
                body=f"Welcome back, {display_name}.",
            ),
            token=fcm_token,
        )
        messaging.send(message, app=app)
        return True
    except Exception:
        return False
