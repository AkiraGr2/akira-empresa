#!/usr/bin/env python3
# AKIRA V2 - PUENTE LIVIANO - URL OFICIAL: https://akira-empresa.onrender.com
import os, json, datetime, threading, time, hashlib
from pathlib import Path
from collections import defaultdict

try:
    from dotenv import load_dotenv
    load_dotenv()
except: pass

VERSION = "AKIRA V2 PUENTE 24/7"
MODEL = "AKIRA V2"
OWNER_EMAILS = ["bjhon9161@gmail.com"]
OWNER_SECRET = os.getenv("OWNER_SECRET", "AKIRA_JHON_MASTER_2024")
OFFICIAL_URL = "https://akira-empresa.onrender.com"

BASE = Path("resultados")
for d in ["memoria","users","usage"]:
    (BASE / d).mkdir(parents=True, exist_ok=True)

usage_log_path = BASE / "usage" / "usage.jsonl"
rate_limit = defaultdict(list)

def get_user_dir(user_id):
    safe = hashlib.sha256(user_id.encode()).hexdigest()[:16]
    p = BASE / "users" / safe
    p.mkdir(parents=True, exist_ok=True)
    return p

def save_user_key(user_id, api_key, email=""):
    udir = get_user_dir(user_id)
    data = {"api_key": api_key, "email": email, "updated": datetime.datetime.now().isoformat()}
    (udir / "config.json").write_text(json.dumps(data), encoding="utf-8")

def get_user_key(user_id):
    try:
        udir = get_user_dir(user_id)
        cfg = json.loads((udir / "config.json").read_text(encoding="utf-8"))
        return cfg.get("api_key")
    except: return None

def check_rate_limit(ip, is_owner=False):
    if is_owner: return True
    now = time.time()
    rate_limit[ip] = [t for t in rate_limit[ip] if now - t < 3600]
    if len(rate_limit[ip]) >= 15: return False
    rate_limit[ip].append(now)
    return True

class MemoriaFINAL:
    def __init__(self):
        self.path = BASE / "memoria" / "akira_memoria_final.jsonl"
        if not self.path.exists(): self.path.write_text("", encoding="utf-8")
    def add(self, texto, tipo="episodica", importancia=5, tags=None):
        entry = {"texto": texto, "tipo": tipo, "importancia": importancia, "ts": datetime.datetime.now().isoformat(), "tags": tags or []}
        try:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except: pass
    def count(self):
        try: return len(self.path.read_text(encoding="utf-8").splitlines())
        except: return 0
    def load_recent(self, n=50):
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()[-n:]
            return [json.loads(l) for l in lines if l.strip()]
        except: return []
    def search(self, query, n=5):
        all_mems = self.load_recent(200)
        return [m['texto'] for m in all_mems if query.lower() in m['texto'].lower()][:n]

memoria = MemoriaFINAL()

def keep_alive_ping():
    import time, threading
    try: import requests
    except: return
    while True:
        time.sleep(600)
        try: requests.get(OFFICIAL_URL + '/health', timeout=10)
        except: pass

def crear_dashboard_final():
    google_client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip() or "148150327312-7k5g3go06tat9gv61c8v0rbbedcusoqn.apps.googleusercontent.com"
    html = f"""... (tu mismo HTML del puente que ya tienes, déjalo igual)..."""
    # por espacio no pego el HTML gigante, usa el mismo que ya tienes en GitHub
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    app = FastAPI()

    @app.get("/", response_class=HTMLResponse)
    async def root(): return HTMLResponse(content=open(__file__).read() if False else """{html}""".replace("{html}", html))

    @app.get("/health")
    async def health():
        return {"status":"ok","version":VERSION,"memoria":memoria.count(),"model":MODEL,"uptime":"24/7","url":OFFICIAL_URL,"official":OFFICIAL_URL,"puente":"liviano"}

    @app.get("/ping")
    async def ping(): return {"status":"ok"}

    #... tus endpoints /api/auth/google, /api/auth/owner, /api/user/key igual...

    @app.post("/api/chat")
    async def chat(request: Request, data: dict):
        msg = data.get("message",""); user_id = data.get("user_id","anon"); user_api_key = data.get("user_api_key",""); is_owner_flag = data.get("is_owner", False)
        client_ip = request.client.host if request.client else "unknown"
        related = memoria.search(msg, 3); context = "\\n".join(related) if related else "Sin memorias"
        is_owner = is_owner_flag
        try:
            udir = get_user_dir(user_id); pp = udir / "profile.json"
            if pp.exists():
                prof = json.loads(pp.read_text(encoding="utf-8"))
                if prof.get("is_owner") or prof.get("email","").lower() in [e.lower() for e in OWNER_EMAILS]: is_owner = True
        except: pass

        use_key = None
        if is_owner:
            owner_key = os.getenv("GEMINI_API_KEY","").strip()
            if owner_key and len(owner_key)>20: use_key = owner_key
        if not use_key and user_api_key and len(user_api_key.strip())>20: use_key = user_api_key.strip()
        if not use_key:
            stored = get_user_key(user_id)
            if stored and len(stored)>20: use_key = stored
            else:
                owner_key = os.getenv("GEMINI_API_KEY","").strip()
                if owner_key and len(owner_key)>20:
                    if not check_rate_limit(client_ip, is_owner=False):
                        return {"response": "⚠️ Límite 15/h. Pon tu API Key en 🔑 Mi API Key."}
                    use_key = owner_key

        if not use_key: return {"response": "❌ No hay API Key válida. Pon tu AQ. en Render > GEMINI_API_KEY."}

        # FIX DEFINITIVO: usar solo google-generativeai (evita el error de metaclasses)
        try:
            import google.generativeai as genai
            genai.configure(api_key=use_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"Eres AKIRA V2 creado por Jhon Bogotá. Memoria: {context}\\nUsuario {user_id}: {msg}\\nResponde útil."
            resp = model.generate_content(prompt)
            answer = resp.text
        except Exception as e:
            err = str(e)
            answer = f"[Error: {err[:300]}]"
            print(f"Gemini error {err}")

        memoria.add(f"User {user_id}: {msg} | AKIRA: {answer}")
        return {"response": answer, "model": MODEL, "is_owner": is_owner}

    return app

app = crear_dashboard_final()

if __name__ == "__main__":
    import uvicorn
    try: threading.Thread(target=keep_alive_ping, daemon=True).start()
    except: pass
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 AKIRA {VERSION} - Puerto {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)