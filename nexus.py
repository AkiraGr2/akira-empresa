#!/usr/bin/env python3
# AKIRA V2 - GOOGLE LOGIN + BYOK AUTOMATICO - UI MODERNA CHATGPT/CLAUDE
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
    _env_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    google_client_id = _env_id if _env_id else "148150327312-7k5g3go06tat9gv61c8v0rbbedcusoqn.apps.googleusercontent.com"
    html = f"""
<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AKIRA V2</title>
<script src="https://accounts.google.com/gsi/client" async defer></script>
<script src="https://unpkg.com/force-graph"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Geist:wght@400;500&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
:root{{--bg:#0e0e10;--sidebar:#151518;--sidebar-hover:#1e1e22;--border:#232326;--text:#ececec;--muted:#9a9aa0;--accent:#10a37f;--accent2:#6d5df6}}
body{{background:var(--bg);color:var(--text);font-family:Inter,system-ui,sans-serif;height:100vh;overflow:hidden;display:flex}}
.sidebar{{width:260px;background:var(--sidebar);border-right:1px solid var(--border);display:flex;flex-direction:column;padding:14px;gap:10px;transition:transform .3s}}
.brand{{display:flex;align-items:center;gap:12px;padding:8px 6px}}
.orb-wrap{{position:relative;width:36px;height:36px;flex-shrink:0}}
.orb{{width:36px;height:36px;border-radius:50%;background:radial-gradient(circle at 30% 25%, #10b981 0%, #06b6d4 25%, #6366f1 60%, #8b5cf6 100%);box-shadow:0 0 0 1px rgba(255,255,255,.08), 0 0 20px rgba(99,102,241,.5), inset 0 1px 1px rgba(255,255,255,.4);animation:float 4s ease-in-out infinite;position:relative;z-index:2}}
.orb::after{{content:'';position:absolute;inset:-12px;background:radial-gradient(circle, rgba(99,102,241,.35), transparent 70%);filter:blur(8px);z-index:-1;animation:pulseGlow 2.5s ease-in-out infinite alternate}}
.orb.thinking{{animation:float 0.8s ease-in-out infinite, spinHue 2s linear infinite;}}
@keyframes float{{0%,100%{{transform:translateY(0) scale(1)}}50%{{transform:translateY(-3px) scale(1.03)}}}}
@keyframes pulseGlow{{0%{{opacity:.5;transform:scale(.9)}}100%{{opacity:1;transform:scale(1.15)}}}}
@keyframes spinHue{{0%{{filter:hue-rotate(0deg)}}100%{{filter:hue-rotate(60deg)}}}}
.brand h1{{font-size:16px;font-weight:700;letter-spacing:-.02em}}
.brand p{{font-size:11px;color:var(--muted);margin-top:1px}}
.nav{{display:flex;flex-direction:column;gap:4px;margin-top:8px}}
.nav-btn{{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:10px;border:1px solid transparent;color:var(--muted);font-size:13.5px;font-weight:500;cursor:pointer;background:transparent;transition:all .2s;text-align:left;width:100%}}
.nav-btn:hover{{background:var(--sidebar-hover);color:var(--text);border-color:var(--border)}}
.nav-btn.active{{background:#1e1e22;color:var(--text);border-color:#2a2a30}}
.nav-btn .ico{{font-size:16px}}
.key-status{{margin-top:auto;background:#1c1c20;border:1px solid var(--border);border-radius:12px;padding:12px}}
.key-status small{{color:var(--muted);font-size:11px;display:block;margin-top:4px;line-height:1.3}}
.btn-key{{width:100%;margin-top:8px;padding:8px;border-radius:8px;background:var(--accent);color:#000;font-weight:600;font-size:12.5px;border:none;cursor:pointer}}
.btn-key.sec{{background:#2a2a30;color:var(--text)}}
.user-box{{display:flex;align-items:center;gap:10px;padding:10px 8px;border-top:1px solid var(--border);margin-top:10px}}
.user-box .avatar{{width:28px;height:28px;border-radius:50%;background:#2a2a30;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600}}
.user-box .email{{font-size:12px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:140px}}
.main{{flex:1;display:flex;flex-direction:column;overflow:hidden;position:relative}}
.topbar{{height:52px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;padding:0 20px;background:rgba(14,14,16,.8);backdrop-filter:blur(12px);z-index:5}}
.topbar h2{{font-size:14px;font-weight:600;color:var(--text);display:flex;align-items:center;gap:10px}}
.dot{{width:8px;height:8px;border-radius:50%;background:#10b981;box-shadow:0 0 8px #10b981}}
.login-screen{{flex:1;display:flex;align-items:center;justify-content:center;padding:20px;background:radial-gradient(1200px 600px at 50% -10%, rgba(99,102,241,.15), transparent), var(--bg)}}
.login-card{{background:#17171a;border:1px solid var(--border);border-radius:20px;padding:32px;width:100%;max-width:400px;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.5)}}
.login-card .orb-big{{width:72px;height:72px;margin:0 auto 18px;background:radial-gradient(circle at 30% 25%, #10b981, #6366f1, #8b5cf6);border-radius:50%;box-shadow:0 0 0 1px rgba(255,255,255,.1), 0 0 40px rgba(99,102,241,.6);animation:float 3s ease-in-out infinite}}
.login-card h3{{font-size:22px;font-weight:700;letter-spacing:-.02em;margin-bottom:6px}}
.login-card .sub{{font-size:13.5px;color:var(--muted);line-height:1.5;margin-bottom:20px}}
.g_id_signin{{margin:14px auto}}
.legal{{font-size:11px;color:#666;margin-top:14px;line-height:1.4}}
.btn-ghost{{width:100%;margin-top:16px;padding:10px;border-radius:10px;background:transparent;border:1px solid var(--border);color:var(--muted);font-size:13px;cursor:pointer}}
.btn-ghost:hover{{background:var(--sidebar-hover);color:var(--text)}}
.chat-wrap{{flex:1;display:flex;flex-direction:column;overflow:hidden}}
.msgs{{flex:1;overflow-y:auto;padding:0;scroll-behavior:smooth}}
.msgs-inner{{max-width:780px;margin:0 auto;width:100%;padding:24px 20px 20px}}
.msg-row{{display:flex;gap:14px;padding:18px 0;border-bottom:1px solid rgba(255,255,255,.04)}}
.msg-row.user{{flex-direction:row-reverse}}
.msg-row.user .bubble{{background:#2a2a30;border-radius:20px 20px 4px 20px;padding:12px 16px;max-width:68%;font-size:14.5px;line-height:1.5}}
.msg-row.akira .avatar{{width:30px;height:30px;border-radius:50%;background:radial-gradient(circle at 30% 25%, #10b981, #6366f1);flex-shrink:0;box-shadow:0 0 0 1px rgba(255,255,255,.1)}}
.msg-row.akira .bubble{{flex:1;font-size:14.5px;line-height:1.65;color:var(--text)}}
.msg-row.akira .bubble b{{color:#fff}}
.typing{{display:flex;gap:4px;padding:8px 0}}
.typing span{{width:6px;height:6px;border-radius:50%;background:var(--muted);animation:typing 1.4s infinite}}
.typing span:nth-child(2){{animation-delay:.2s}} .typing span:nth-child(3){{animation-delay:.4s}}
@keyframes typing{{0%,80%,100%{{opacity:.3;transform:translateY(0)}}40%{{opacity:1;transform:translateY(-4px)}}}}
.input-bar{{padding:12px 20px 20px;background:linear-gradient(transparent, var(--bg) 20%);border-top:1px solid transparent}}
.input-inner{{max-width:780px;margin:0 auto;background:#1e1e22;border:1px solid #2a2a30;border-radius:24px;padding:8px 10px 8px 18px;display:flex;align-items:flex-end;gap:10px;box-shadow:0 4px 20px rgba(0,0,0,.3);transition:border-color .2s}}
.input-inner:focus-within{{border-color:#3a3a44}}
.input-inner textarea{{flex:1;background:transparent;border:none;color:var(--text);font-size:15px;resize:none;outline:none;max-height:160px;min-height:24px;line-height:1.5;font-family:Inter,sans-serif;padding:6px 0}}
.btn-send{{width:32px;height:32px;border-radius:50%;background:#fff;color:#000;border:none;display:flex;align-items:center;justify-content:center;cursor:pointer;flex-shrink:0;transition:all .2s}}
.btn-send:disabled{{opacity:.3;cursor:not-allowed}}
.btn-send:hover:not(:disabled){{transform:scale(1.05)}}
.section{{display:none;flex:1;overflow-y:auto;padding:24px}}
.section.active{{display:block}}
.card{{background:#17171a;border:1px solid var(--border);border-radius:14px;padding:16px;margin-bottom:12px}}
#graph{{height:360px;background:#111113;border-radius:14px;border:1px solid var(--border)}}
.modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);backdrop-filter:blur(8px);z-index:100;align-items:center;justify-content:center;padding:20px}}
.modal.active{{display:flex}}
.modal-box{{background:#1c1c20;border:1px solid #2a2a30;border-radius:16px;padding:24px;max-width:440px;width:100%;box-shadow:0 20px 60px rgba(0,0,0,.6)}}
.modal-box h3{{font-size:16px;font-weight:600;margin-bottom:8px}}
.modal-box p{{font-size:13px;color:var(--muted);line-height:1.5}}
.input-key{{width:100%;padding:12px 14px;border-radius:10px;border:1px solid #2a2a30;background:#0e0e10;color:#fff;margin:14px 0;font-family:Geist Mono,monospace;font-size:13px;outline:none}}
.input-key:focus{{border-color:#3a3a44}}
.btn{{padding:10px 18px;border-radius:10px;border:none;font-weight:600;font-size:13px;cursor:pointer;transition:all .2s}}
.btn.primary{{background:#fff;color:#000;flex:1}} .btn.sec{{background:#2a2a30;color:#fff;flex:1}} .btn.full{{width:100%;margin-top:10px;background:transparent;border:1px solid #2a2a30;color:var(--muted)}}
@media(max-width:800px){{.sidebar{{position:fixed;inset:0 40% 0 0;z-index:20;transform:translateX(-100%)}}.sidebar.open{{transform:translateX(0)}} .topbar .menu{{display:block}} }} .menu{{display:none;background:transparent;border:none;color:var(--text);font-size:20px;cursor:pointer}}
</style></head>
<body>
<div class="sidebar" id="sidebar">
  <div class="brand">
    <div class="orb-wrap"><div class="orb" id="orb"></div></div>
    <div><h1>AKIRA V2</h1><p>by Jhon • Bogotá</p></div>
  </div>
  <div class="nav">
    <button class="nav-btn active" id="btn-chat" onclick="showTab('chat')"><span class="ico">💬</span> Chat</button>
    <button class="nav-btn" id="btn-cerebro" onclick="showTab('cerebro')"><span class="ico">🧠</span> Cerebro</button>
    <button class="nav-btn" id="btn-memoria" onclick="showTab('memoria')"><span class="ico">📚</span> Memoria</button>
    <button class="nav-btn" id="btn-empresa" onclick="showTab('empresa')"><span class="ico">💼</span> Servicios</button>
    <button class="nav-btn" id="btn-sistema" onclick="showTab('sistema')"><span class="ico">⚙️</span> Sistema</button>
  </div>
  <div class="key-status">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <span style="font-size:12px;font-weight:600" id="keyStatus">🔑 Sin key</span>
      <span class="dot" id="keyDot" style="background:#ef4444;box-shadow:0 0 8px #ef4444"></span>
    </div>
    <small id="keySub">Inicia con Google y guarda tu API key 1 vez</small>
    <button class="btn-key" onclick="openKeyModal()">Gestionar API Key</button>
  </div>
  <div class="user-box" id="userBox" style="display:none">
    <div class="avatar" id="userAvatar">J</div>
    <div style="flex:1;min-width:0">
      <div class="email" id="userEmail">--</div>
      <div style="font-size:10px;color:var(--muted)">BYOK activo</div>
    </div>
    <button onclick="logout()" style="background:transparent;border:none;color:var(--muted);cursor:pointer;font-size:14px">↪</button>
  </div>
</div>

<div class="main">
  <div class="topbar">
    <h2><button class="menu" onclick="document.getElementById('sidebar').classList.toggle('open')">☰</button> <span id="topTitle">Chat</span> <span class="dot" id="topDot"></span></h2>
    <div id="userInfoTop" style="font-size:12px;color:var(--muted)"></div>
  </div>

  <div id="loginSection" class="login-screen">
    <div class="login-card">
      <div class="orb-big" id="orbBig"></div>
      <h3>Bienvenido a AKIRA</h3>
      <p class="sub">Tu IA con memoria infinita. Inicia sesión para que use <b>tus tokens</b>, no los míos. Como ChatGPT Pro, pero BYOK.</p>
      <div id="g_id_onload"
           data-client_id="{google_client_id}"
           data-context="signin"
           data-ux_mode="popup"
           data-callback="handleGoogleLogin"
           data-auto_prompt="false">
      </div>
      <div class="g_id_signin" data-type="standard" data-shape="pill" data-theme="filled_black" data-text="signin_with" data-size="large" data-logo_alignment="left" style="width:100%"></div>
      <p class="legal">Tu key se guarda cifrada ligada a tu Google. Nunca la compartimos. Funciona con keys <code>AIza...</code> y <code>AQ....</code></p>
      <button class="btn-ghost" onclick="continueWithoutLogin()">Continuar sin login (owner key - 15/h)</button>
    </div>
  </div>

  <div id="mainApp" style="display:none;flex:1;flex-direction:column;overflow:hidden">
    <div id="sec-chat" class="section active" style="padding:0;display:flex;flex-direction:column">
      <div class="chat-wrap">
        <div class="msgs" id="msgs"><div class="msgs-inner" id="msgsInner">
          <div class="msg-row akira"><div class="avatar"></div><div class="bubble"><b>AKIRA V2</b> listo. Ya iniciaste sesión. Pregúntame lo que quieras — tengo memoria de tus chats anteriores y ahora gasto tus tokens.<br><br><span style="color:var(--muted);font-size:13px">Tip: escribe y presiona Enter. Shift+Enter para salto de línea.</span></div></div>
        </div></div>
        <div class="input-bar">
          <div class="input-inner">
            <textarea id="msg" placeholder="Pregúntale a AKIRA..." rows="1"></textarea>
            <button id="sendBtn" class="btn-send" onclick="sendMsg()">↑</button>
          </div>
        </div>
      </div>
    </div>

    <div id="sec-cerebro" class="section"><h3 style="margin-bottom:12px">🧠 Cerebro</h3><div id="graph"></div><p style="margin-top:12px;color:var(--muted);font-size:13px">Visualización de tu grafo de conocimiento.</p></div>
    <div id="sec-memoria" class="section"><h3>📚 Memoria</h3><div id="memList" style="margin-top:12px">Cargando...</div></div>
    <div id="sec-empresa" class="section"><h3>💼 Servicios</h3><div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;margin-top:14px"><div class="card"><h4>WhatsApp Bot</h4><p style="color:var(--muted);font-size:13px;margin:6px 0">Automatización completa</p><b>$350 USD</b></div><div class="card"><h4>Contenido IA</h4><p style="color:var(--muted);font-size:13px;margin:6px 0">Posts + reels</p><b>$200/mes</b></div><div class="card"><h4>Chatbot RAG</h4><p style="color:var(--muted);font-size:13px;margin:6px 0">Con tus docs</p><b>$500 USD</b></div></div></div>
    <div id="sec-sistema" class="section"><h3>⚙️ Cómo funciona</h3><div class="card" style="margin-top:12px"><h4>BYOK Automático (como Poe / TypingMind)</h4><p style="color:var(--muted);font-size:13px;line-height:1.6;margin-top:8px">Gemini solo da quota por API Key, no por OAuth. Por eso: 1) Logueas con Google → 2) Creas tu key en AI Studio (formato <code>AIza...</code> o <code>AQ...</code>) → 3) La pegas 1 vez → queda guardada ligada a tu Google ID → 4) Próximas veces entra automático. El orbe arriba respira y cambia de color cuando estoy pensando.</p></div></div>
  </div>
</div>

<div class="modal" id="keyModal">
  <div class="modal-box">
    <h3>🔑 Tu API Key</h3>
    <p>Se guarda ligada a <span id="modalEmail" style="color:#fff;font-weight:600">tu Google</span>. Después es automático. Acepta <code>AIza...</code> y <code>AQ...</code></p>
    <input class="input-key" id="keyInput" placeholder="AIzaSy... o AQ.Ab8..." type="password">
    <p style="font-size:11px;color:#666">1. Ve a <a href="https://aistudio.google.com/app/apikey" target="_blank" style="color:#8b9cff">aistudio.google.com/app/apikey</a><br>2. Create API key → Copiar<br>3. Pegar aquí</p>
    <div style="display:flex;gap:8px;margin-top:14px">
      <button class="btn primary" onclick="saveKey()">Guardar</button>
      <button class="btn sec" onclick="closeKeyModal()">Cancelar</button>
    </div>
    <button class="btn full" onclick="window.open('https://aistudio.google.com/app/apikey','_blank')">🚀 Crear API Key (1 clic)</button>
  </div>
</div>

<script>
let currentUser = null;
let userKey = localStorage.getItem('akira_user_key');

function handleGoogleLogin(response){{
  const orb = document.getElementById('orb'); if(orb) orb.classList.add('thinking');
  fetch('/api/auth/google',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{credential: response.credential}})}})
  .then(r=>r.json()).then(data=>{{
    if(data.user_id){{
      currentUser = data;
      localStorage.setItem('akira_user', JSON.stringify(data));
      localStorage.setItem('akira_user_id', data.user_id);
      document.getElementById('loginSection').style.display='none';
      document.getElementById('mainApp').style.display='flex';
      document.getElementById('userBox').style.display='flex';
      document.getElementById('userEmail').textContent = data.email;
      document.getElementById('userAvatar').textContent = data.email[0].toUpperCase();
      document.getElementById('userInfoTop').textContent = data.email;
      document.getElementById('modalEmail').textContent = data.email;
      if(orb) orb.classList.remove('thinking');
      if(data.has_key){{
        userKey = 'server_stored';
        updateKeyUI(true);
      }} else if(userKey){{
        updateKeyUI(true);
      }} else {{
        updateKeyUI(false);
        setTimeout(()=>openKeyModal(),600);
      }}
    }} else {{
      alert('Error login: '+(data.error||'desconocido'));
      if(orb) orb.classList.remove('thinking');
    }}
  }});
}}

function continueWithoutLogin(){{
  document.getElementById('loginSection').style.display='none';
  document.getElementById('mainApp').style.display='flex';
  document.getElementById('topTitle').textContent='Chat (owner key limitada)';
  updateKeyUI(false);
}}

function logout(){{
  localStorage.removeItem('akira_user'); localStorage.removeItem('akira_user_id');
  location.reload();
}}

function updateKeyUI(has){{
  const status = document.getElementById('keyStatus');
  const sub = document.getElementById('keySub');
  const dot = document.getElementById('keyDot');
  const topDot = document.getElementById('topDot');
  if(has){{
    status.textContent='🔑 Key guardada'; sub.textContent='BYOK activo - gastas tus tokens'; dot.style.background='#10b981'; dot.style.boxShadow='0 0 8px #10b981'; if(topDot){{topDot.style.background='#10b981'}}
  }} else {{
    status.textContent='🔑 Sin key'; sub.textContent='Pon tu API key 1 vez'; dot.style.background='#ef4444'; dot.style.boxShadow='0 0 8px #ef4444'; if(topDot){{topDot.style.background='#ef4444'}}
  }}
}}

function openKeyModal(){{document.getElementById('keyModal').classList.add('active');}}
function closeKeyModal(){{document.getElementById('keyModal').classList.remove('active');}}

function saveKey(){{
  const k = document.getElementById('keyInput').value.trim();
  if(k.length < 20){{alert('Key muy corta');return;}}
  if(!k.startsWith('AIza') && !k.startsWith('AQ.')){{if(!confirm('La key no empieza con AIza ni AQ. ¿Guardarla igual?')) return;}}
  const uid = localStorage.getItem('akira_user_id') || 'anon';
  if(uid==='anon'){{
    localStorage.setItem('akira_user_key', k);
    userKey = k;
    updateKeyUI(true);
    closeKeyModal();
    return;
  }}
  fetch('/api/user/key',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{user_id:uid,api_key:k}})}})
  .then(r=>r.json()).then(d=>{{
    if(d.ok){{ userKey=k; localStorage.setItem('akira_user_key', k); updateKeyUI(true); closeKeyModal(); }}
    else alert(d.error||'Error');
  }});
}}

function showTab(name){{
  document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
  document.getElementById('sec-'+name).classList.add('active');
  document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
  const b = document.getElementById('btn-'+name); if(b) b.classList.add('active');
  document.getElementById('topTitle').textContent = name.charAt(0).toUpperCase()+name.slice(1);
  document.getElementById('sidebar').classList.remove('open');
  if(name==='memoria') loadMems();
  if(name==='cerebro') initGraph();
}}

function loadMems(){{
  fetch('/api/memorias').then(r=>r.json()).then(d=>{{
    const el=document.getElementById('memList');
    el.innerHTML = `<div style="color:var(--muted);font-size:13px;margin-bottom:10px">${{d.count}} memorias</div>` + d.recent.map(m=>`<div class="card" style="font-size:13px">${{escapeHtml(m.texto||JSON.stringify(m))}}</div>`).join('');
  }});
}}

let graphInited=false;
function initGraph(){{
  if(graphInited) return; graphInited=true;
  try{{
    const el=document.getElementById('graph');
    const g=ForceGraph()(el).graphData({{nodes:[{{id:'AKIRA'}},{{id:'Tú'}}],links:[{{source:'AKIRA',target:'Tú'}}]}}).nodeColor(()=>'#6366f1');
  }}catch(e){{}}
}}

function sendMsg(){{
  const inp=document.getElementById('msg');
  const txt=inp.value.trim(); if(!txt) return;
  const orb=document.getElementById('orb'); if(orb) orb.classList.add('thinking');
  addMsg(txt,'user');
  inp.value=''; inp.style.height='24px';
  const typingId = addTyping();
  const uid = localStorage.getItem('akira_user_id') || 'anon';
  const uk = localStorage.getItem('akira_user_key') || '';
  fetch('/api/chat',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{message:txt,user_id:uid,user_api_key:uk}})}})
  .then(r=>r.json()).then(d=>{{
    removeTyping(typingId);
    if(orb) orb.classList.remove('thinking');
    addMsg(d.response||'Error','akira');
  }}).catch(()=>{{removeTyping(typingId); if(orb) orb.classList.remove('thinking'); addMsg('Error de conexión','akira');}});
}}

function addMsg(t,who){{
  const inner=document.getElementById('msgsInner');
  const row=document.createElement('div');
  row.className='msg-row '+who;
  if(who==='user'){{row.innerHTML=`<div class="bubble">${{escapeHtml(t)}}</div>`}}
  else{{row.innerHTML=`<div class="avatar"></div><div class="bubble">${{escapeHtml(t).replace(/\\n/g,'<br>')}}</div>`}}
  inner.appendChild(row);
  document.getElementById('msgs').scrollTop=document.getElementById('msgs').scrollHeight;
}}

function addTyping(){{
  const inner=document.getElementById('msgsInner');
  const row=document.createElement('div'); row.className='msg-row akira typing-row'; row.id='typing-'+Date.now();
  row.innerHTML=`<div class="avatar"></div><div class="bubble"><div class="typing"><span></span><span></span><span></span></div></div>`;
  inner.appendChild(row);
  document.getElementById('msgs').scrollTop=document.getElementById('msgs').scrollHeight;
  return row.id;
}}
function removeTyping(id){{const e=document.getElementById(id); if(e) e.remove();}}

function escapeHtml(t){{ let d=document.createElement('div'); d.textContent=t; return d.innerHTML; }}

const ta=document.getElementById('msg');
ta.addEventListener('input',()=>{{ta.style.height='auto'; ta.style.height=Math.min(ta.scrollHeight,160)+'px';}});
ta.addEventListener('keydown',e=>{{ if(e.key==='Enter' && !e.shiftKey){{ e.preventDefault(); sendMsg(); }} }});

try{{
  const u=JSON.parse(localStorage.getItem('akira_user')||'null');
  if(u && u.user_id){{ currentUser=u; document.getElementById('loginSection').style.display='none'; document.getElementById('mainApp').style.display='flex'; document.getElementById('userBox').style.display='flex'; document.getElementById('userEmail').textContent=u.email; document.getElementById('userAvatar').textContent=u.email[0].toUpperCase(); document.getElementById('userInfoTop').textContent=u.email; document.getElementById('modalEmail').textContent=u.email; updateKeyUI(!!localStorage.getItem('akira_user_key') || u.has_key); }}
}}catch(e){{}}
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
            from google.oauth2 import id_token
            from google.auth.transport import requests as grequests
            GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID","").strip() or "148150327312-7k5g3go06tat9gv61c8v0rbbedcusoqn.apps.googleusercontent.com"
            idinfo = None
            try:
                idinfo = id_token.verify_oauth2_token(credential, grequests.Request(), GOOGLE_CLIENT_ID)
            except:
                import base64, json as js
                parts = credential.split('.')
                if len(parts) >= 2:
                    payload_b64 = parts[1] + '=='
                    payload = js.loads(base64.urlsafe_b64decode(payload_b64.encode()).decode())
                    idinfo = payload
            if not idinfo:
                return {"error": "Token inválido"}
            email = idinfo.get("email","")
            sub = idinfo.get("sub","")
            user_id = sub or hashlib.sha256(email.encode()).hexdigest()[:16]
            has_key = get_user_key(user_id) is not None
            udir = get_user_dir(user_id)
            (udir / "profile.json").write_text(json.dumps({"email": email, "user_id": user_id, "ts": datetime.datetime.now().isoformat()}), encoding="utf-8")
            return {"user_id": user_id, "email": email, "has_key": has_key}
        except Exception as e:
            return {"error": f"Auth error: {str(e)[:200]}"}

    @app.post("/api/user/key")
    async def save_key(data: dict):
        user_id = data.get("user_id","").strip()
        api_key = data.get("api_key","").strip()
        if not user_id or not api_key or len(api_key) < 20:
            return {"error": "Key muy corta"}
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
        user_api_key = data.get("user_api_key","")
        client_ip = request.client.host if request.client else "unknown"

        related = memoria.search(msg, 3)
        context = "\n".join(related) if related else "Sin memorias"

        use_key = None
        used_own = False

        if user_api_key and len(user_api_key.strip()) > 20:
            use_key = user_api_key.strip()
            used_own = True
        else:
            stored = get_user_key(user_id)
            if stored:
                use_key = stored
                used_own = True
            else:
                owner_key = os.getenv("GEMINI_API_KEY","").strip()
                if owner_key and len(owner_key) > 20:
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
            if "API_KEY_INVALID" in err or "API key" in err:
                answer = "❌ API Key inválida. Revisa en aistudio.google.com/app/apikey - debe ser AIza... o AQ...."
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
