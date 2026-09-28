"""AKIRA V8 - Etapa B0: identidad real en el backend.

Responsabilidades (y nada más):
  1. Verificar el token de Google (firma, caducidad, audiencia, emisor).
  2. Emitir y validar una sesión propia firmada con HMAC-SHA256 y caducidad.
  3. Decidir is_owner SOLO en el servidor, a partir de un correo verificado.

Reglas:
  - Nunca imprime ni devuelve secretos.
  - Ninguna función lanza excepciones hacia el llamador: devuelven (dato, motivo).
  - Sin AKIRA_SESSION_SECRET (>= 32 caracteres) no se emiten sesiones.
"""
import base64
import hashlib
import hmac
import json
import os
import time

SESSION_TTL_SECONDS = 24 * 3600
GENERIC_EMAIL = "usuario@akira.com"
_GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")


def _b64e(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def owner_emails(default=()):
    """Correos de propietario: variable OWNER_EMAILS (separada por comas) o lista por defecto."""
    raw = os.getenv("OWNER_EMAILS", "").strip()
    source = raw.split(",") if raw else list(default)
    return {e.strip().lower() for e in source if e and e.strip()}


def owner_scope(sub):
    """Ámbito de memoria de un usuario verificado. Se deriva del 'sub' de Google, nunca del cliente."""
    return "g:" + str(sub)


def _secret():
    value = os.getenv("AKIRA_SESSION_SECRET", "").strip()
    return value.encode("utf-8") if len(value) >= 32 else None


def verifier_available():
    """True si las librerías de google-auth necesarias están instaladas."""
    try:
        from google.oauth2 import id_token  # noqa: F401
        from google.auth.transport import requests as g_requests  # noqa: F401
        return True
    except Exception:
        return False


def verify_google_credential(credential, client_id):
    """Verifica un ID token de Google. Devuelve (info, motivo). info = {sub, email} o None."""
    if not credential or not isinstance(credential, str):
        return None, "no_credential"
    if not client_id:
        return None, "client_id_not_configured"
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as g_requests
    except Exception:
        return None, "verifier_unavailable"
    try:
        claims = id_token.verify_oauth2_token(
            credential, g_requests.Request(), client_id, clock_skew_in_seconds=10
        )
    except ValueError:
        return None, "invalid_token"
    except Exception:
        return None, "verifier_error"
    if claims.get("iss") not in _GOOGLE_ISSUERS:
        return None, "bad_issuer"
    sub = claims.get("sub")
    email = claims.get("email")
    if not sub or not email or claims.get("email_verified") is not True:
        return None, "email_not_verified"
    return {"sub": str(sub), "email": str(email).lower()}, None


def issue_session(sub, email, now=None):
    """Devuelve (token, expira_epoch, motivo). Sin secreto configurado: (None, None, motivo)."""
    secret = _secret()
    if secret is None:
        return None, None, "session_secret_missing_or_short"
    issued = int(now if now is not None else time.time())
    payload = {"v": 1, "sub": str(sub), "email": str(email).lower(),
               "iat": issued, "exp": issued + SESSION_TTL_SECONDS}
    body = _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = _b64e(hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest())
    return body + "." + sig, payload["exp"], None


def verify_session(token, default_owner_emails=(), now=None):
    """Valida un token de sesión. Devuelve dict {sub,email,is_owner,owner_scope,exp} o None."""
    secret = _secret()
    if secret is None or not token or not isinstance(token, str):
        return None
    parts = token.split(".")
    if len(parts) != 2:
        return None
    body, sig = parts
    try:
        expected = _b64e(hmac.new(secret, body.encode("ascii"), hashlib.sha256).digest())
    except Exception:
        return None
    if not hmac.compare_digest(sig.encode("ascii", "ignore"), expected.encode("ascii")):
        return None
    try:
        payload = json.loads(_b64d(body))
    except Exception:
        return None
    if not isinstance(payload, dict) or payload.get("v") != 1:
        return None
    exp = payload.get("exp")
    sub = payload.get("sub")
    email = payload.get("email")
    current = now if now is not None else time.time()
    if not isinstance(exp, int) or exp <= current or not sub or not email:
        return None
    return {
        "sub": str(sub),
        "email": str(email),
        "is_owner": str(email).lower() in owner_emails(default_owner_emails),
        "owner_scope": owner_scope(sub),
        "exp": exp,
    }


def session_from_header(authorization, default_owner_emails=(), now=None):
    """Extrae y valida 'Authorization: Bearer <token>'. Devuelve la sesión o None."""
    if not authorization or not isinstance(authorization, str):
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return verify_session(token.strip(), default_owner_emails, now)
