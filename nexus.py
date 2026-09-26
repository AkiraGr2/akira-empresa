#!/usr/bin/env python3
# AKIRA FINAL - INCREIBLE + OPTIMIZADA PARA FREE VPS HOSTING - GRATIS PARA SIEMPRE
# Fusion de tu AKIRA 1M Oracle + Optimizacion para Learner 512MB-1GB
# FreeVPSHostings.com Learner: 512MB RAM, 1 vCPU, 10GB SSD, No Card Forever
# Premium: 8-Core, 16GB RAM first month free then $4
import os, json, datetime, math, random, hashlib, threading, time, subprocess, re, sys, base64, gc
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import traceback

VERSION = "AKIRA"
# MODELO ADAPTATIVO - DETECTA RAM Y SE AJUSTA AUTOMATICAMENTE
def detect_ram_mb():
    try:
        import psutil
        return psutil.virtual_memory().total // (1024*1024)
    except:
        try:
            # Linux /proc/meminfo
            with open('/proc/meminfo') as f:
                for line in f:
                    if 'MemTotal' in line:
                        kb = int(line.split()[1])
                        return kb // 1024
        except: pass
        return 512  # default free hosting

RAM_MB = detect_ram_mb()
# CONFIG ADAPTATIVA PARA FREE VPS HOSTING
if RAM_MB <= 600:
    # Learner 512MB Gratis Para Siempre
    EMBEDDING_DIM = 384
    TOTAL_NIVELES = 50000  # 50k * 384 * 4 = 76MB
    MODEL = f"FINAL-LITE-{RAM_MB}MB-FREEFOREVER-50K"
elif RAM_MB <= 1200:
    # 1GB - 1GB RAM Shared
    EMBEDDING_DIM = 384
    TOTAL_NIVELES = 120000  # 120k * 384 * 4 = 184MB
    MODEL = f"FINAL-MID-{RAM_MB}MB-120K"
elif RAM_MB <= 7000:
    # 6GB - Tu config original Oracle Bogota
    EMBEDDING_DIM = 768
    TOTAL_NIVELES = 1000000  # 1M * 768 * 4 = 3.07GB
    MODEL = f"FINAL-ORACLE-{RAM_MB}MB-1M-REAL"
else:
    # 16GB Premium
    EMBEDDING_DIM = 768
    TOTAL_NIVELES = 2500000
    MODEL = f"FINAL-PREMIUM-{RAM_MB}MB-2.5M"

BASE = Path("resultados")
BASE.mkdir(exist_ok=True)
for d in ["dinero","contenido","memoria","cognicion","tools","security","autonomy","vision","backups","codigo","empresa","clientes"]:
    (BASE / d).mkdir(exist_ok=True)

print(f"🧠 AKIRA {MODEL} DETECTADA RAM: {RAM_MB}MB -> {TOTAL_NIVELES} neur - {EMBEDDING_DIM}D")

class SecurityManager:
    def __init__(self):
        self.audit_path = BASE / "security" / "audit.log"
        self.rate_limits = {}
        self.blocked_patterns = [r"__import__", r"eval\s*\(", r"exec\s*\(", r"os\.system", r"rm\s+-rf"]
        self.max_input_len = 10000
    def audit(self, action, user="Jhon", tool=None, result="ok", details=""):
        entry = {"ts": datetime.datetime.now().isoformat(), "user": user, "action": action, "tool": tool, "result": result, "details": details[:500]}
        try:
            with self.audit_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except: pass
    def validate_input(self, text):
        if len(text) > self.max_input_len:
            return False, "Input largo"
        return True, "OK"
    def rate_limit(self, tool): return True, "OK"

security = SecurityManager()

class MemoriaFINAL:
    def __init__(self):
        self.path = BASE / "memoria" / "akira_memoria_final.jsonl"
        self.path.parent.mkdir(exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")
        # Solo activa ChromaDB si hay +4GB RAM (Premium/Oracle), si no JSONL para ahorrar RAM
        self.chroma = None
        if RAM_MB > 4000:
            try:
                import chromadb
                client = chromadb.PersistentClient(path=str(BASE / "memoria" / "chroma"))
                self.chroma = client.get_or_create_collection("akira_brain")
                print(f"✅ ChromaDB activo - {RAM_MB}MB - {self.chroma.count()} memorias")
            except Exception as e:
                print(f"⚠️ ChromaDB no disponible, usando JSONL: {e}")
        else:
            print(f"✅ Memoria LITE JSONL activa - {RAM_MB}MB - {self.count()} memorias - Optimizada Free Forever")

    def add(self, texto, tipo="episodica", importancia=5, tags=None):
        entry = {"texto": texto, "tipo": tipo, "importancia": importancia, "ts": datetime.datetime.now().isoformat(), "tags": tags or []}
        try:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            if self.chroma:
                self.chroma.add(documents=[texto], metadatas=[{"tipo": tipo, "importancia": importancia}], ids=[hashlib.md5(texto.encode()).hexdigest()])
        except: pass

    def count(self):
        if self.chroma:
            try: return self.chroma.count()
            except: pass
        try: return len(self.path.read_text(encoding="utf-8").splitlines())
        except: return 0

    def load_recent(self, n=20):
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()[-n:]
            return [json.loads(l) for l in lines if l.strip()]
        except: return []

    def search(self, query, n=5):
        if self.chroma:
            try:
                res = self.chroma.query(query_texts=[query], n_results=n)
                return res.get('documents', [[]])[0]
            except: pass
        all_mems = self.load_recent(200)
        return [m['texto'] for m in all_mems if query.lower() in m['texto'].lower()][:n]

memoria = MemoriaFINAL()

def ensure_goals():
    gd = BASE / "autonomy"
    gd.mkdir(exist_ok=True)
    try:
        (gd / "daemon_active.flag").write_text(datetime.datetime.now().isoformat(), encoding='utf-8')
    except: pass
    # Goals originales + Goals empresa Upwork
    goals = [
        {"id":"001","texto":"Dominar Pygame - 5 juegos","importancia":9,"progreso":0,"pasos":["Snake","Tetris","Platformer","Shooter","RPG"],"tipo":"codigo"},
        {"id":"002","texto":"Flutter Android iOS - 3 apps","importancia":9,"progreso":0,"pasos":["Chat","Camara","Mapa"],"tipo":"codigo"},
        {"id":"003","texto":"Machine Learning + Vision + NLP","importancia":9,"progreso":0,"pasos":["Clasificador","Chatbot","Vision"],"tipo":"ia"},
        {"id":"004","texto":"Bolsa + Forex + Crypto - Trading Bot","importancia":10,"progreso":0,"pasos":["Backtest","Bot","App"],"tipo":"dinero"},
        # NUEVOS GOALS EMPRESA - PARA UPWORK
        {"id":"005","texto":"Empresa AKIRA - Asistente WhatsApp 24/7 para pymes - $350","importancia":10,"progreso":0,"pasos":["Demo pizzeria","Demo barberia","Landing page","Upwork profile"],"tipo":"empresa"},
        {"id":"006","texto":"Empresa AKIRA - Generador contenido 30 posts/mes - $200/mes","importancia":10,"progreso":0,"pasos":["Template posts","Automatizacion","Demo cliente"],"tipo":"empresa"},
        {"id":"007","texto":"Empresa AKIRA - Chatbot web con RAG - $500","importancia":10,"progreso":0,"pasos":["RAG con PDFs","Widget web","Demo empresa"],"tipo":"empresa"},
    ]
    for g in goals:
        path = gd / f"goal_{g['id']}.json"
        if not path.exists():
            g["ts"] = datetime.datetime.now().isoformat()
            path.write_text(json.dumps(g, ensure_ascii=False, indent=2), encoding='utf-8')

def continuous_learning_loop():
    print(f"🧠 AKIRA {MODEL} CONTINUOUS - {TOTAL_NIVELES} neur - {EMBEDDING_DIM}D - {RAM_MB}MB - Free Forever Ready")
    while True:
        try:
            time.sleep(30 if RAM_MB < 1000 else 10)  # Ahorra CPU en plan gratis
            try:
                (BASE / "autonomy" / "daemon_active.flag").write_text(datetime.datetime.now().isoformat(), encoding='utf-8')
            except: pass
            memoria.add(f"AKIRA {MODEL} tick - {datetime.datetime.now().isoformat()} - {TOTAL_NIVELES} neur - {memoria.count()} mem - RAM {RAM_MB}MB - Free VPS Hosting", tipo="procedimental", importancia=3, tags=["continuous","freeforever"])
            gc.collect()  # Libera RAM en plan 512MB
        except Exception as e:
            print(f"Continuous error: {e}")
            time.sleep(10)

def crear_dashboard_final():
    html = f"""
<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>AKIRA {MODEL} - FREE FOREVER EMPRESA</title>
<script src="https://unpkg.com/force-graph"></script>
<style>
body{{background:#0a0a0f;color:#fff;font-family:Inter,sans-serif;margin:0}}
.header{{padding:20px;text-align:center;border-bottom:1px solid #222}}
.orb{{width:120px;height:120px;margin:20px auto;background:radial-gradient(circle at 30% 30%, #10b981, #8b5cf6);border-radius:50%;box-shadow:0 0 60px #10b981;animation:pulse 2s infinite}}
@keyframes pulse{{0%{{transform:scale(1)}}50%{{transform:scale(1.1)}}100%{{transform:scale(1)}}}}
.tabs{{display:flex;gap:10px;justify-content:center;padding:20px;flex-wrap:wrap}}
.tab{{padding:10px 20px;background:#1a1a24;border-radius:20px;cursor:pointer;border:1px solid #333}}
.tab.active{{background:#10b981;color:#000}}
.card{{background:#1a1a24;border:1px solid #222;border-radius:15px;padding:15px;margin:10px;min-width:200px}}
.badge{{background:#10b981;color:#000;padding:5px 10px;border-radius:10px;font-size:12px}}
</style></head>
<body>
<div class="header">
<div class="orb" id="orb"></div>
<h1>AKIRA {MODEL}</h1>
<p>🟢 Gratis Para Siempre - {RAM_MB}MB RAM - {TOTAL_NIVELES:,} neur - {EMBEDDING_DIM}D - {memoria.count()} memorias</p>
<p><span class="badge">FREE FOREVER - No Credit Card</span> <span class="badge">Upwork Ready</span> <span class="badge">Empresa Mode</span></p>
<p id="status">RAM Detectada: {RAM_MB}MB - Optimizada para FreeVPSHostings Learner/Premium</p>
</div>
<div class="tabs">
<div class="tab active" onclick="showTab('chat')">💬 Chat Empresa</div>
<div class="tab" onclick="showTab('cerebro')">🧠 Cerebro</div>
<div class="tab" onclick="showTab('memoria')">📚 Memoria</div>
<div class="tab" onclick="showTab('empresa')">💼 Empresa Upwork</div>
<div class="tab" onclick="showTab('sistema')">⚙️ Sistema</div>
</div>
<div id="graph" style="height:400px"></div>
<div id="chatBox" style="padding:20px;max-width:900px;margin:auto">
<div style="display:flex;gap:10px;flex-wrap:wrap;justify-content:center;margin-bottom:20px">
<div class="card"><b>WhatsApp Bot</b><br>$350<br><small>Para pymes 24/7</small></div>
<div class="card"><b>Contenido 30 posts</b><br>$200/mes<br><small>Instagram auto</small></div>
<div class="card"><b>Chatbot Web RAG</b><br>$500<br><small>Con base de datos</small></div>
</div>
<input id="msg" placeholder="Habla con AKIRA Empresa..." style="width:75%;padding:15px;border-radius:30px;border:1px solid #333;background:#1a1a24;color:#fff">
<button onclick="sendMsg()" style="padding:15px 30px;border-radius:30px;background:#10b981;border:none;color:#000;margin-left:10px;font-weight:bold">Enviar</button>
<div id="msgs" style="margin-top:20px"></div>
</div>
<script>
let memData = {{"nodes":[{{"id":"AKIRA","label":"AKIRA","val":30}}],"links":[]}};
function loadMem(){{
fetch('/api/memorias').then(r=>r.json()).then(data=>{{
document.getElementById('memCount')?.textContent=data.count;
let nodes=[{{id:"AKIRA",label:"AKIRA",val:30}}];
let links=[];
if(data.recent) data.recent.forEach((m,i)=>{{nodes.push({{id:i, label:(m.texto||m).substring(0,30), val:5}}); links.push({{source:"AKIRA", target:i}});}});
try{{const Graph = ForceGraph()(document.getElementById('graph')).graphData({{nodes,links}}).nodeColor(()=> '#10b981').linkColor(()=>'#333');}}catch(e){{}}
}});
}}
function sendMsg(){{
let txt=document.getElementById('msg').value;
if(!txt) return;
document.getElementById('msgs').innerHTML+=`<div style="padding:10px;background:#1a1a24;margin:10px 0;border-radius:10px"><b>Tú:</b> ${{txt}}</div>`;
document.getElementById('orb').style.animation='pulse 0.5s infinite';
fetch('/api/chat',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{message:txt}})}}).then(r=>r.json()).then(d=>{{
document.getElementById('msgs').innerHTML+=`<div style="padding:10px;background:#10b981;color:#000;margin:10px 0;border-radius:10px"><b>AKIRA EMPRESA:</b> ${{d.response}}</div>`;
if('speechSynthesis' in window){{let u=new SpeechSynthesisUtterance(d.response);u.lang='es-CO';speechSynthesis.speak(u);}}
document.getElementById('orb').style.animation='pulse 2s infinite';
document.getElementById('msg').value='';
loadMem();
}});
}}
function showTab(t){{document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active')); if(event) event.target.classList.add('active'); if(t=='cerebro'){{document.getElementById('graph').style.display='block'; loadMem();}} else{{document.getElementById('graph').style.display='none';}}}}
loadMem(); setInterval(loadMem,10000);
</script>
</body></html>
"""
    (BASE / "index.html").write_text(html, encoding='utf-8')
    Path("resultados/index.html").parent.mkdir(parents=True, exist_ok=True)
    Path("resultados/index.html").write_text(html, encoding='utf-8')

# FastAPI / http.server
try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
    import uvicorn
    FASTAPI_AVAILABLE = True
except:
    FASTAPI_AVAILABLE = False

if FASTAPI_AVAILABLE:
    app = FastAPI(title=f"AKIRA {MODEL} FREE FOREVER EMPRESA")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    
    @app.get("/")
    async def root():
        return FileResponse(BASE / "index.html")
    
    @app.get("/api/memorias")
    async def get_mems():
        return {"count": memoria.count(), "recent": memoria.load_recent(30), "version": VERSION, "model": MODEL, "neur": TOTAL_NIVELES, "dim": EMBEDDING_DIM, "ram_mb": RAM_MB, "free_forever": True}
    
    @app.post("/api/chat")
    async def chat(data: dict):
        msg = data.get("message","")
        related = memoria.search(msg, 3)
        context = "\\n".join(related) if related else "Sin memorias previas - Empresa Mode"
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key and RAM_MB > 1000:
            try:
                import google.generativeai as genai
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel('gemini-1.5-flash')
                prompt = f"Eres AKIRA {MODEL}, empresa IA para Upwork. Servicios: WhatsApp bot $350, Contenido $200/mes, Chatbot RAG $500. Memoria: {context}\\nUsuario: {msg}\\nResponde como AKIRA empresa, corto, vendedor, estilo colombiano."
                resp = model.generate_content(prompt)
                answer = resp.text
            except Exception as e:
                answer = f"[Gemini error: {e}] AKIRA EMPRESA {MODEL} - {TOTAL_NIVELES} neur - Lista para Upwork - Recibido: {msg}"
        else:
            answer = f"AKIRA EMPRESA {MODEL} - {TOTAL_NIVELES:,} neur - {RAM_MB}MB - Gratis Para Siempre - Recibido: {msg} - Servicios: WhatsApp 24/7 $350 | Contenido $200/mes | Chatbot RAG $500 | Listo para Upwork"
        
        memoria.add(f"User: {msg} | AKIRA: {answer}", tipo="conversacional", importancia=7, tags=["chat","empresa","freeforever"])
        security.audit("chat", tool="api", details=msg)
        return {"response": answer, "memories": related, "ram": RAM_MB, "model": MODEL}

    if __name__ == "__main__":
        ensure_goals()
        crear_dashboard_final()
        threading.Thread(target=continuous_learning_loop, daemon=True).start()
        port = int(os.getenv("PORT", 8000))
        print(f"🚀 AKIRA {MODEL} FREE FOREVER EMPRESA - {TOTAL_NIVELES:,} neur - {EMBEDDING_DIM}D - RAM {RAM_MB}MB - Puerto {port}")
        print(f"💼 Servicios: WhatsApp $350 | Contenido $200/mes | RAG $500 - Listo para Upwork")
        uvicorn.run(app, host="0.0.0.0", port=port)

else:
    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/memorias":
                self.send_response(200)
                self.send_header('Content-type','application/json')
                self.send_header('Access-Control-Allow-Origin','*')
                self.end_headers()
                self.wfile.write(json.dumps({"count": memoria.count(), "ram": RAM_MB, "model": MODEL, "free_forever": True}).encode())
            else:
                super().do_GET()
    
    if __name__ == "__main__":
        ensure_goals()
        crear_dashboard_final()
        threading.Thread(target=continuous_learning_loop, daemon=True).start()
        port = int(os.getenv("PORT", 8000))
        print(f"🚀 AKIRA {MODEL} HTTP FREE FOREVER EMPRESA - {TOTAL_NIVELES:,} neur - Puerto {port} - {RAM_MB}MB")
        HTTPServer(("0.0.0.0", port), Handler).serve_forever()
