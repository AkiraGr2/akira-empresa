#!/usr/bin/env python3
# AKIRA V2 - GOOGLE LOGIN + BYOK + OWNER ACCESS + OBSIDIAN GRAPH - FINAL FIX
import os, json, datetime, threading, time, gc, hashlib
from pathlib import Path
from collections import defaultdict

try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

VERSION = "AKIRA V2 OBSIDIAN OWNER"
MODEL = "AKIRA V2"
OWNER_EMAILS = ["bjhon9161@gmail.com"]
OWNER_SECRET = os.getenv("OWNER_SECRET", "AKIRA_JHON_MASTER_2024")

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
    # Mantener vivo en Render - evita que se duerma cada 15 min
    import time, threading
    try:
        import requests
    except:
        return
    while True:
        time.sleep(600)  # 10 min
        try:
            url = os.getenv('RENDER_EXTERNAL_URL') or os.getenv('KEEPALIVE_URL') or ''
            if url:
                requests.get(url + '/health', timeout=10)
        except:
            pass


def crear_dashboard_final():
    google_client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip() or "148150327312-7k5g3go06tat9gv61c8v0rbbedcusoqn.apps.googleusercontent.com"
    html = f"""
<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AKIRA V2 • Obsidian + Owner</title>
<script src="https://accounts.google.com/gsi/client" async defer></script>
<script src="https://unpkg.com/force-graph@1.43.0/dist/force-graph.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
:root{{--bg:#0b0b0e;--sidebar:#121216;--border:#23232a;--text:#ececf1;--muted:#8a8a93}}
body{{background:var(--bg);color:var(--text);font-family:Inter,sans-serif;height:100dvh;overflow:hidden;display:flex}}
.sidebar{{width:270px;background:var(--sidebar);border-right:1px solid var(--border);display:flex;flex-direction:column;padding:14px;gap:10px;z-index:20;transition:transform .28s}}
.brand{{display:flex;align-items:center;gap:12px;padding:6px;cursor:pointer}}
.orb-wrap{{width:40px;height:40px;position:relative}} .orb{{width:40px;height:40px;border-radius:50%;background:radial-gradient(circle at 28% 22%, #10b981 0%, #6366f1 55%, #8b5cf6 90%);box-shadow:0 0 0 1px rgba(255,255,255,.1), 0 0 24px rgba(124,92,252,.55);animation:float 4s ease-in-out infinite}}
.orb.thinking{{animation:float .8s ease-in-out infinite, hue 2.2s linear infinite}} @keyframes float{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-3px) scale(1.04)}}}} @keyframes hue{{0%{{filter:hue-rotate(0deg)}}50%{{filter:hue-rotate(40deg)}}100%{{filter:hue-rotate(0deg)}}}}
.brand h1{{font-size:15.5px;font-weight:700}} .brand p{{font-size:11px;color:var(--muted)}}
.nav{{display:flex;flex-direction:column;gap:3px}} .nav-btn{{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:10px;border:1px solid transparent;color:var(--muted);font-size:13.5px;cursor:pointer;background:transparent;width:100%;text-align:left}} .nav-btn:hover{{background:#1c1c22;color:var(--text)}} .nav-btn.active{{background:#1e1e26;color:#fff;border-color:#2a2a36}}
.owner-badge{{background:linear-gradient(135deg,#f59e0b,#ef4444);color:#000;font-size:10px;font-weight:800;padding:3px 8px;border-radius:20px;margin-left:6px}}
.key-card{{margin-top:auto;background:#17171d;border:1px solid var(--border);border-radius:12px;padding:12px}} .dot{{width:8px;height:8px;border-radius:50%;background:#ef4444}} .dot.ok{{background:#10b981;box-shadow:0 0 8px #10b981}} .btn-key{{width:100%;margin-top:10px;padding:9px;border-radius:8px;background:#fff;color:#000;font-weight:600;font-size:12.5px;border:none;cursor:pointer}}
.user-box{{display:flex;align-items:center;gap:10px;padding:10px 8px;border-top:1px solid var(--border);margin-top:6px}} .av{{width:28px;height:28px;border-radius:50%;background:#2a2a36;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px}} .em{{font-size:12px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:130px}}
.main{{flex:1;display:flex;flex-direction:column;overflow:hidden}} .topbar{{height:52px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;padding:0 18px;background:rgba(11,11,14,.9)}} .menu{{display:none;background:transparent;border:none;color:var(--text);font-size:22px;cursor:pointer}} @media(max-width:860px){{.sidebar{{position:fixed;inset:0 35% 0 0;transform:translateX(-100%)}} .sidebar.open{{transform:translateX(0)}} .menu{{display:block}}}}
.login{{flex:1;display:flex;align-items:center;justify-content:center;padding:20px;background:radial-gradient(1000px 500px at 50% -10%, rgba(124,92,252,.18), transparent), var(--bg)}} .login-card{{background:#16161b;border:1px solid var(--border);border-radius:20px;padding:32px;max-width:400px;width:100%;text-align:center}} .orb-big{{width:72px;height:72px;margin:0 auto 18px;border-radius:50%;background:radial-gradient(circle at 28% 22%, #10b981, #6366f1, #8b5cf6);box-shadow:0 0 0 1px rgba(255,255,255,.12), 0 0 50px rgba(124,92,252,.7);animation:float 3s ease-in-out infinite}} .legal{{font-size:11px;color:#666;margin-top:14px}} .btn-ghost{{width:100%;margin-top:16px;padding:10px;border-radius:10px;background:transparent;border:1px solid var(--border);color:var(--muted);font-size:13px;cursor:pointer}}
.chat-wrap{{flex:1;display:flex;flex-direction:column;overflow:hidden}} .msgs{{flex:1;overflow-y:auto}} .msgs-inner{{max-width:760px;margin:0 auto;width:100%;padding:22px 18px}} .msg-row{{display:flex;gap:12px;padding:14px 0}} .msg-row.user{{flex-direction:row-reverse}} .msg-row.user .bubble{{background:#24242d;border-radius:18px 18px 4px 18px;padding:11px 15px;max-width:72%;font-size:14.3px}} .msg-row.akira .avatar{{width:30px;height:30px;border-radius:50%;background:radial-gradient(circle at 28% 22%, #10b981, #6366f1);flex-shrink:0}} .msg-row.akira .bubble{{flex:1;font-size:14.4px;line-height:1.6}}
.typing{{display:flex;gap:4px}} .typing span{{width:5px;height:5px;border-radius:50%;background:var(--muted);animation:typ 1.4s infinite}} @keyframes typ{{0%,80%,100%{{opacity:.3}}40%{{opacity:1}}}}
.input-bar{{padding:12px 16px 18px;background:linear-gradient(transparent, var(--bg) 22%)}} .input-inner{{max-width:760px;margin:0 auto;background:#1c1c22;border:1px solid #2a2a36;border-radius:24px;padding:7px 8px 7px 16px;display:flex;align-items:flex-end;gap:8px}} .input-inner textarea{{flex:1;background:transparent;border:none;color:var(--text);font-size:15px;resize:none;outline:none;max-height:160px;min-height:24px;font-family:Inter,sans-serif;padding:5px 0}} .btn-send{{width:32px;height:32px;border-radius:50%;background:#fff;color:#000;border:none;display:flex;align-items:center;justify-content:center;cursor:pointer}}
.section{{display:none;flex:1;overflow-y:auto;padding:20px}} .section.active{{display:block}}
.obsidian-wrap{{height:100%;display:flex;flex-direction:column;gap:12px}} .obsidian-toolbar{{display:flex;gap:8px;align-items:center;flex-wrap:wrap;background:#15151a;border:1px solid var(--border);border-radius:12px;padding:10px 12px}} .obsidian-toolbar input{{background:#0e0e12;border:1px solid var(--border);border-radius:8px;padding:8px 12px;color:#fff;font-size:13px;min-width:200px;outline:none}} #graph{{flex:1;min-height:520px;background:#0a0a0e;border-radius:14px;border:1px solid var(--border);position:relative;overflow:hidden}} .graph-hint{{position:absolute;left:12px;bottom:12px;background:rgba(0,0,0,.6);border:1px solid rgba(255,255,255,.08);border-radius:8px;padding:8px 10px;font-size:11px;color:var(--muted);z-index:2;pointer-events:none}}
.card{{background:#16161b;border:1px solid var(--border);border-radius:14px;padding:14px}}
.modal{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);backdrop-filter:blur(10px);z-index:100;align-items:center;justify-content:center;padding:18px}} .modal.active{{display:flex}} .modal-box{{background:#1a1a22;border:1px solid #2a2a36;border-radius:16px;padding:22px;max-width:420px;width:100%}} .input-key{{width:100%;padding:12px 14px;border-radius:10px;border:1px solid #2a2a36;background:#0e0e12;color:#fff;margin:12px 0;font-family:monospace;font-size:13px;outline:none}} .btn{{padding:10px 16px;border-radius:10px;border:none;font-weight:600;font-size:13px;cursor:pointer}} .btn.primary{{background:#fff;color:#000;flex:1}} .btn.sec{{background:#2a2a36;color:#fff;flex:1}} .btn.full{{width:100%;margin-top:10px;background:transparent;border:1px solid #2a2a36;color:var(--muted)}}
</style></head>
<body>
<div class="sidebar" id="sidebar">
  <div class="brand" onclick="ownerTap()"><div class="orb-wrap"><div class="orb" id="orb"></div></div><div><h1>AKIRA V2 <span id="ownerTag" style="display:none" class="owner-badge">CREADOR</span></h1><p>Obsidian Brain • Bogotá</p></div></div>
  <div class="nav">
    <button class="nav-btn active" id="btn-chat" onclick="showTab('chat')">💬 Chat</button>
    <button class="nav-btn" id="btn-cerebro" onclick="showTab('cerebro')">🕸️ Cerebro Obsidian</button>
    <button class="nav-btn" id="btn-memoria" onclick="showTab('memoria')">📚 Memoria</button>
    <button class="nav-btn" id="btn-empresa" onclick="showTab('empresa')">💼 Servicios</button>
    <button class="nav-btn" id="btn-owner" onclick="openOwnerModal()" style="display:none;border:1px dashed #f59e0b;color:#f59e0b">👑 Panel Creador</button>
  </div>
  <div class="key-card"><div style="display:flex;justify-content:space-between;align-items:center"><span style="font-size:12px;font-weight:600" id="keyStatus">🔑 Sin key</span><span class="dot" id="keyDot"></span></div><small id="keySub">Guarda tu key 1 vez</small><button class="btn-key" onclick="openKeyModal()">Gestionar API Key</button><small id="ownerInfo" style="display:none;color:#f59e0b;margin-top:8px;font-weight:600">👑 Modo Creador: sin límites, usa tu key directa del servidor</small></div>
  <div class="user-box" id="userBox" style="display:none"><div class="av" id="userAvatar">J</div><div style="flex:1;min-width:0"><div class="em" id="userEmail">--</div><div style="font-size:10px;color:var(--muted)" id="userRole">BYOK activo</div></div><button onclick="logout()" style="background:transparent;border:none;color:var(--muted);cursor:pointer">↪</button></div>
</div>
<div class="main">
  <div class="topbar"><h2><button class="menu" onclick="document.getElementById('sidebar').classList.toggle('open')">☰</button><span id="topTitle">Chat</span></h2><span id="userInfoTop" style="font-size:11px;color:var(--muted)"></span></div>
  <div id="loginSection" class="login"><div class="login-card"><div class="orb-big"></div><h3>Bienvenido a AKIRA</h3><p style="font-size:13px;color:var(--muted);margin:8px 0 18px">ChatGPT + Obsidian. Inicia con Google.</p><div id="g_id_onload" data-client_id="{google_client_id}" data-context="signin" data-ux_mode="popup" data-callback="handleGoogleLogin" data-auto_prompt="false"></div><div class="g_id_signin" data-type="standard" data-shape="pill" data-theme="filled_black" data-text="signin_with" data-size="large"></div><p class="legal">Keys válidas: AIza...<br><span style="font-size:10px;color:#555">5 clics en el logo para acceso creador • o añade ?owner a la URL</span></p><button class="btn-ghost" onclick="continueWithoutLogin()">Continuar sin login (15/h)</button></div></div>
  <div id="mainApp" style="display:none;flex:1;flex-direction:column;overflow:hidden">
    <div id="sec-chat" class="section active" style="padding:0;display:flex;flex-direction:column"><div class="chat-wrap"><div class="msgs" id="msgs"><div class="msgs-inner" id="msgsInner"><div class="msg-row akira"><div class="avatar"></div><div class="bubble"><b>AKIRA V2 • Obsidian + Owner</b><br>Si eres Jhon, 5 clics en el orbe o ?owner en la URL = acceso creador sin límites.<br><br>🧠 El cerebro Obsidian ya está activo en 🕸️ Cerebro.</div></div></div></div><div class="input-bar"><div class="input-inner"><textarea id="msg" placeholder="Pregúntale a AKIRA..." rows="1"></textarea><button id="sendBtn" class="btn-send" onclick="sendMsg()">↑</button></div></div></div></div>
    <div id="sec-cerebro" class="section"><div class="obsidian-wrap"><div class="obsidian-toolbar"><input id="graphSearch" placeholder="Buscar en cerebro..." oninput="filterGraph(this.value)"><span id="graphStats" style="font-size:11px;color:var(--muted);background:#1c1c22;padding:6px 10px;border-radius:20px;border:1px solid var(--border)">0 nodos</span><button class="icon-btn" onclick="resetGraph()">↻</button></div><div id="graph"><div class="graph-hint">🟣 AKIRA • 🔵 Tú • ⚪ Memorias • arrastra • zoom • click memoria → chat</div></div></div></div>
    <div id="sec-memoria" class="section"><h3>📚 Memoria</h3><div id="memList">Cargando...</div></div>
    <div id="sec-empresa" class="section"><h3>💼 Servicios</h3><div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;margin-top:14px"><div class="card"><h4>WhatsApp Bot</h4><b>$350</b></div><div class="card"><h4>Contenido IA</h4><b>$200/mes</b></div><div class="card"><h4>RAG</h4><b>$500</b></div></div></div>
  </div>
</div>
<div class="modal" id="keyModal"><div class="modal-box"><h3>🔑 API Key</h3><p style="font-size:13px;color:var(--muted)">Debe empezar con AIza...</p><input class="input-key" id="keyInput" placeholder="AIzaSy..." type="password"><p style="font-size:11px;color:#666">Ve a <a href="https://aistudio.google.com/app/apikey" target="_blank" style="color:#8b9cff">aistudio.google.com/app/apikey</a> → Create → Copiar. Las AQ. NO sirven para Gemini.</p><div style="display:flex;gap:8px;margin-top:12px"><button class="btn primary" onclick="saveKey()">Guardar</button><button class="btn sec" onclick="closeKeyModal()">Cancelar</button></div></div></div>
<div class="modal" id="ownerModal"><div class="modal-box" style="border:1px solid #f59e0b"><h3>👑 Acceso Creador</h3><p style="font-size:13px;color:var(--muted)">Solo para Jhon. Sin Google, sin límites. Usa tu GEMINI_API_KEY directa del servidor.</p><input class="input-key" id="ownerInput" placeholder="AKIRA_JHON_MASTER_2024" type="password"><p style="font-size:11px;color:#888">Secret en Render: OWNER_SECRET (default AKIRA_JHON_MASTER_2024). También puedes entrar directo con tu Google bjhon9161@gmail.com y ya eres owner.</p><div style="display:flex;gap:8px;margin-top:12px"><button class="btn primary" onclick="loginOwner()">Entrar como Creador</button><button class="btn sec" onclick="closeOwnerModal()">Cancelar</button></div><div id="ownerStatus" style="margin-top:10px;font-size:12px;color:#f59e0b"></div></div></div>
<script>
let currentUser=null; let userKey=localStorage.getItem('akira_user_key'); let Graph=null; let allGraphData=null; let ownerClicks=0; let isOwner=false;
function ownerTap(){{ ownerClicks++; if(ownerClicks>=5){{ openOwnerModal(); ownerClicks=0; }} setTimeout(()=>ownerClicks=0,3000); }}
if(window.location.search.includes('owner')){{ setTimeout(()=>openOwnerModal(),800); }}
function handleGoogleLogin(r){{const o=document.getElementById('orb'); if(o)o.classList.add('thinking'); fetch('/api/auth/google',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{credential:r.credential}})}}).then(x=>x.json()).then(d=>{{if(d.user_id){{currentUser=d; isOwner=d.is_owner||false; localStorage.setItem('akira_user',JSON.stringify(d)); localStorage.setItem('akira_user_id',d.user_id); localStorage.setItem('akira_is_owner', isOwner?'1':'0'); document.getElementById('loginSection').style.display='none'; document.getElementById('mainApp').style.display='flex'; document.getElementById('userBox').style.display='flex'; document.getElementById('userEmail').textContent=d.email; document.getElementById('userAvatar').textContent=d.email[0].toUpperCase(); document.getElementById('userInfoTop').textContent=d.email; if(isOwner){{document.getElementById('ownerTag').style.display='inline-block'; document.getElementById('ownerInfo').style.display='block'; document.getElementById('btn-owner').style.display='flex'; document.getElementById('userRole').textContent='👑 Creador'; document.getElementById('userRole').style.color='#f59e0b';}} if(o)o.classList.remove('thinking'); if(d.has_key || isOwner){{updateKeyUI(true)}} else if(userKey){{updateKeyUI(true)}} else {{updateKeyUI(false); setTimeout(()=>openKeyModal(),600)}} }} else {{alert('Error: '+(d.error||'')); if(o)o.classList.remove('thinking');}} }});}}
function loginOwner(){{const secret=document.getElementById('ownerInput').value.trim(); document.getElementById('ownerStatus').textContent='Verificando...'; fetch('/api/auth/owner',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{secret}})}}).then(r=>r.json()).then(d=>{{if(d.ok){{ currentUser=d; isOwner=true; localStorage.setItem('akira_user',JSON.stringify(d)); localStorage.setItem('akira_user_id',d.user_id); localStorage.setItem('akira_is_owner','1'); document.getElementById('loginSection').style.display='none'; document.getElementById('mainApp').style.display='flex'; document.getElementById('userBox').style.display='flex'; document.getElementById('userEmail').textContent=d.email; document.getElementById('userAvatar').textContent='👑'; document.getElementById('userInfoTop').textContent=d.email+' (CREADOR)'; document.getElementById('ownerTag').style.display='inline-block'; document.getElementById('ownerInfo').style.display='block'; document.getElementById('btn-owner').style.display='flex'; updateKeyUI(true); closeOwnerModal(); addMsg('👑 Acceso creador activado. Usas tu GEMINI_API_KEY directa, sin límite 15/h.','akira'); }} else {{document.getElementById('ownerStatus').textContent='❌ Secreto incorrecto.';}}}});}}
function continueWithoutLogin(){{document.getElementById('loginSection').style.display='none'; document.getElementById('mainApp').style.display='flex'; updateKeyUI(false);}}
function logout(){{localStorage.clear(); location.reload();}}
function updateKeyUI(has){{const s=document.getElementById('keyStatus'), dot=document.getElementById('keyDot'), sub=document.getElementById('keySub'); if(has){{s.textContent='🔑 Key OK'; dot.className='dot ok'; sub.textContent=isOwner?'👑 Creador - sin límite':'BYOK activo';}} else {{s.textContent='🔑 Sin key'; dot.className='dot'; sub.textContent='Pon tu key AIza...';}}}}
function openKeyModal(){{document.getElementById('keyModal').classList.add('active');}} function closeKeyModal(){{document.getElementById('keyModal').classList.remove('active');}} function openOwnerModal(){{document.getElementById('ownerModal').classList.add('active');}} function closeOwnerModal(){{document.getElementById('ownerModal').classList.remove('active');}}
function saveKey(){{const k=document.getElementById('keyInput').value.trim(); if(!k.startsWith('AIza')){{alert('Debe empezar con AIza... Las AQ. NO sirven. Ve a aistudio.google.com/app/apikey'); return;}} const uid=localStorage.getItem('akira_user_id')||'anon'; if(uid==='anon'){{localStorage.setItem('akira_user_key',k); userKey=k; updateKeyUI(true); closeKeyModal(); return;}} fetch('/api/user/key',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{user_id:uid,api_key:k}})}}).then(r=>r.json()).then(d=>{{if(d.ok){{userKey=k; localStorage.setItem('akira_user_key',k); updateKeyUI(true); closeKeyModal();}} else alert(d.error||'Error');}});}}
function showTab(name){{document.querySelectorAll('.section').forEach(s=>s.classList.remove('active')); document.getElementById('sec-'+name).classList.add('active'); document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active')); const b=document.getElementById('btn-'+name); if(b)b.classList.add('active'); document.getElementById('topTitle').textContent=name==='cerebro'?'Cerebro Obsidian':name.charAt(0).toUpperCase()+name.slice(1); document.getElementById('sidebar').classList.remove('open'); if(name==='memoria')loadMems(); if(name==='cerebro')initGraph();}}
function loadMems(){{fetch('/api/memorias').then(r=>r.json()).then(d=>{{const el=document.getElementById('memList'); el.innerHTML=`<div style="color:var(--muted);font-size:12px;margin-bottom:10px">${{d.count}} memorias</div>`+d.recent.map(m=>`<div class="card" style="font-size:12.5px">${{escapeHtml((m.texto||'').slice(0,400))}}</div>`).join('');}});}}
async function initGraph(){{ if(Graph){{ Graph.zoomToFit(400); return; }} const el=document.getElementById('graph'); let mems=[]; try{{ const r=await fetch('/api/memorias'); const j=await r.json(); mems=j.recent||[]; }}catch(e){{}} const nodes=[]; const links=[]; nodes.push({{id:'AKIRA', label:'AKIRA V2', type:'akira', val:16, color:'#7c5cfc'}}); nodes.push({{id:'YOU', label: (currentUser?currentUser.email:'Tú'), type:'user', val:11, color:'#3b82f6'}}); links.push({{source:'AKIRA', target:'YOU', value:2}}); mems.slice(0,45).forEach((m,i)=>{{ const txt=(m.texto||''); const id='mem-'+i; const short=txt.split(' ').slice(0,4).join(' ').slice(0,30); nodes.push({{id, label: short||'mem '+i, full: txt, type:'mem', val:4+Math.min(7, txt.length/130), color: i%3===0?'#10b981': i%3===1?'#8a8a93':'#d4d4d8'}}); links.push({{source:'AKIRA', target:id, value:0.7}}); if(i>0){{ const prev='mem-'+(i-1); if(Math.random()>0.6) links.push({{source:prev, target:id, value:0.35}}); }} }}); const graphData={{nodes, links}}; allGraphData={{nodes:[...nodes], links:[...links]}}; Graph = ForceGraph()(el).backgroundColor('#0a0a0e').graphData(graphData).nodeId('id').nodeVal('val').nodeLabel(n=> (n.full||n.label||'').slice(0,180)).nodeColor(n=> n.color).nodeCanvasObject((node, ctx, globalScale)=>{{ const r=Math.max(2, Math.min(8, (node.val||4)/globalScale*0.8+2.5)); if(node.type==='akira'){{ ctx.beginPath(); ctx.arc(node.x, node.y, r*2.3, 0, 2*Math.PI); ctx.fillStyle='rgba(124,92,252,0.18)'; ctx.fill(); }} ctx.beginPath(); ctx.arc(node.x, node.y, r, 0, 2*Math.PI); ctx.fillStyle=node.color||'#888'; ctx.fill(); }}).linkColor(()=>'rgba(255,255,255,0.09)').linkWidth(l=> l.value||0.5).d3AlphaDecay(0.02).d3VelocityDecay(0.32).onNodeClick(n=>{{ if(n&&n.full){{ addMsg('Memoria: '+n.full.slice(0,320),'akira'); showTab('chat'); }} }}); Graph.d3Force('charge').strength(-85); Graph.d3Force('link').distance(92); setTimeout(()=>Graph.zoomToFit(380,30),500); }}
function filterGraph(q){{ if(!Graph||!allGraphData) return; q=q.toLowerCase().trim(); if(!q){{ Graph.graphData(allGraphData); return; }} const filteredNodes = allGraphData.nodes.filter(n=> (n.label&&n.label.toLowerCase().includes(q)) || (n.full&&n.full.toLowerCase().includes(q)) ); const ids=new Set(filteredNodes.map(n=>n.id)); ids.add('AKIRA'); ids.add('YOU'); const fLinks=allGraphData.links.filter(l=> ids.has(l.source.id||l.source) && ids.has(l.target.id||l.target)); const fNodes=allGraphData.nodes.filter(n=> ids.has(n.id)); Graph.graphData({{nodes:fNodes, links:fLinks}}); }}
function resetGraph(){{ document.getElementById('graphSearch').value=''; if(Graph&&allGraphData){{ Graph.graphData(allGraphData); Graph.zoomToFit(400); }} }}
function sendMsg(){{const inp=document.getElementById('msg'); const txt=inp.value.trim(); if(!txt) return; const orb=document.getElementById('orb'); if(orb)orb.classList.add('thinking'); addMsg(txt,'user'); inp.value=''; const tid=addTyping(); const uid=localStorage.getItem('akira_user_id')||'anon'; const uk=localStorage.getItem('akira_user_key')||''; const isOwn=localStorage.getItem('akira_is_owner')==='1'; fetch('/api/chat',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{message:txt,user_id:uid,user_api_key:uk,is_owner:isOwn}})}}).then(r=>r.json()).then(d=>{{removeTyping(tid); if(orb)orb.classList.remove('thinking'); addMsg(d.response||'Error','akira');}}).catch(()=>{{removeTyping(tid); if(orb)orb.classList.remove('thinking'); addMsg('Error','akira');}});}}
function addMsg(t,who){{const inner=document.getElementById('msgsInner'); const row=document.createElement('div'); row.className='msg-row '+who; if(who==='user'){{row.innerHTML=`<div class="bubble">${{escapeHtml(t)}}</div>`}} else {{row.innerHTML=`<div class="avatar"></div><div class="bubble">${{escapeHtml(t).replace(/\n/g,'<br>')}}</div>`}} inner.appendChild(row); document.getElementById('msgs').scrollTop=document.getElementById('msgs').scrollHeight;}}
function addTyping(){{const inner=document.getElementById('msgsInner'); const row=document.createElement('div'); row.className='msg-row akira'; row.id='typing-'+Date.now(); row.innerHTML=`<div class="avatar"></div><div class="bubble"><div class="typing"><span></span><span></span><span></span></div></div>`; inner.appendChild(row); document.getElementById('msgs').scrollTop=document.getElementById('msgs').scrollHeight; return row.id;}}
function removeTyping(id){{const e=document.getElementById(id); if(e)e.remove();}}
function escapeHtml(t){{let d=document.createElement('div'); d.textContent=t; return d.innerHTML;}}
const ta=document.getElementById('msg'); ta.addEventListener('input',()=>{{ta.style.height='auto'; ta.style.height=Math.min(ta.scrollHeight,160)+'px';}}); ta.addEventListener('keydown',e=>{{if(e.key==='Enter'&&!e.shiftKey){{e.preventDefault(); sendMsg();}}}});
try{{const u=JSON.parse(localStorage.getItem('akira_user')||'null'); if(u&&u.user_id){{currentUser=u; isOwner=localStorage.getItem('akira_is_owner')==='1' || u.is_owner; document.getElementById('loginSection').style.display='none'; document.getElementById('mainApp').style.display='flex'; document.getElementById('userBox').style.display='flex'; document.getElementById('userEmail').textContent=u.email; document.getElementById('userAvatar').textContent=u.email[0].toUpperCase(); document.getElementById('userInfoTop').textContent=u.email+(isOwner?' (CREADOR)':''); if(isOwner){{document.getElementById('ownerTag').style.display='inline-block'; document.getElementById('ownerInfo').style.display='block'; document.getElementById('btn-owner').style.display='flex';}} updateKeyUI(!!localStorage.getItem('akira_user_key')||u.has_key||isOwner);}}}}catch(e){{}}
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
    app = FastAPI(title=f"AKIRA {MODEL} OWNER")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    
    @app.get("/")
    async def root():
        return FileResponse(BASE / "index.html")
    
    @app.get("/api/memorias")
    async def get_mems():
        return {"count": memoria.count(), "recent": memoria.load_recent(50), "version": VERSION, "model": MODEL}

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
        if secret != OWNER_SECRET:
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
        if not user_id or not api_key or len(api_key) < 30:
            return {"error": "Key muy corta"}
        if not (api_key.startswith("AIza") or api_key.startswith("AQ.")):
            return {"error": "Key inválida - debe empezar con AIza... o AQ."}
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
        context = "\n".join(related) if related else "Sin memorias"
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
            if owner_key and (owner_key.startswith("AIza") or owner_key.startswith("AQ.")) and len(owner_key) > 20:
                use_key = owner_key
            else:
                return {"response": "👑 Eres creador pero tu GEMINI_API_KEY en Render está vacía o mal copiada. Pega tu AQ. completa en Render > GEMINI_API_KEY y Save.", "is_owner": True}
        elif user_api_key and (user_api_key.startswith("AIza") or user_api_key.startswith("AQ.")) and len(user_api_key.strip()) > 20:
            use_key = user_api_key.strip()
        else:
            stored = get_user_key(user_id)
            if stored and (stored.startswith("AIza") or stored.startswith("AQ.")) and len(stored) > 20:
                use_key = stored
            else:
                owner_key = os.getenv("GEMINI_API_KEY","").strip()
                if owner_key and (owner_key.startswith("AIza") or owner_key.startswith("AQ.")) and len(owner_key) > 20:
                    if not check_rate_limit(client_ip, is_owner=False):
                        return {"response": "⚠️ Límite 15/h con key del owner. Pon tu API Key AIza... en 🔑 Mi API Key."}
                    use_key = owner_key
                else:
                    return {"response": "❌ No hay API Key válida. Pon tu key AQ. o AIza... en 🔑 Mi API Key. Si eres Jhon, pon tu AQ. en Render > GEMINI_API_KEY."}

        try:
            answer = ""
            if use_key.startswith("AQ."):
                # Nuevo formato AQ. usa google-genai
                try:
                    from google import genai
                    client = genai.Client(api_key=use_key)
                    prompt = f"Eres AKIRA V2 creado por Jhon Bogotá. Memoria: {context}\nUsuario {user_id}: {msg}\nResponde útil."
                    resp = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
                    answer = resp.text
                except Exception as e_new:
                    # Fallback intentar con librería vieja
                    import google.generativeai as genai_old
                    genai_old.configure(api_key=use_key)
                    model = genai_old.GenerativeModel('gemini-1.5-flash')
                    prompt = f"Eres AKIRA V2. Memoria: {context}\nUsuario {user_id}: {msg}\nResponde útil."
                    resp = model.generate_content(prompt)
                    answer = resp.text
            else:
                import google.generativeai as genai
                genai.configure(api_key=use_key)
                model = genai.GenerativeModel('gemini-1.5-flash')
                prompt = f"Eres AKIRA V2. Memoria: {context}\nUsuario {user_id}: {msg}\nResponde útil."
                resp = model.generate_content(prompt)
                answer = resp.text
        except Exception as e:
            err = str(e)
            if "API_KEY_INVALID" in err or "API key" in err.lower():
                answer = f"❌ API Key inválida: {err[:150]}. Verifica que tu AQ. esté bien copiada en Render > GEMINI_API_KEY."
            else:
                answer = f"[Error: {err[:200]}]"
            print(f"Gemini error {err}")

        memoria.add(f"User {user_id}: {msg} | AKIRA: {answer}")
        return {"response": answer, "model": MODEL, "is_owner": is_owner}

    if __name__ == "__main__":
        crear_dashboard_final()
        # Hilo para mantener vivo 24/7 en Render
        try:
            threading.Thread(target=keep_alive_ping, daemon=True).start()
        except:
            pass
        port = int(os.getenv("PORT", 8000))
        print(f"🚀 AKIRA {MODEL} OWNER+OBSIDIAN - Puerto {port}")
        uvicorn.run(app, host="0.0.0.0", port=port)
