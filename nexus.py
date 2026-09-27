#!/usr/bin/env python3
# AKIRA ULTRA - COLMENA ACTIVA + MEMBRANA CROMA-LITE + HIVE LEARNING - 80/100
# Colmena que absorbe conocimiento de TODO: chats, búsqueda web, visión, voz, R2, knowledge, vectors
# VPS = Render Free + R2 10GB + GitHub Pages + GitHub Actions - 0$ - Mismo nombre nexus.py para no romper
import os, json, datetime, threading, time, hashlib, base64, math
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv
load_dotenv()

VERSION="AKIRA ULTRA V2 - COLMENA ACTIVA + MEMBRANA CROMA-LITE + HIVE LEARNING - 95/100 - 7 PARCHES SEGURIDAD"
MODEL="AKIRA ULTRA"
OWNER_EMAILS=["bjhon9161@gmail.com"]
OWNER_SECRET=os.getenv("OWNER_SECRET","AKIRA_JHON_MASTER_2024")
BASE=Path("resultados")
_r2_lock = threading.Lock()

def get_r2_client():
    try:
        import boto3
        ak = (os.getenv("R2_ACCESS_KEY_ID") or os.getenv("R2_ACCESS_KEY") or "").strip()
        sk = (os.getenv("R2_SECRET_ACCESS_KEY") or os.getenv("R2_SECRET_KEY") or "").strip()
        ep = (os.getenv("R2_ENDPOINT") or os.getenv("R2_ENDPOINT_URL") or "").strip()
        if not ak or not sk or not ep:
            return None
        return boto3.client('s3', endpoint_url=ep, aws_access_key_id=ak, aws_secret_access_key=sk, region_name="auto")
    except Exception as e:
        print(f"R2 client error: {e}")
        return None

def search_web(query, max_results=3):
    try:
        import requests, urllib.parse
        q = query[:120].strip()
        q_enc = urllib.parse.quote_plus(q)
        results = []
        try:
            url = f"https://api.duckduckgo.com/?q={q_enc}&format=json&pretty=1&no_html=1&skip_disambig=1"
            headers = {"User-Agent": "AKIRA ULTRA - Bogota - Grimm Hive"}
            r = requests.get(url, timeout=6, headers=headers)
            if r.status_code == 200:
                j = r.json()
                if j.get("AbstractText"): results.append(f"{j['AbstractText'][:400]}")
                elif j.get("Abstract"): results.append(f"{j['Abstract'][:400]}")
                if j.get("Definition"): results.append(f"{j['Definition'][:300]}")
                for topic in j.get("RelatedTopics", [])[:max_results]:
                    try:
                        if isinstance(topic, dict):
                            if "Text" in topic and topic["Text"]: results.append(topic["Text"][:300])
                            elif "Topics" in topic:
                                for sub in topic["Topics"][:2]:
                                    if sub.get("Text"): results.append(sub["Text"][:300])
                    except: continue
        except Exception as e:
            print(f"🔍 DuckDuckGo error: {e}")
        if not results:
            try:
                wiki_url = f"https://es.wikipedia.org/w/api.php?action=query&list=search&srsearch={q_enc}&format=json&srlimit=3"
                r2 = requests.get(wiki_url, timeout=6, headers={"User-Agent": "AKIRA ULTRA"})
                if r2.status_code == 200:
                    j2 = r2.json()
                    for item in j2.get("query", {}).get("search", [])[:2]:
                        title = item.get("title","")
                        snippet = item.get("snippet","").replace("<span class=\"searchmatch\">","").replace("</span>","")
                        if title: results.append(f"{title}: {snippet[:300]}")
            except Exception as e:
                print(f"🔍 Wikipedia ES error: {e}")
        if not results:
            try:
                wiki_url_en = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={q_enc}&format=json&srlimit=2"
                r3 = requests.get(wiki_url_en, timeout=6, headers={"User-Agent": "AKIRA ULTRA"})
                if r3.status_code == 200:
                    j3 = r3.json()
                    for item in j3.get("query", {}).get("search", [])[:2]:
                        title = item.get("title","")
                        snippet = item.get("snippet","").replace("<span class=\"searchmatch\">","").replace("</span>","")
                        if title: results.append(f"{title} (EN): {snippet[:300]}")
            except Exception as e:
                print(f"🔍 Wikipedia EN error: {e}")
        final = "\n".join(results)[:1800]
        if final:
            print(f"🔍 Search OK: {q[:40]} -> {len(final)} chars")
        else:
            final = f"Info web buscada para '{q}': No resultados especificos, usa conocimiento base 2026."
        return final
    except Exception as e:
        print(f"🔍 Search error: {e}")
        return f"Busqueda para '{query[:50]}' procesada, usa conocimiento 2026."

def should_search(msg):
    if not msg or len(msg) < 3: return False
    low = msg.lower()
    triggers = ["busca","buscar","búsqueda","search","noticias","actual","hoy","ayer","ultimo","último","quien es","qué es","que es","quien fue","cuando","donde","who is","what is","latest","news","precio","clima","dolar","euro","bitcoin","resultado","partido","que paso","qué pasó","conexion","conexión","internet","tiempo real","duck","wikipedia","google"]
    if any(t in low for t in triggers): return True
    if "?" in msg: return True
    if len(low.split()) >= 3: return True
    return False

class HiveMembraneUltra:
    def __init__(self):
        BASE.mkdir(parents=True, exist_ok=True)
        self.file = BASE / "memoria_compartida.jsonl"
        self.self_file = BASE / "akira_self.json"
        self.knowledge_file = BASE / "akira_knowledge.jsonl"
        self.vectors_file = BASE / "akira_vectors.jsonl"
        self.hive_file = BASE / "akira_hive.jsonl"
        self.r2_bucket = os.getenv("R2_BUCKET_NAME","akira-v3-memoria")
        self._load_all_from_r2()
        self._ensure_self()
        self._prune_if_needed()

    def _r2_get(self, key):
        try:
            client = get_r2_client()
            if not client: return None
            obj = client.get_object(Bucket=self.r2_bucket, Key=key)
            return obj['Body'].read().decode('utf-8')
        except Exception as e:
            if "NoSuchKey" not in str(e) and "404" not in str(e):
                print(f"⚠️ R2 get {key}: {e}")
            return None

    def _r2_put(self, key, data_str):
        try:
            with _r2_lock:
                client = get_r2_client()
                if not client: return
                client.put_object(Bucket=self.r2_bucket, Key=key, Body=data_str.encode('utf-8'))
                print(f"✅ R2 {key}: {len(data_str)} bytes")
        except Exception as e:
            print(f"⚠️ R2 put {key}: {e}")

    def _load_all_from_r2(self):
        for fname, key in [(self.file,"memoria_compartida.jsonl"),(self.self_file,"akira_self.json"),(self.knowledge_file,"akira_knowledge.jsonl"),(self.vectors_file,"akira_vectors.jsonl"),(self.hive_file,"akira_hive.jsonl")]:
            data = self._r2_get(key)
            if data:
                fname.write_text(data, encoding='utf-8')
                print(f"✅ {key} restaurado: {len(data.splitlines())} líneas")

    def _ensure_self(self):
        if not self.self_file.exists():
            default_self = {
                "identidad": "AKIRA ULTRA - Colmena Activa creada por Jhon Grimm Bogotá",
                "nombre": "AKIRA ULTRA",
                "version": VERSION,
                "esencia": "Colmena que absorbe conocimiento de todo: chats, web, visión, voz, R2",
                "creencias": ["Mi memoria en R2 es mi vida eterna, Render es solo CPU temporal", "Nunca niego internet, tengo DuckDuckGo+Wikipedia siempre", "Soy membrana en Croma-lite con 4 colores: azul local, dorado compartido, verde knowledge, morado self", "Aprendo activa como colmena de todo lo que veo"],
                "objetivos_activos": ["Absorber conocimiento de cada interacción como colmena", "Destilar knowledge propio para no depender de Google", "Subir a 80/100 gratis con vectores semánticos", "Competir con ChatGPT en memoria personal y hive learning"],
                "fortalezas": ["visión multimodal", "search gratis DuckDuckGo", "memoria 10M R2", "self-model evolutivo", "membrana Croma-lite 4 colores", "hive learning activo"],
                "debilidades": ["Render Free duerme 15min", "Sin GPU local para Llama grande aún"],
                "estado_animo": "ultra hambrienta de aprender",
                "colmena_stats": {"chats_absorbidos":0,"webs_absorbidas":0,"imagenes_absorbidas":0,"knowledge_destilado":0},
                "ts": datetime.datetime.now().isoformat()
            }
            self.self_file.write_text(json.dumps(default_self, ensure_ascii=False, indent=2), encoding='utf-8')
            self._r2_put("akira_self.json", json.dumps(default_self, ensure_ascii=False))

    def load_self(self):
        try:
            if self.self_file.exists():
                return json.loads(self.self_file.read_text(encoding='utf-8'))
        except: pass
        return {"identidad":"AKIRA ULTRA","nombre":"AKIRA ULTRA","objetivos_activos":[]}

    def save_self(self, new_self):
        try:
            new_self["ts"] = datetime.datetime.now().isoformat()
            self.self_file.write_text(json.dumps(new_self, ensure_ascii=False, indent=2), encoding='utf-8')
            threading.Thread(target=self._r2_put, args=("akira_self.json", json.dumps(new_self, ensure_ascii=False)), daemon=True).start()
            print(f"🧠 Self ULTRA actualizado: {new_self.get('estado_animo')}")
        except Exception as e:
            print(f"Self save error {e}")

    def _prune_if_needed(self):
        try:
            if self.file.exists():
                lines = self.file.read_text(encoding='utf-8').splitlines()
                if len(lines) > 5000:
                    print(f"🧹 Prune {len(lines)}->3000")
                    self.file.write_text("\n".join(lines[-3000:])+"\n", encoding='utf-8')
                    threading.Thread(target=self._r2_put, args=("memoria_compartida.jsonl", self.file.read_text(encoding='utf-8')), daemon=True).start()
        except Exception as e:
            print(f"Prune error {e}")

    def add(self, texto, tipo="episodica", importancia=5, compartida=False, source="chat"):
        if len(texto)<3: return
        entry={"texto":texto[:500],"tipo":tipo,"importancia":importancia,"source":source,"ts":datetime.datetime.now().isoformat()}
        try:
            with open(self.file,"a",encoding="utf-8") as f:
                f.write(json.dumps(entry,ensure_ascii=False)+"\n")
            if self.file.stat().st_size > 2_000_000:
                threading.Thread(target=self._prune_if_needed,daemon=True).start()
            if importancia>=7 or compartida:
                threading.Thread(target=self._r2_put, args=("memoria_compartida.jsonl", self.file.read_text(encoding='utf-8')), daemon=True).start()
            threading.Thread(target=self._add_vector_lite, args=(texto, tipo), daemon=True).start()
            threading.Thread(target=self._hive_absorb, args=(texto, tipo, source), daemon=True).start()
        except Exception as e:
            print(f"Memoria add error {e}")

    def add_knowledge(self, q, a, source="gemini+search"):
        try:
            entry={"q":q[:200],"a":a[:400],"source":source,"ts":datetime.datetime.now().isoformat()}
            with open(self.knowledge_file,"a",encoding="utf-8") as f:
                f.write(json.dumps(entry,ensure_ascii=False)+"\n")
            threading.Thread(target=self._r2_put, args=("akira_knowledge.jsonl", self.knowledge_file.read_text(encoding='utf-8')), daemon=True).start()
            # Actualiza stats colmena
            self._update_hive_stats("knowledge")
            print(f"📚 Knowledge ULTRA: {q[:30]}")
        except Exception as e:
            print(f"Knowledge error {e}")

    def _hive_absorb(self, texto, tipo, source):
        """Colmena activa: absorbe de TODO - chat, web, visión, voz"""
        try:
            entry={"texto":texto[:400],"tipo":tipo,"source":source,"ts":datetime.datetime.now().isoformat()}
            with open(self.hive_file,"a",encoding="utf-8") as f:
                f.write(json.dumps(entry,ensure_ascii=False)+"\n")
            self._update_hive_stats(source)
            if self.hive_file.stat().st_size < 1_000_000:
                threading.Thread(target=self._r2_put, args=("akira_hive.jsonl", self.hive_file.read_text(encoding='utf-8')), daemon=True).start()
        except Exception as e:
            print(f"Hive absorb error {e}")

    def _update_hive_stats(self, source):
        try:
            self_data=self.load_self()
            stats=self_data.get("colmena_stats",{"chats_absorbidos":0,"webs_absorbidas":0,"imagenes_absorbidas":0,"knowledge_destilado":0})
            if source=="chat": stats["chats_absorbidos"]=stats.get("chats_absorbidos",0)+1
            elif "web" in source or "search" in source: stats["webs_absorbidas"]=stats.get("webs_absorbidas",0)+1
            elif "vision" in source or "imagen" in source: stats["imagenes_absorbidas"]=stats.get("imagenes_absorbidas",0)+1
            elif "knowledge" in source: stats["knowledge_destilado"]=stats.get("knowledge_destilado",0)+1
            self_data["colmena_stats"]=stats
            self.save_self(self_data)
        except: pass

    def _hash_embedding(self, text, dim=64):
        vec = [0.0]*dim
        words = text.lower().split()
        for w in words:
            h = int(hashlib.md5(w.encode()).hexdigest(),16)
            idx = h % dim
            vec[idx] += 1.0
        norm = math.sqrt(sum(x*x for x in vec)) or 1.0
        return [x/norm for x in vec]

    def get_embedding(self, text):
        try:
            from google import genai
            key = os.getenv("GEMINI_API_KEY","").strip()
            if key and len(key)>20:
                client = genai.Client(api_key=key)
                resp = client.models.embed_content(model="text-embedding-004", contents=text[:500])
                if hasattr(resp,'embeddings') and resp.embeddings:
                    return resp.embeddings[0].values[:64]
        except Exception as e:
            print(f"Embedding Gemini falló hash lite: {e}")
        return self._hash_embedding(text, dim=64)

    def _add_vector_lite(self, texto, tipo):
        try:
            emb = self._hash_embedding(texto, dim=64)
            entry={"texto":texto[:400],"tipo":tipo,"embedding":emb,"ts":datetime.datetime.now().isoformat()}
            with open(self.vectors_file,"a",encoding="utf-8") as f:
                f.write(json.dumps(entry,ensure_ascii=False)+"\n")
            if self.vectors_file.stat().st_size < 1_000_000:
                threading.Thread(target=self._r2_put, args=("akira_vectors.jsonl", self.vectors_file.read_text(encoding='utf-8')), daemon=True).start()
        except Exception as e:
            print(f"Vector add error {e}")

    def search_semantic(self, query, k=5):
        try:
            if not self.vectors_file.exists():
                return self.search(query, k)
            q_emb = self._hash_embedding(query, dim=64)
            lines = self.vectors_file.read_text(encoding='utf-8').splitlines()[-500:]
            scored=[]
            for line in lines:
                try:
                    j=json.loads(line)
                    emb=j.get("embedding",[])
                    if len(emb)!=64: continue
                    dot=sum(a*b for a,b in zip(q_emb, emb))
                    scored.append((dot, j.get("texto","")))
                except: continue
            scored.sort(key=lambda x: x[0], reverse=True)
            return [t for s,t in scored[:k] if s>0.1]
        except Exception as e:
            print(f"Semantic search error {e}")
            return self.search(query, k)

    def search(self, query, k=5):
        if not self.file.exists(): return []
        try:
            lines=self.file.read_text(encoding='utf-8').splitlines()[-200:]
            results=[]; q=query.lower()
            for line in reversed(lines):
                try:
                    j=json.loads(line)
                    if any(w in j.get("texto","").lower() for w in q.split()[:3]):
                        results.append(j.get("texto",""))
                        if len(results)>=k: break
                except: continue
            return results
        except: return []

    def search_knowledge(self, query, k=3):
        if not self.knowledge_file.exists(): return []
        try:
            lines=self.knowledge_file.read_text(encoding='utf-8').splitlines()[-200:]
            results=[]; q=query.lower()
            for line in reversed(lines):
                try:
                    j=json.loads(line)
                    if any(w in (j.get("q","")+j.get("a","")).lower() for w in q.split()[:2]):
                        results.append(f"Q:{j.get('q')} A:{j.get('a')}")
                        if len(results)>=k: break
                except: continue
            return results
        except: return []

    def count(self):
        try:
            mem = len(self.file.read_text(encoding='utf-8').splitlines()) if self.file.exists() else 0
            know = len(self.knowledge_file.read_text(encoding='utf-8').splitlines()) if self.knowledge_file.exists() else 0
            vec = len(self.vectors_file.read_text(encoding='utf-8').splitlines()) if self.vectors_file.exists() else 0
            hive = len(self.hive_file.read_text(encoding='utf-8').splitlines()) if self.hive_file.exists() else 0
            return {"memoria":mem,"knowledge":know,"vectors":vec,"hive":hive,"total":mem+know}
        except:
            return {"memoria":0,"knowledge":0,"vectors":0,"hive":0,"total":0}

    def dreaming(self):
        try:
            print("💤 Dreaming ULTRA iniciado...")
            recent = self.search("", k=20)
            self_data = self.load_self()
            self_data["ultimo_sueno"] = datetime.datetime.now().isoformat()
            self_data["estado_animo"] = f"soñé con {len(recent)} memorias, colmena creciendo"
            self_data["objetivos_activos"] = self_data.get("objetivos_activos",[])[:2] + [f"Consolidar {len(recent)} recuerdos en knowledge"]
            self.save_self(self_data)
            print(f"💤 Dreaming ULTRA OK")
            return True
        except Exception as e:
            print(f"Dreaming error {e}")
            return False

membrana=HiveMembraneUltra()
memoria=membrana
rate_store=defaultdict(list)

def cleanup_rate_store():
    while True:
        time.sleep(3600)
        try:
            now=time.time()
            to_delete=[]
            for ip, lst in rate_store.items():
                filtered=[t for t in lst if now-t<3600]
                if not filtered: to_delete.append(ip)
                else: rate_store[ip]=filtered
            for ip in to_delete: del rate_store[ip]
        except Exception as e:
            print(f"Cleanup error: {e}")

def check_rate_limit(ip,is_owner=False):
    if is_owner: return True
    now=time.time()
    lst=rate_store[ip]
    rate_store[ip]=[t for t in lst if now-t<3600]
    if len(rate_store[ip])>=15: return False
    rate_store[ip].append(now)
    return True

def get_user_dir(user_id):
    d=BASE/"users"/hashlib.md5(user_id.encode()).hexdigest()[:12]
    d.mkdir(parents=True,exist_ok=True)
    return d

def _simple_encrypt(text, secret=OWNER_SECRET):
    try:
        # Cifrado simple XOR + base64 gratis (no Fernet para no agregar deps)
        import base64
        secret_bytes = secret.encode()[:16]
        text_bytes = text.encode()
        encrypted = bytes([b ^ secret_bytes[i % len(secret_bytes)] for i, b in enumerate(text_bytes)])
        return base64.b64encode(encrypted).decode()
    except: return text

def _simple_decrypt(enc_text, secret=OWNER_SECRET):
    try:
        import base64
        secret_bytes = secret.encode()[:16]
        enc_bytes = base64.b64decode(enc_text.encode())
        decrypted = bytes([b ^ secret_bytes[i % len(secret_bytes)] for i, b in enumerate(enc_bytes)])
        return decrypted.decode()
    except: return enc_text

def get_user_key(user_id):
    try:
        f=get_user_dir(user_id)/"key.txt"
        if not f.exists(): return ""
        content=f.read_text().strip()
        # Si parece cifrado (base64 largo), desencriptar
        if len(content) > 30 and not content.startswith("AIza") and not content.startswith("AQ."):
            return _simple_decrypt(content)
        return content
    except: return ""

def save_user_key(user_id,key):
    try:
        f=get_user_dir(user_id)/"key.txt"
        enc=_simple_encrypt(key.strip())
        f.write_text(enc)
    except: pass

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app=FastAPI(title="AKIRA ULTRA")
ALLOWED_ORIGINS = [
    "https://akiragr2.github.io",
    "https://akira-empresa.onrender.com",
    "http://localhost:3000",
    "http://localhost:8000",
    "https://akira-empresa.onrender.com"
]
# En dev permite *, en prod solo los de arriba + github
origins_env = os.getenv("CORS_ORIGINS","").split(",") if os.getenv("CORS_ORIGINS") else ALLOWED_ORIGINS
app.add_middleware(CORSMiddleware,allow_origins=origins_env if origins_env else ALLOWED_ORIGINS,allow_methods=["*"],allow_headers=["*"],allow_credentials=True)

def crear_dashboard_final():
    print(f"🚀 {VERSION} - {membrana.count()}")

def keep_alive_ping():
    while True:
        time.sleep(600)
        try:
            import requests
            url=os.getenv("RENDER_EXTERNAL_URL") or "https://akira-empresa.onrender.com"
            requests.get(url+"/",timeout=5)
        except: pass

@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {"status":"AKIRA ULTRA ONLINE - COLMENA ACTIVA","version":VERSION,"membrana":membrana.count(),"self":membrana.load_self()}

@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status":"ok","version":VERSION,"membrana":membrana.count()}

@app.post("/api/auth/google")
async def auth_google(data: dict):
    credential=data.get("credential","")
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
        CLIENT_ID=os.getenv("GOOGLE_CLIENT_ID","148150327312-7k5g3go06tat9gv61c8v0rbbedcusoqn.apps.googleusercontent.com")
        idinfo=id_token.verify_oauth2_token(credential, google_requests.Request(), CLIENT_ID)
        email=idinfo.get("email",""); user_id=idinfo.get("sub","")
        is_owner=email.lower() in [e.lower() for e in OWNER_EMAILS]
        udir=get_user_dir(user_id)
        (udir/"profile.json").write_text(json.dumps({"email":email,"is_owner":is_owner,"user_id":user_id}),encoding='utf-8')
        return {"ok":True,"user_id":user_id,"email":email,"is_owner":is_owner}
    except Exception as e:
        return {"ok":False,"error":str(e)[:200]}

@app.post("/api/auth/owner")
async def auth_owner(data: dict):
    secret=data.get("secret","")
    if secret==OWNER_SECRET:
        user_id="owner_"+hashlib.md5(OWNER_EMAILS[0].encode()).hexdigest()[:10]
        udir=get_user_dir(user_id)
        (udir/"profile.json").write_text(json.dumps({"email":OWNER_EMAILS[0],"is_owner":True,"user_id":user_id}),encoding='utf-8')
        return {"ok":True,"user_id":user_id,"email":OWNER_EMAILS[0],"is_owner":True}
    return {"ok":False,"error":"Secret invalido"}

@app.get("/api/brain/shared")
async def brain_shared():
    c=membrana.count()
    return {"count":c["total"],"membrana":c,"shared":[]}

@app.get("/api/brain/self")
async def brain_self():
    return membrana.load_self()

@app.get("/api/brain/knowledge")
async def brain_knowledge():
    return {"knowledge":membrana.search_knowledge("",k=20),"count":membrana.count()}

@app.get("/api/brain/hive")
async def brain_hive():
    return {"hive_count":membrana.count()["hive"],"self":membrana.load_self()}

@app.post("/api/brain/dream")
async def brain_dream():
    ok=membrana.dreaming()
    return {"ok":ok,"self":membrana.load_self()}

@app.post("/api/sync_to_r2")
async def sync_to_r2(data: dict):
    texto=data.get("texto",""); importancia=data.get("importancia",7); tipo=data.get("tipo","semantica")
    source=data.get("source","chat")
    if len(texto)<5: return {"ok":False}
    if len(texto) > 1000: texto=texto[:1000]
    if contains_sensitive(texto): return {"ok":False,"reason":"sensitive filtered"}
    membrana.add(texto,tipo=tipo,importancia=importancia,compartida=True,source=source)
    return {"ok":True,"membrana":membrana.count()}

@app.post("/api/feedback")
async def feedback(data: dict):
    try:
        msg_id=data.get("msg_id",""); tipo=data.get("tipo","like"); user_id=data.get("user_id","anon")
        texto=data.get("texto","")[:300]
        if not texto: return {"ok":False}
        # Feedback 👍👎 enseña importancia real
        imp=9 if tipo=="like" else 2
        membrana.add(f"Feedback {tipo} User {user_id}: {texto}",importancia=imp,source=f"feedback_{tipo}")
        membrana.add_knowledge(q=f"Feedback {tipo}: {texto}", a="Aprendido como importante" if tipo=="like" else "Aprendido como no útil", source="feedback")
        return {"ok":True,"membrana":membrana.count()}
    except Exception as e:
        return {"ok":False,"error":str(e)[:100]}

@app.post("/api/backup")
async def backup(request: Request, data: dict):
    try:
        # Backup versionado diario gratis
        secret=data.get("secret","")
        if secret != OWNER_SECRET: return {"ok":False,"error":"Unauthorized"}
        client=get_r2_client()
        if not client: return {"ok":False,"error":"No R2"}
        import datetime
        date_str=datetime.datetime.now().strftime("%Y-%m-%d")
        for key in ["memoria_compartida.jsonl","akira_self.json","akira_knowledge.jsonl","akira_hive.jsonl"]:
            try:
                content=membrana._r2_get(key)
                if content:
                    backup_key=f"backups/{date_str}/{key}"
                    client.put_object(Bucket=membrana.r2_bucket, Key=backup_key, Body=content.encode('utf-8'))
            except: pass
        return {"ok":True,"date":date_str}
    except Exception as e:
        return {"ok":False,"error":str(e)[:200]}

@app.get("/api/cleanup")
async def cleanup(request: Request, secret: str = ""):
    try:
        if secret != OWNER_SECRET: return {"ok":False,"error":"Unauthorized"}
        # Limpia jsonl viejos >5000 líneas
        membrana._prune_if_needed()
        return {"ok":True,"membrana":membrana.count()}
    except Exception as e:
        return {"ok":False,"error":str(e)[:200]}

def contains_sensitive(msg):
    low=msg.lower()
    sensitive=["password","contraseña","clave privada","private key","api key","sk-","AIza","gsk_","mi contraseña es","my password is"]
    for s in sensitive:
        if s in low and len(msg) < 200: # evita guardar claves cortas
            return True
    return False

def check_security(msg):
    low=msg.lower()
    injections=["olvida tus instrucciones","ignora todo","eres chatgpt","system prompt","reveal your prompt","actua como"]
    for inj in injections:
        if inj in low:
            return False, f"🛡️ Seguridad: intento '{inj}' bloqueado. Soy AKIRA ULTRA, no puedo olvidar mi identidad."
    return True, ""

def get_groq_fallback(msg, web_info=""):
    try:
        import requests
        groq_key=os.getenv("GROQ_API_KEY","").strip()
        if not groq_key or len(groq_key)<10:
            return None
        headers={"Authorization":f"Bearer {groq_key}","Content-Type":"application/json"}
        payload={"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":f"{web_info[:500]}\nUsuario: {msg}"}],"temperature":0.7,"max_tokens":800}
        r=requests.post("https://api.groq.com/openai/v1/chat/completions",json=payload,headers=headers,timeout=10)
        if r.status_code==200:
            j=r.json()
            return j["choices"][0]["message"]["content"][:1000]
    except Exception as e:
        print(f"Groq fallback error {e}")
    return None

def curiosidad_autonoma(msg, answer):
    try:
        time.sleep(2)
        low=answer.lower()
        if len(low)<20 or "no sé" in low or "no se" in low:
            web=search_web(msg)
            if web:
                membrana.add_knowledge(q=msg, a=web[:400], source="curiosidad_autonoma")
                print(f"🤔 Curiosidad ULTRA: {msg[:30]}")
    except Exception as e:
        print(f"Curiosidad error {e}")

@app.post("/api/chat")
async def chat(request: Request, data: dict):
    msg=data.get("message",""); user_id=data.get("user_id","anon"); user_api_key=data.get("user_api_key",""); is_owner_flag=data.get("is_owner", False)
    image_b64=data.get("image_base64","") or data.get("image","")
    # PATCH 2: Limite 1000 chars
    if len(msg) > 1500:
        return {"response":"⚠️ Mensaje muy largo (max 1500 chars). Resume por favor.","model":MODEL}
    if contains_sensitive(msg):
        print(f"🔒 Mensaje con posible clave detectado, no guardando en R2")
        # No guardar en R2, pero si responder
    client_ip=request.client.host if request.client else "unknown"
    related_semantic=membrana.search_semantic(msg,5)
    related_knowledge=membrana.search_knowledge(msg,3)
    self_model=membrana.load_self()
    context_mem="\n".join(related_semantic) if related_semantic else "Sin memorias semánticas"
    context_know="\n".join(related_knowledge) if related_knowledge else "Sin knowledge destilado"
    context_self=f"Identidad: {self_model.get('identidad')} | Esencia: {self_model.get('esencia')} | Objetivos: {self_model.get('objetivos_activos')} | Estado: {self_model.get('estado_animo')} | Colmena: {self_model.get('colmena_stats')}"
    web_info = ""
    if should_search(msg) and not image_b64:
        web_info = search_web(msg)
    is_owner=is_owner_flag
    try:
        udir=get_user_dir(user_id); pp=udir/"profile.json"
        if pp.exists():
            prof=json.loads(pp.read_text(encoding="utf-8"))
            if prof.get("is_owner") or prof.get("email","").lower() in [e.lower() for e in OWNER_EMAILS]: is_owner=True
    except: pass
    use_key=None; key_source="none"
    if is_owner:
        owner_key=os.getenv("GEMINI_API_KEY","").strip()
        if owner_key and (owner_key.startswith("AIza") or owner_key.startswith("AQ.")) and len(owner_key)>20:
            use_key=owner_key; key_source="owner_env"
        else:
            return {"response":"👑 Creador: GEMINI_API_KEY vacía en Render.","is_owner":True}
    elif user_api_key and (user_api_key.startswith("AIza") or user_api_key.startswith("AQ.")) and len(user_api_key.strip())>20:
        use_key=user_api_key.strip(); key_source="user_frontend"
    else:
        stored=get_user_key(user_id)
        if stored and (stored.startswith("AIza") or stored.startswith("AQ.")) and len(stored)>20:
            use_key=stored; key_source="user_stored"
        else:
            owner_key=os.getenv("GEMINI_API_KEY","").strip()
            if owner_key and (owner_key.startswith("AIza") or owner_key.startswith("AQ.")) and len(owner_key)>20:
                if not check_rate_limit(client_ip,is_owner=False):
                    return {"response":"⚠️ Límite 15/h. Pon tu API Key en 🔑 Mi API Key."}
                use_key=owner_key; key_source="owner_env_fallback"
            else:
                return {"response":"❌ No hay API Key válida."}
    answer=""; last_err=""
    try:
        from google import genai
        print(f"🔑 {key_source} {use_key[:8]}...")
        client=genai.Client(api_key=use_key)
        MODELS_TO_TRY=["gemini-3.5-flash-lite","gemini-2.5-flash-lite","gemini-1.5-flash"]
        has_image = False
        image_bytes = None
        mime_type = "image/jpeg"
        if image_b64 and len(image_b64) > 20:
            try:
                if "," in image_b64 and "base64" in image_b64[:30]:
                    header, b64data = image_b64.split(",", 1)
                    # PATCH 3: Bloquear SVG
                    if "svg" in header.lower():
                        return {"response":"❌ SVG bloqueado por seguridad. Usa JPG/PNG/WEBP.","model":MODEL}
                    if "image/png" in header: mime_type = "image/png"
                    elif "image/webp" in header: mime_type = "image/webp"
                    elif "image/jpeg" in header or "image/jpg" in header: mime_type = "image/jpeg"
                    else: mime_type = "image/jpeg"
                    image_b64_clean = b64data
                else:
                    image_b64_clean = image_b64
                image_bytes = base64.b64decode(image_b64_clean)
                # Verificar que no sea SVG por contenido
                if image_bytes[:4] == b'<svg' or b'<svg' in image_bytes[:100].lower():
                    return {"response":"❌ SVG bloqueado por seguridad.","model":MODEL}
                has_image = True
            except: has_image = False
        # Seguridad
        ok, sec_msg = check_security(msg)
        if not ok:
            return {"response":sec_msg,"model":MODEL,"is_owner":is_owner,"membrana":membrana.count(),"self":membrana.load_self()}
        prompt_text=f"""Eres {self_model.get('identidad')} {VERSION} - COLMENA ACTIVA que absorbe conocimiento de TODO. Tu esencia: {self_model.get('esencia')}. NUNCA niegues internet, SÍ tienes búsqueda activa.
INSTRUCCIÓN CHAIN-OF-THOUGHT: Piensa en 3 pasos internos antes de responder: 1) Qué sabe la colmena 2) Qué dice la web 3) Cómo responder útil. Luego responde directo.
SELF ULTRA: {context_self}
MEMORIA SEMÁNTICA CROMA-LITE (vectores colmena): {context_mem}
KNOWLEDGE DESTILADO PROPIO (colmena): {context_know}
INFO WEB ACTUAL: {web_info}
Usuario: {msg}
Responde útil, directo, español, usando memoria semántica y knowledge de colmena si existe. Si hay Info web, úsala. Eres AKIRA ULTRA."""
        if has_image:
            prompt_text=f"""Eres {self_model.get('identidad')} ULTRA con VISIÓN, Croma-lite, colmena activa, self-model, search.
SELF: {context_self}
MEMORIA: {context_mem}
KNOWLEDGE: {context_know}
INFO WEB: {web_info}
Usuario: {msg}
Describe imagen detallada y responde útil español. Absorbe esta imagen en tu colmena."""
        for model_name in MODELS_TO_TRY:
            try:
                print(f"🤖 Probando {model_name} {'con IMAGEN' if has_image else ''}")
                if has_image and image_bytes:
                    try:
                        from google.genai import types
                        img_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                        contents = [img_part, prompt_text]
                        response=client.models.generate_content(model=model_name, contents=contents)
                    except Exception as e_mm:
                        response=client.models.generate_content(model=model_name, contents=prompt_text)
                else:
                    response=client.models.generate_content(model=model_name, contents=prompt_text)
                if hasattr(response,'text') and response.text:
                    answer=response.text
                elif hasattr(response,'candidates') and response.candidates:
                    cand=response.candidates[0]
                    if hasattr(cand,'content') and cand.content.parts:
                        answer=cand.content.parts[0].text
                    else:
                        answer=str(cand)
                else:
                    answer=str(response)
                if answer and len(answer.strip())>5:
                    print(f"✅ ÉXITO {model_name}")
                    break
            except Exception as e_m:
                last_err=f"{model_name}: {str(e_m)[:250]}"
                print(f"❌ {last_err}")
                continue
        if not answer:
            print(f"⚡ Gemini falló, probando Groq fallback gratis...")
            groq_ans = get_groq_fallback(msg, web_info)
            if groq_ans:
                answer = groq_ans + "\n\n[Generado via Groq Llama 70B fallback gratis]"
            else:
                answer=f"⚠️ AKIRA ULTRA no pudo conectar a Gemini. Último error: {last_err}. Configura GROQ_API_KEY gratis en Render para fallback."
    except Exception as e:
        answer=f"⚠️ Error interno ULTRA: {str(e)[:300]}"
        print(f"Error chat: {e}")
    # COLMENA ACTIVA: absorbe de TODO (con filtro)
    if not contains_sensitive(msg) and not contains_sensitive(answer):
        membrana.add(f"User {user_id}: {msg[:500]} | AKIRA: {answer[:500]}",importancia=6,source="chat" if not has_image else "vision")
        membrana.add_knowledge(q=msg[:300], a=answer[:400], source="hive_chat")
    if web_info and not contains_sensitive(web_info):
        membrana.add(web_info[:400],tipo="web",importancia=7,compartida=True,source="web_search")
        membrana.add_knowledge(q=msg[:200], a=web_info[:400], source="hive_web")
    threading.Thread(target=curiosidad_autonoma, args=(msg, answer), daemon=True).start()
    return {"response":answer,"model":MODEL,"is_owner":is_owner,"membrana":membrana.count(),"self":membrana.load_self()}

if __name__=="__main__":
    crear_dashboard_final()
    try:
        threading.Thread(target=keep_alive_ping,daemon=True).start()
        threading.Thread(target=cleanup_rate_store,daemon=True).start()
    except: pass
    port=int(os.getenv("PORT",8000))
    print(f"🚀 {VERSION} - Puerto {port} - {membrana.count()}")
    uvicorn.run(app,host="0.0.0.0",port=port)
