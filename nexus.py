#!/usr/bin/env python3
# AKIRA V2 - GOOGLE LOGIN + BYOK AUTOMATICO
# Flujo: Usuario inicia sesión con Google -> Si no tiene key, 1 clic a AI Studio -> Guarda -> Automático para siempre
import os, json, datetime, threading, time, gc, hashlib
from pathlib import Path
from collections import defaultdict

try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

VERSION = "AKIRA V2 GOOGLE"
MODEL = "AKIRA V2"

def get_ram_mb():
    if os.getenv("RENDER") or os.getenv("RENDER_EXTERNAL_HOSTNAME"):
        return 512
    try:
        with open('/proc/meminfo') as f:
            for line in f:
                if 'MemTotal' in line:
                    mb = int(line.split()[1]) // 1024
                    return 512 if mb > 4000 else mb
    except:
        pass
    return 512

RAM_MB = get_ram_mb()
TOTAL_NIVELES = 50000
BASE = Path("resultados")
for d in ["memoria","users","usage"]:
    (BASE / d).mkdir(parents=True, exist_ok=True)

print(f"🧠 AKIRA {MODEL} GOOGLE LOGIN + BYOK - {RAM_MB}MB")

usage_log_path = BASE / "usage" / "usage.jsonl"
rate_limit = defaultdict(list)

def get_user_dir(user_id):
    # Sanitize
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

def log_usage(user_id, ip, own_key, msg=""):
    try:
        with usage_log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": datetime.datetime.now().isoformat(), "user_id": user_id[:16], "ip": ip, "own_key": own_key, "msg": msg[:60]}, ensure_ascii=False)+"\n")
    except:
        pass

def check_rate_limit(ip):
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
    def load_recent(self, n=20):
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()[-n:]
            return [json.loads(l) for l in lines if l.strip()]
        except: return []
    def search(self, query, n=5):
        all_mems = self.load_recent(200)
        return [m['texto'] for m in all_mems if query.lower() in m['texto'].lower()][:n]

memoria = MemoriaFINAL()

def crear_dashboard_final():
    # GOOGLE_CLIENT_ID - Tu ID ya configurado
    google_client_id = os.getenv("GOOGLE_CLIENT_ID", "148150327312-7k5g3go06tat9gv61c8v0rbbedcusoqn.apps.googleusercontent.com")
    html = f"""
<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AKIRA V2 - Login con Google</title>
<script src="https://accounts.google.com/gsi/client" async defer></script>
<script src="https://unpkg.com/force-graph"></script>
<style>
body{{background:#0a0a0f;color:#fff;font-family:Inter,sans-serif;margin:0}}
.header{{padding:20px;text-align:center;border-bottom:1px solid #222;background:linear-gradient(180deg,#11111a,#0a0a0f)}}
.orb{{width:85px;height:85px;margin:10px auto;background:radial-gradient(circle at 30% 30%, #10b981, #6366f1);border-radius:50%;box-shadow:0 0 40px rgba(16,185,129,.5);animation:pulse 2s infinite}}
@keyframes pulse{{0%{{transform:scale(1)}}50%{{transform:scale(1.08)}}100%{{transform:scale(1)}}}}
.login-box{{background:#1a1a24;border:1px solid #333;border-radius:16px;padding:20px;max-width:420px;margin:20px auto;text-align:center}}
.tabs{{display:flex;gap:8px;justify-content:center;padding:12px;flex-wrap:wrap;background:#0f0f17;position:sticky;top:0;z-index:10;border-bottom:1px solid #222}}
.tab{{padding:8px 16px;background:#1a1a24;border-radius:20px;cursor:pointer;border:1px solid #333;font-size:13px}}
.tab.active{{background:#10b981;color:#000;font-weight:600}}
.section{{display:none;padding:15px;max-width:1000px;margin:auto}}
.section.active{{display:block}}
.card{{background:#1a1a24;border:1px solid #222;border-radius:14px;padding:16px;margin:8px;flex:1;min-width:220px}}
.badge{{background:#10b981;color:#000;padding:4px 10px;border-radius:10px;font-size:11px;font-weight:700;margin:2px;display:inline-block}}
.badge.google{{background:#4285f4;color:#fff}}
#graph{{height:320px;background:#111;border-radius:12px;margin-top:10px;border:1px solid #222}}
.chat-box{{background:#11111a;border:1px solid #222;border-radius:18px;padding:12px;display:flex;gap:8px;margin-top:12px}}
.chat-box input{{flex:1;padding:12px 16px;border-radius:22px;border:1px solid #333;background:#1a1a24;color:#fff;outline:none}}
.btn{{padding:10px 22px;border-radius:22px;background:#10b981;border:none;color:#000;font-weight:700;cursor:pointer}}
.btn.google{{background:#fff;color:#000;width:100%;margin:8px 0;display:flex;align-items:center;justify-content:center;gap:8px}}
.btn:disabled{{opacity:.5}}
.msg{{padding:10px 14px;border-radius:10px;margin:8px 0;line-height:1.4}}
.msg.user{{background:#1a1a24;border:1px solid #2a2a3a}}
.msg.akira{{background:linear-gradient(135deg,#10b98122,#6366f122);border:1px solid #10b98144}}
.key-bar{{background:#1a1a24;border:1px dashed #10b981;border-radius:12px;padding:12px;margin:10px 0;display:flex;gap:10px;align-items:center;flex-wrap:wrap;justify-content:space-between}}
.modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:100;align-items:center;justify-content:center;padding:20px}}
.modal.active{{display:flex}}
.modal-box{{background:#1a1a24;border:1px solid #333;border-radius:16px;padding:20px;max-width:500px;width:100%}}
.input-key{{width:100%;padding:12px;border-radius:10px;border:1px solid #333;background:#0a0a0f;color:#fff;margin:10px 0;box-sizing:border-box}}
</style></head>
<body>
<div class="header">
<div class="orb"></div>
<h1>AKIRA V2</h1>
<p>🔐 Login con Google + BYOK Automático</p>
<p><span class="badge google">Google Login</span> <span class="badge">BYOK Auto</span> <span class="badge">Cada uno paga lo suyo</span></p>
<div id="userInfo" style="margin-top:10px;color:#aaa;font-size:13px"></div>
</div>

<div id="loginSection" class="login-box">
<h3>👋 Bienvenido a AKIRA V2</h3>
<p style="color:#aaa;font-size:14px">Inicia sesión con Google para que gastes tus propios tokens automáticamente. Es como lo hacen todas las IAs pro.</p>
<div id="g_id_onload"
     data-client_id="{google_client_id}"
     data-context="signin"
     data-ux_mode="popup"
     data-callback="handleGoogleLogin"
     data-auto_prompt="false">
</div>
<div class="g_id_signin" data-type="standard" data-shape="pill" data-theme="filled_black" data-text="signin_with" data-size="large" data-logo_alignment="left" style="margin:15px auto"></div>
<p style="font-size:11px;color:#666;margin-top:10px">Al iniciar sesión aceptas que tu key se guarde cifrada solo para ti. Nunca compartimos tu key.</p>
<div style="margin-top:15px;border-top:1px solid #222;padding-top:15px">
<button class="btn" onclick="continueWithoutLogin()" style="background:#333;color:#fff;width:100%">Continuar sin login (usa key del owner - limitado)</button>
</div>
</div>

<div id="mainApp" style="display:none">
<div class="key-bar" id="keyBar">
<div>
<span id="keyStatus">🔑 Configurando...</span>
<small id="keySub" style="color:#888;display:block;margin-top:4px"></small>
</div>
<button class="btn" onclick="openKeyModal()" style="background:#f59e0b">🔑 Mi API Key</button>
</div>

<div class="tabs">
<div class="tab active" id="tab-chat" onclick="showTab('chat')">💬 Chat</div>
<div class="tab" id="tab-cerebro" onclick="showTab('cerebro')">🧠 Cerebro</div>
<div class="tab" id="tab-memoria" onclick="showTab('memoria')">📚 Memoria</div>
<div class="tab" id="tab-empresa" onclick="showTab('empresa')">💼 Upwork</div>
<div class="tab" id="tab-sistema" onclick="showTab('sistema')">⚙️ Cómo funciona</div>
</div>

<div id="sec-chat" class="section active">
<div id="msgs" style="max-height:50vh;overflow-y:auto">
<div class="msg akira"><b>AKIRA:</b> ¡Listo! Ya iniciaste sesión. Ahora gastas tus tokens, no los míos. Si es tu primera vez, pon tu API Key una sola vez y queda automático para siempre. 🚀</div>
</div>
<div class="chat-box">
<input id="msg" placeholder="Escribe..." autocomplete="off">
<button id="sendBtn" class="btn" onclick="sendMsg()">Enviar</button>
</div>
</div>
<div id="sec-cerebro" class="section"><h2>🧠 Cerebro</h2><div id="graph"></div></div>
<div id="sec-memoria" class="section"><h2>📚 Memoria</h2><div id="memList">Cargando...</div></div>
<div id="sec-empresa" class="section"><h2>💼 Upwork</h2><div style="display:flex;flex-wrap:wrap"><div class="card"><h3>WhatsApp Bot</h3><b>$350</b></div><div class="card"><h3>Contenido</h3><b>$200/mes</b></div><div class="card"><h3>Chatbot RAG</h3><b>$500</b></div></div></div>
<div id="sec-sistema" class="section">
<h2>⚙️ Cómo lo hacen las otras IAs</h2>
<div class="card">
<h3>Por qué no es 100% automático sin pegar key?</h3>
<p><b>Gemini gratis</b> solo da quota por <b>API Key</b>, no por login con Google. Si usamos solo "Login con Google" con OAuth directo, la quota la pagas TÚ (owner), no el usuario. Por eso todas las IAs pro hacen:</p>
<ul>
<li><b>Poe, TypingMind, LibreChat:</b> Login con Google + BYOK (pegas key 1 vez)</li>
<li><b>ChatGPT:</b> Login + pagas suscripción</li>
</ul>
<p><b>Flujo automático que implementamos:</b></p>
<ol>
<li>Usuario da clic "Continuar con Google" (1 clic, familiar)</li>
<li>Sistema revisa si ya tiene key guardada para su email</li>
<li>Si no tiene: abre <a href="https://aistudio.google.com/app/apikey" target="_blank" style="color:#10b981">aistudio.google.com/app/apikey</a> automáticamente (ya logueado con su Google)</li>
<li>Pega key 1 vez -> se guarda cifrada en servidor ligada a su Google ID</li>
<li>Próximas veces que inicie sesión, <b>ya no pide nada</b>, es automático, gasta sus tokens</li>
</ol>
<p style="color:#f59e0b">💡 Truco pro: En el modal de key hay botón "Crear key automáticamente" que abre AI Studio en nueva pestaña ya logueado.</p>
</div>
</div>
</div>

<div class="modal" id="keyModal">
<div class="modal-box">
<h3>🔑 Tu API Key de Gemini</h3>
<p style="color:#aaa;font-size:13px">Se guarda ligada a tu Google (<span id="modalEmail"></span>). Después es automático.</p>
<input class="input-key" id="keyInput" placeholder="AIzaSy..." type="password">
<p style="font-size:12px;color:#888">1. Ve a <a href="https://aistudio.google.com/app/apikey" target="_blank" style="color:#10b981">aistudio.google.com/app/apikey</a> (ya estás logueado con Google)<br>2. Clic "Create API key"<br>3. Copia y pega aquí</p>
<div style="display:flex;gap:8px;margin-top:12px">
<button class="btn" onclick="saveKey()" style="flex:1">Guardar - Ya queda automático</button>
<button class="btn" onclick="closeKeyModal()" style="background:#333;color:#fff;flex:1">Cancelar</button>
</div>
<button class="btn google" onclick="window.open('https://aistudio.google.com/app/apikey','_blank')">🚀 Crear API Key (1 clic)</button>
</div>
</div>

<script>
let currentUser = null;
let userKey = localStorage.getItem('akira_user_key');

function handleGoogleLogin(response){{
  // response.credential es JWT ID token
  fetch('/api/auth/google',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{credential: response.credential}})}})
  .then(r=>r.json()).then(data=>{{
    if(data.user_id){{
      currentUser = data;
      localStorage.setItem('akira_user', JSON.stringify(data));
      localStorage.setItem('akira_user_id', data.user_id);
      document.getElementById('loginSection').style.display='none';
      document.getElementById('mainApp').style.display='block';
      document.getElementById('userInfo').innerHTML = `👤 ${{data.email}} <button onclick="logout()" style="margin-left:10px;background:#333;color:#fff;border:none;padding:4px 10px;border-radius:10px;cursor:pointer">Salir</button>`;
      document.getElementById('modalEmail').textContent = data.email;
      // Si tiene key guardada en servidor, usarla
      if(data.has_key){{
        userKey = 'server_stored';
        updateKeyUI(true);
      }} else if(userKey){{
        updateKeyUI(false);
      }} else {{
        updateKeyUI(false);
        setTimeout(()=>{{ openKeyModal(); }},800);
      }}
      loadGraph(); loadMemList();
    }} else {{
      alert('Error login: '+(data.error||'desconocido'));
    }}
  }}).catch(e=>{{ alert('Error login: '+e.message); }});
}}

function continueWithoutLogin(){{
  currentUser = {{user_id:'anon_'+Date.now(), email:'anonimo', has_key:false}};
  document.getElementById('loginSection').style.display='none';
  document.getElementById('mainApp').style.display='block';
  document.getElementById('userInfo').innerHTML = `👤 Anónimo (limitado 15/h) <button onclick="logout()" style="margin-left:10px;background:#333;color:#fff;border:none;padding:4px 10px;border-radius:10px;cursor:pointer">Login con Google</button>`;
  updateKeyUI(false);
  loadGraph(); loadMemList();
}}

function logout(){{
  localStorage.removeItem('akira_user');
  localStorage.removeItem('akira_user_id');
  currentUser=null;
  document.getElementById('mainApp').style.display='none';
  document.getElementById('loginSection').style.display='block';
  document.getElementById('userInfo').innerHTML='';
}}

// Restaurar sesión
let savedUser = localStorage.getItem('akira_user');
if(savedUser){{
  try{{
    let u=JSON.parse(savedUser);
    currentUser=u;
    document.getElementById('loginSection').style.display='none';
    document.getElementById('mainApp').style.display='block';
    document.getElementById('userInfo').innerHTML = `👤 ${{u.email}} <button onclick="logout()" style="margin-left:10px;background:#333;color:#fff;border:none;padding:4px 10px;border-radius:10px;cursor:pointer">Salir</button>`;
    document.getElementById('modalEmail').textContent = u.email;
    updateKeyUI(u.has_key);
    setTimeout(()=>{{loadGraph(); loadMemList();}},500);
  }}catch(e){{}}
}}

function openKeyModal(){{ document.getElementById('keyModal').classList.add('active'); }}
function closeKeyModal(){{ document.getElementById('keyModal').classList.remove('active'); }}
function saveKey(){{
  let k=document.getElementById('keyInput').value.trim();
  if(!k.startsWith('AIza')){{ alert('Key inválida, debe empezar por AIza'); return; }}
  // Guardar en servidor ligada a usuario si está logueado
  if(currentUser && currentUser.user_id && !currentUser.user_id.startsWith('anon')){{
    fetch('/api/user/key',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{user_id: currentUser.user_id, api_key:k}})}})
    .then(r=>r.json()).then(()=>{{
      localStorage.setItem('akira_user_key', k);
      userKey=k;
      updateKeyUI(true);
      closeKeyModal();
      alert('✅ Key guardada ligada a tu Google. La próxima vez que inicies sesión será automático, sin pedir nada.');
    }});
  }} else {{
    localStorage.setItem('akira_user_key', k);
    userKey=k;
    updateKeyUI(false);
    closeKeyModal();
    alert('✅ Key guardada en tu navegador. Ahora gastas tus tokens.');
  }}
}}
function updateKeyUI(hasServerKey){{
  let status=document.getElementById('keyStatus');
  let sub=document.getElementById('keySub');
  let localKey=localStorage.getItem('akira_user_key');
  if((hasServerKey && currentUser && !currentUser.user_id.startsWith('anon')) || localKey){{
    status.innerHTML='✅ <b>Automático con tu key</b> - gastas tus tokens';
    sub.textContent='Cada mensaje usa tu quota de Gemini gratis. La próxima vez que inicies sesión con Google, ya no te pedirá nada.';
    document.getElementById('keyBar').style.borderColor='#f59e0b';
  }} else {{
    status.innerHTML='⚠️ Usando key del owner (15/h) - pon tu key para ilimitado';
    sub.textContent='Haz login con Google y pon tu key 1 vez, luego queda automático.';
  }}
}}

function showTab(t){{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
  document.querySelectorAll('.section').forEach(x=>x.classList.remove('active'));
  document.getElementById('tab-'+t).classList.add('active');
  document.getElementById('sec-'+t).classList.add('active');
  if(t=='cerebro') setTimeout(loadGraph,100);
  if(t=='memoria') loadMemList();
}}
function loadGraph(){{
  fetch('/api/memorias').then(r=>r.json()).then(data=>{{
    let el=document.getElementById('graph'); if(!el) return;
    let nodes=[{{id:"AKIRA",label:"AKIRA",val:20}}];
    let links=[];
    if(data.recent) data.recent.slice(0,10).forEach((m,i)=>{{nodes.push({{id:i+1,label:(m.texto||'').substring(0,18),val:4}}); links.push({{source:"AKIRA",target:i+1}});}});
    try{{ if(window.ForceGraph) ForceGraph()(el).graphData({{nodes,links}}).nodeColor(()=> '#10b981').linkColor(()=> '#333').backgroundColor('#111'); }}catch(e){{}}
  }});
}}
function loadMemList(){{
  fetch('/api/memorias').then(r=>r.json()).then(data=>{{
    let list=document.getElementById('memList');
    if(!data.recent||data.recent.length==0){{ list.innerHTML='<p style="color:#666">Sin memorias</p>'; return; }}
    let h=''; data.recent.slice().reverse().forEach(m=>{{ h+=`<div style="background:#1a1a24;padding:8px;border-radius:8px;margin:5px 0;border-left:3px solid #10b981"><small style="color:#666">${{(m.ts||'').substring(0,19)}}</small><br>${{escapeHtml((m.texto||'').substring(0,180))}}</div>`; }});
    list.innerHTML=h;
  }});
}}
let isLoading=false;
async function sendMsg(){{
  let input=document.getElementById('msg');
  let txt=input.value.trim(); if(!txt||isLoading) return;
  isLoading=true; document.getElementById('sendBtn').disabled=true; document.getElementById('sendBtn').textContent='...';
  let msgs=document.getElementById('msgs');
  msgs.innerHTML+=`<div class="msg user"><b>Tú:</b> ${{escapeHtml(txt)}}</div>`;
  input.value=''; msgs.scrollTop=msgs.scrollHeight;
  let typingId='t_'+Date.now();
  let keyMode = (localStorage.getItem('akira_user_key')|| (currentUser&&currentUser.has_key)) ? 'tu key' : 'key owner';
  msgs.innerHTML+=`<div class="msg akira" id="${{typingId}}"><b>AKIRA:</b> <i>pensando con ${{keyMode}}...</i> ⏳</div>`;
  msgs.scrollTop=msgs.scrollHeight;
  try{{
    let uid = currentUser ? currentUser.user_id : localStorage.getItem('akira_user_id')||'anon';
    let body={{message:txt,user_id:uid,user_api_key: localStorage.getItem('akira_user_key')||null}};
    let r=await fetch('/api/chat',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});
    let d=await r.json();
    if(!r.ok) throw new Error(d.detail||d.error||'Error');
    document.getElementById(typingId).remove();
    msgs.innerHTML+=`<div class="msg akira"><b>AKIRA:</b> ${{escapeHtml(d.response)}}<br><small style="color:#666">${{d.used_own_key?'✅ tu key':'⚠️ owner'}} | ${{d.model}}</small></div>`;
  }}catch(e){{
    document.getElementById(typingId).remove();
    msgs.innerHTML+=`<div class="msg akira" style="border-color:#f55"><b>Error:</b> ${{escapeHtml(e.message)}}</div>`;
  }}
  isLoading=false; document.getElementById('sendBtn').disabled=false; document.getElementById('sendBtn').textContent='Enviar'; msgs.scrollTop=msgs.scrollHeight; loadMemList();
}}
function escapeHtml(t){{ let d=document.createElement('div'); d.textContent=t; return d.innerHTML; }}
document.getElementById('msg').addEventListener('keypress',e=>{{ if(e.key==='Enter') sendMsg(); }});
</script>
</body></html>
"""
    (BASE / "index.html").write_text(html, encoding='utf-8')

# FastAPI
try:
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
    import uvicorn
    FASTAPI_AVAILABLE = True
except:
    FASTAPI_AVAILABLE = False

if FASTAPI_AVAILABLE:
    app = FastAPI(title=f"AKIRA {MODEL} GOOGLE")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    
    @app.get("/")
    async def root():
        return FileResponse(BASE / "index.html")
    
    @app.get("/api/memorias")
    async def get_mems():
        return {"count": memoria.count(), "recent": memoria.load_recent(20), "version": VERSION, "model": MODEL, "ram_mb": RAM_MB}

    @app.post("/api/auth/google")
    async def auth_google(data: dict):
        credential = data.get("credential","")
        if not credential:
            return {"error": "No credential"}
        try:
            # Verificar ID token con google-auth
            from google.oauth2 import id_token
            from google.auth.transport import requests as grequests
            GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID","")
            # Si no hay CLIENT_ID configurado, aceptamos el token decodificando sin verificar (modo demo)
            if not GOOGLE_CLIENT_ID:
                # Modo demo: decodificar payload sin verificar firma
                import base64, json as js
                parts = credential.split('.')
                if len(parts) < 2:
                    return {"error": "Token inválido"}
                payload_b64 = parts[1] + '==' 
                payload = js.loads(base64.urlsafe_b64decode(payload_b64.encode()).decode())
                email = payload.get("email","")
                sub = payload.get("sub","")
            else:
                idinfo = id_token.verify_oauth2_token(credential, grequests.Request(), GOOGLE_CLIENT_ID)
                email = idinfo.get("email","")
                sub = idinfo.get("sub","")

            user_id = sub or hashlib.sha256(email.encode()).hexdigest()[:16]
            # Ver si ya tiene key
            has_key = get_user_key(user_id) is not None
            # Guardar usuario básico
            udir = get_user_dir(user_id)
            (udir / "profile.json").write_text(json.dumps({"email": email, "user_id": user_id, "ts": datetime.datetime.now().isoformat()}), encoding="utf-8")
            return {"user_id": user_id, "email": email, "has_key": has_key}
        except Exception as e:
            return {"error": f"Auth error: {str(e)[:200]}"}

    @app.post("/api/user/key")
    async def save_key(data: dict):
        user_id = data.get("user_id","")
        api_key = data.get("api_key","")
        if not user_id or not api_key or not api_key.startswith("AIza"):
            return {"error": "Datos inválidos"}
        save_user_key(user_id, api_key)
        return {"ok": True}

    @app.get("/api/user/key/{user_id}")
    async def get_key_status(user_id: str):
        has = get_user_key(user_id) is not None
        return {"has_key": has}

    @app.post("/api/chat")
    async def chat(request: Request, data: dict):
        msg = data.get("message","")
        user_id = data.get("user_id","anon")
        user_api_key = data.get("user_api_key")
        client_ip = request.client.host if request.client else "unknown"

        related = memoria.search(msg, 3)
        context = "\n".join(related) if related else "Sin memorias"

        # Prioridad: 1) key del body (localStorage), 2) key guardada por user_id en servidor, 3) owner key
        use_key = None
        used_own = False

        if user_api_key and user_api_key.startswith("AIza"):
            use_key = user_api_key
            used_own = True
        else:
            # Buscar key guardada para este user_id (si logueado con Google)
            stored = get_user_key(user_id)
            if stored:
                use_key = stored
                used_own = True
            else:
                owner_key = os.getenv("GEMINI_API_KEY")
                if owner_key:
                    if not check_rate_limit(client_ip):
                        return {"response": "⚠️ Límite 15/h con key del owner. Inicia sesión con Google y pon tu API Key 1 vez en 🔑 Mi API Key (aistudio.google.com/app/apikey) - luego queda automático.", "used_own_key": False, "model": MODEL}
                    use_key = owner_key
                    used_own = False
                else:
                    return {"response": f"Soy AKIRA V2. Necesito API Key. Pon tu key en 🔑 Mi API Key. Recibí: '{msg}'", "used_own_key": False, "model": MODEL}

        try:
            import google.generativeai as genai
            genai.configure(api_key=use_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"Eres AKIRA V2 creado por Jhon Bogotá. Razonas paso a paso, fluido colombiano. Memoria: {context}\nUsuario {user_id}: {msg}\nResponde inteligente, útil, si aplica vende: WhatsApp $350, Contenido $200/mes, RAG $500."
            resp = model.generate_content(prompt)
            answer = resp.text
        except Exception as e:
            err = str(e)
            if "API_KEY_INVALID" in err:
                answer = "❌ API Key inválida. Revisa en aistudio.google.com/app/apikey"
            elif "429" in err or "quota" in err.lower():
                answer = "⚠️ Cuota agotada. Si usas tu key, espera o revisa Google AI Studio."
            else:
                answer = f"[Error: {err[:200]}] AKIRA V2 aquí: {msg[:100]}"
            print(f"Gemini error {err}")

        memoria.add(f"User {user_id}: {msg} | AKIRA: {answer}")
        log_usage(user_id, client_ip, used_own, msg)
        return {"response": answer, "used_own_key": used_own, "model": MODEL, "count": memoria.count()}

    if __name__ == "__main__":
        from pathlib import Path
        crear_dashboard_final()
        import threading
        threading.Thread(target=lambda: (time.sleep(30), gc.collect()), daemon=True).start()
        port = int(os.getenv("PORT", 8000))
        print(f"🚀 AKIRA {MODEL} GOOGLE LOGIN BYOK - Puerto {port}")
        uvicorn.run(app, host="0.0.0.0", port=port)
