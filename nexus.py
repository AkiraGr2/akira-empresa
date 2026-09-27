#!/usr/bin/env python3
# AKIRA V2 - PUENTE LIVIANO - URL OFICIAL: https://akira-empresa.onrender.com
# Render solo es puente -> Cerebro real en Google Gemini + GPU del usuario
import os, json, datetime, threading, time, hashlib
from pathlib import Path
from collections import defaultdict

try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

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
    except:
        return None

def check_rate_limit(ip, is_owner=False):
    if is_owner:
        return True
    now = time.time()
    rate_limit[ip] = [t for t in rate_limit[ip] if now - t < 3600]
    if len(rate_limit[ip]) >= 15:
        return False
    rate_limit[ip].append(now)
    return True

class MemoriaFINAL:
    def __init__(self):
        self.path = BASE / "memoria" / "akira_memoria_final.jsonl"
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")
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
    import time
    try:
        import requests
    except:
        return
    while True:
        time.sleep(600)
        try:
            url = os.getenv('RENDER_EXTERNAL_URL') or OFFICIAL_URL
            requests.get(url.rstrip('/') + '/health', timeout=10)
        except:
            pass

def crear_dashboard_final():
    google_client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip() or "148150327312-7k5g3go06tat9gv61c8v0rbbedcusoqn.apps.googleusercontent.com"
    html = f"""
<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AKIRA V2 • Puente 24/7</title>
<script src="https://accounts.google.com/gsi/client" async defer></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
:root{{--bg:#0b0b0e;--sidebar:#121216;--border:#23232a;--text:#ececf1;--muted:#8a8a93}}
body{{background:var(--bg);color:var(--text);font-family:Inter,sans-serif;height:100dvh;overflow:hidden;display:flex}}
.sidebar{{width:270px;background:var(--sidebar);border-right:1px solid var(--border);display:flex;flex-direction:column;padding:14px;gap:10px}}
.brand{{display:flex;align-items:center;gap:12px;padding:6px}}.orb{{width:40px;height:40px;border-radius:50%;background:radial-gradient(circle at 28% 22%, #10b981 0%, #6366f1 55%, #8b5cf6 90%);box-shadow:0 0 0 1px rgba(255,255,255,.1), 0 0 24px rgba(124,92,252,.55);animation:float 4s ease-in-out infinite}}
@keyframes float{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-3px)}}}}
.brand h1{{font-size:15.5px;font-weight:700}}.brand p{{font-size:11px;color:var(--muted)}}
.nav-btn{{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:10px;color:var(--muted);font-size:13.5px;cursor:pointer;background:transparent;width:100%;text-align:left;border:1px solid transparent}}.nav-btn.active{{background:#1e1e26;color:#fff;border-color:#2a2a36}}
.owner-badge{{background:linear-gradient(135deg,#f59e0b,#ef4444);color:#000;font-size:10px;font-weight:800;padding:3px 8px;border-radius:20px;margin-left:6px}}
.key-card{{margin-top:auto;background:#17171d;border:1px solid var(--border);border-radius:12px;padding:12px}}.dot{{width:8px;height:8px;border-radius:50%;background:#ef4444}}.dot.ok{{background:#10b981;box-shadow:0 0 8px #10b981}}.btn-key{{width:100%;margin-top:10px;padding:9px;border-radius:8px;background:#fff;color:#000;font-weight:600;font-size:12.5px;border:none;cursor:pointer}}
.user-box{{display:flex;align-items:center;gap:10px;padding:10px 8px;border-top:1px solid var(--border);margin-top:6px}}.av{{width:28px;height:28px;border-radius:50%;background:#2a2a36;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px}}.em{{font-size:12px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:130px}}
.main{{flex:1;display:flex;flex-direction:column}}.topbar{{height:52px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;padding:0 16px;background:var(--sidebar)}}.chat{{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:12px}}.msg{{max-width:75%;padding:12px 14px;border-radius:14px;font-size:13.5px;line-height:1.5}}.msg.user{{align-self:flex-end;background:#fff;color:#000}}.msg.akira{{align-self:flex-start;background:#1c1c22;border:1px solid var(--border)}}.inputbar{{padding:12px;border-top:1px solid var(--border);display:flex;gap:8px;background:var(--sidebar)}}.inputbar input{{flex:1;padding:12px 14px;border-radius:10px;border:1px solid var(--border);background:#0f0f12;color:#fff;outline:none}}.inputbar button{{padding:0 18px;border-radius:10px;border:none;background:#fff;color:#000;font-weight:700;cursor:pointer}}
</style></head><body>
<div class="sidebar"><div class="brand"><div class="orb" id="orb"></div><div><h1>AKIRA V2</h1><p>Puente 24/7</p></div></div>
<div class="nav"><button class="nav-btn active">💬 Chat</button><button class="nav-btn">🕸️ Cerebro <span id="memCount">{memoria.count()}</span></button></div>
<div class="key-card"><div style="display:flex;align-items:center;gap:8px"><div class="dot" id="dot"></div><span style="font-size:12px">API Key</span></div><button class="btn-key" onclick="showKeyModal()">🔑 Mi API Key</button></div>
<div class="user-box"><div class="av" id="av">A</div><div class="em" id="em">No logueado</div></div></div>
<div class="main"><div class="topbar"><span style="font-size:11px;color:var(--muted)">● 24/7 • {OFFICIAL_URL} • Puente liviano</span><div id="g_id_onload" data-client_id="{google_client_id}" data-callback="handleGoogle"></div><div class="g_id_signin" data-type="standard"></div></div>
<div class="chat" id="chat"></div><div class="inputbar"><input id="msg" placeholder="Habla con AKIRA..."/><button onclick="send()">➤</button></div></div>
<script>
let userId='anon', isOwner=false, userApiKey='';
function addMsg(t,cls){{const d=document.createElement('div');d.className='msg '+cls;d.textContent=t;document.getElementById('chat').appendChild(d);document.getElementById('chat').scrollTop=document.getElementById('chat').scrollHeight;}}
async function send(){{const i=document.getElementById('msg');const m=i.value.trim();if(!m)return;i.value='';addMsg(m,'user');document.getElementById('orb').style.filter='hue-rotate(90deg)';try{{const r=await fetch('/api/chat',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{message:m,user_id:userId,is_owner:isOwner,user_api_key:userApiKey}})}});const j=await r.json();addMsg(j.response||'[sin respuesta]','akira');}}catch(e){{addMsg('[Error: '+e+']','akira');}}document.getElementById('orb').style.filter='';}}
document.getElementById('msg').addEventListener('keydown',e=>{{if(e.key==='Enter')send();}});
async function handleGoogle(r){{const res=await fetch('/api/auth/google',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{credential:r.credential}})}});const d=await res.json();if(d.error){{alert(d.error);return;}}userId=d.user_id;isOwner=d.is_owner;document.getElementById('em').textContent=d.email;document.getElementById('av').textContent=d.email[0].toUpperCase();document.getElementById('dot').classList.add('ok');}}
function showKeyModal(){{const k=prompt('Pega tu API Key AIza... o AQ.');if(k){{userApiKey=k.trim();fetch('/api/user/key',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{user_id:userId,api_key:k}})}});document.getElementById('dot').classList.add('ok');}}}}
</script></body></html>
    """
    (BASE / "index.html").write_text(html, encoding="utf-8")
    from fastapi import FastAPI, Request
    from fastapi.responses import FileResponse
    app = FastAPI(title="AKIRA V2", version=VERSION)

    @app.get("/")
    async def root():
        return FileResponse(BASE / "index.html")

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": VERSION, "memoria": memoria.count(), "model": MODEL, "uptime": "24/7", "url": OFFICIAL_URL, "official": OFFICIAL_URL, "puente": "liviano"}

    @app.get("/ping")
    async def ping():
        return {"pong": True, "ts": datetime.datetime.now().isoformat(), "url": OFFICIAL_URL}

    @app.get("/api/memorias")
    async def get_memorias():
        return {"count": memoria.count(), "recent": memoria.load_recent(100), "official_url": OFFICIAL_URL}

    @app.post("/api/auth/google")
    async def auth_google(data: dict):
        try:
            from google.oauth2 import id_token
            from google.auth.transport import requests as grequests
            token = data.get("credential","")
            if not token:
                return {"error": "No token"}
            idinfo = id_token.verify_oauth2_token(token, grequests.Request(), google_client_id)
            email = idinfo.get("email","")
            sub = idinfo.get("sub","")
            user_id = sub or hashlib.sha256(email.encode()).hexdigest()[:16]
            is_owner = email.lower() in [e.lower() for e in OWNER_EMAILS]
            has_key = True if is_owner else (get_user_key(user_id) is not None)
            udir = get_user_dir(user_id)
            (udir / "profile.json").write_text(json.dumps({"email": email, "user_id": user_id, "is_owner": is_owner, "ts": datetime.datetime.now().isoformat()}), encoding="utf-8")
            return {"user_id": user_id, "email": email, "has_key": has_key, "is_owner": is_owner}
        except Exception as e:
            return {"error": f"Auth error: {str(e)[:200]}"}

    @app.post("/api/auth/owner")
    async def auth_owner(data: dict):
        secret = data.get("secret","").strip()
        if secret!= OWNER_SECRET:
            return {"ok": False, "error": "Secreto incorrecto"}
        owner_email = OWNER_EMAILS[0]
        user_id = hashlib.sha256(owner_email.encode()).hexdigest()[:16]
        udir = get_user_dir(user_id)
        (udir / "profile.json").write_text(json.dumps({"email": owner_email, "user_id": user_id, "is_owner": True, "ts": datetime.datetime.now().isoformat()}), encoding="utf-8")
        return {"ok": True, "user_id": user_id, "email": owner_email, "has_key": True, "is_owner": True}

    @app.post("/api/user/key")
    async def save_key(data: dict):
        user_id = data.get("user_id","").strip()
        api_key = data.get("api_key","").strip()
        if not api_key or len(api_key) < 20:
            return {"error": "Key muy corta"}
        save_user_key(user_id, api_key)
        return {"ok": True}

    @app.post("/api/chat")
    async def chat(request: Request, data: dict):
        msg = data.get("message","")
        user_id = data.get("user_id","anon")
        user_api_key = data.get("user_api_key","")
        is_owner_flag = data.get("is_owner", False)
        client_ip = request.client.host if request.client else "unknown"
        related = memoria.search(msg, 3)
        context = "\\n".join(related) if related else "Sin memorias"
        is_owner = is_owner_flag
        try:
            udir = get_user_dir(user_id)
            pp = udir / "profile.json"
            if pp.exists():
                prof = json.loads(pp.read_text(encoding="utf-8"))
                if prof.get("is_owner") or prof.get("email","").lower() in [e.lower() for e in OWNER_EMAILS]:
                    is_owner = True
        except:
            pass
        use_key = None
        if is_owner:
            owner_key = os.getenv("GEMINI_API_KEY","").strip()
            if owner_key and len(owner_key) > 20:
                use_key = owner_key
            else:
                return {"response": "👑 Eres creador pero tu GEMINI_API_KEY en Render está vacía. Pega tu AQ. completa en Render > GEMINI_API_KEY y Save.", "is_owner": True}
        elif user_api_key and len(user_api_key.strip()) > 20:
            use_key = user_api_key.strip()
        else:
            stored = get_user_key(user_id)
            if stored and len(stored) > 20:
                use_key = stored
            else:
                owner_key = os.getenv("GEMINI_API_KEY","").strip()
                if owner_key and len(owner_key) > 20:
                    if not check_rate_limit(client_ip, is_owner=False):
                        return {"response": "⚠️ Límite 15/h con key del owner. Pon tu API Key en 🔑 Mi API Key."}
                    use_key = owner_key
                else:
                    return {"response": "❌ No hay API Key válida. Pon tu key AQ. o AIza... en 🔑 Mi API Key."}
        try:
            answer = ""
            if use_key.startswith("AQ."):
                try:
                    from google import genai
                    client = genai.Client(api_key=use_key)
                    prompt = f"Eres AKIRA V2 creado por Jhon Bogotá. Memoria: {context}\\nUsuario {user_id}: {msg}\\nResponde útil."
                    resp = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
                    answer = resp.text
                except:
                    import google.generativeai as genai_old
                    genai_old.configure(api_key=use_key)
                    model = genai_old.GenerativeModel('gemini-1.5-flash')
                    resp = model.generate_content(f"Eres AKIRA V2. Memoria: {context}\\nUsuario: {msg}")
                    answer = resp.text
            else:
                import google.generativeai as genai
                genai.configure(api_key=use_key)
                model = genai.GenerativeModel('gemini-1.5-flash')
                resp = model.generate_content(f"Eres AKIRA V2. Memoria: {context}\\nUsuario: {msg}")
                answer = resp.text
        except Exception as e:
            answer = f"[Error: {str(e)[:200]}]"
        memoria.add(f"User {user_id}: {msg} | AKIRA: {answer}")
        return {"response": answer, "model": MODEL, "is_owner": is_owner}

    return app

app = crear_dashboard_final()

def _start_keep_alive():
    try:
        threading.Thread(target=keep_alive_ping, daemon=True).start()
    except:
        pass
_start_keep_alive()

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 {MODEL} {VERSION} - {OFFICIAL_URL} - Puerto {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
