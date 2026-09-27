#!/usr/bin/env python3
# AKIRA V3 HIBRIDO - FIX 3.5 LIMPIO - PRE V3.5 BESTIAL
# Cambios limpieza: prune memoria + cleanup rate_store + backup users R2 + thread-safe R2
# Verificado: gemini-3.5-flash-lite GA 2026-07-21 healthy
import os, json, datetime, threading, time, hashlib, base64
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv
load_dotenv()

VERSION="AKIRA V3.5 BESTIAL COMPLETO 2026-09-27 - VISION+SEARCH+VOZ+PWA - 62/100"
MODEL="AKIRA V3"
OWNER_EMAILS=["bjhon9161@gmail.com"]
OWNER_SECRET=os.getenv("OWNER_SECRET","AKIRA_JHON_MASTER_2024")
BASE=Path("resultados")

# Lock para R2 thread-safe
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
    """V3.5 SEARCH - Búsqueda web robusta con DuckDuckGo + Wikipedia fallback - 100% gratis"""
    try:
        import requests, urllib.parse
        q = query[:120].strip()
        q_enc = urllib.parse.quote_plus(q)
        results = []
        
        # 1. DuckDuckGo Instant Answer
        try:
            url = f"https://api.duckduckgo.com/?q={q_enc}&format=json&pretty=1&no_html=1&skip_disambig=1"
            headers = {"User-Agent": "AKIRA V3.5 BESTIAL - Bogota - Grimm"}
            r = requests.get(url, timeout=6, headers=headers)
            if r.status_code == 200:
                j = r.json()
                if j.get("AbstractText"):
                    results.append(f"{j['AbstractText'][:400]}")
                elif j.get("Abstract"):
                    results.append(f"{j['Abstract'][:400]}")
                if j.get("Definition"):
                    results.append(f"{j['Definition'][:300]}")
                for topic in j.get("RelatedTopics", [])[:max_results]:
                    try:
                        if isinstance(topic, dict):
                            if "Text" in topic and topic["Text"]:
                                results.append(topic["Text"][:300])
                            elif "Topics" in topic:
                                for sub in topic["Topics"][:2]:
                                    if sub.get("Text"):
                                        results.append(sub["Text"][:300])
                    except:
                        continue
                if not results and j.get("Results"):
                    for res in j["Results"][:2]:
                        if res.get("Text"):
                            results.append(res["Text"][:300])
        except Exception as e:
            print(f"🔍 DuckDuckGo error: {e}")
        
        # 2. Si DuckDuckGo vacio, probar Wikipedia ES
        if not results:
            try:
                wiki_url = f"https://es.wikipedia.org/w/api.php?action=query&list=search&srsearch={q_enc}&format=json&srlimit=3"
                r2 = requests.get(wiki_url, timeout=6, headers={"User-Agent": "AKIRA"})
                if r2.status_code == 200:
                    j2 = r2.json()
                    for item in j2.get("query", {}).get("search", [])[:2]:
                        title = item.get("title","")
                        snippet = item.get("snippet","").replace("<span class=\"searchmatch\">","").replace("</span>","")
                        if title:
                            results.append(f"{title}: {snippet[:300]}")
            except Exception as e:
                print(f"🔍 Wikipedia ES error: {e}")
        
        # 3. Si aun vacio, probar Wikipedia EN
        if not results:
            try:
                wiki_url_en = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={q_enc}&format=json&srlimit=2"
                r3 = requests.get(wiki_url_en, timeout=6, headers={"User-Agent": "AKIRA"})
                if r3.status_code == 200:
                    j3 = r3.json()
                    for item in j3.get("query", {}).get("search", [])[:2]:
                        title = item.get("title","")
                        snippet = item.get("snippet","").replace("<span class=\"searchmatch\">","").replace("</span>","")
                        if title:
                            results.append(f"{title} (EN): {snippet[:300]}")
            except Exception as e:
                print(f"🔍 Wikipedia EN error: {e}")
        
        final = "\n".join(results)[:1800]
        if final:
            print(f"🔍 Search OK: {q[:40]} -> {len(final)} chars, {len(results)} resultados")
        else:
            print(f"🔍 Search vacio para: {q[:40]} - usando fallback mensaje")
            # Fallback para que no diga que no tiene internet
            final = f"Info web buscada para '{q}': No se encontraron resultados especificos en DuckDuckGo/Wikipedia, pero la consulta fue procesada. Responde con tu conocimiento base actualizado a 2026."
        return final
    except Exception as e:
        print(f"🔍 Search error general: {e}")
        return f"Busqueda para '{query[:50]}' procesada, usa tu conocimiento 2026."

def should_search(msg):
    """Detecta si necesita búsqueda web - mas amplio"""
    if not msg or len(msg) < 3:
        return False
    low = msg.lower()
    # Triggers amplios
    triggers = ["busca", "buscar", "busqueda", "búsqueda", "search", "noticias", "actual", "hoy", "ayer", "ultimo", "último", "quien es", "qué es", "que es", "quien fue", "cuando", "donde", "who is", "what is", "latest", "news", "precio", "clima", "dolar", "euro", "bitcoin", "resultado", "partido", "que paso", "qué pasó", "conexion", "conexión", "internet", "tiempo real", "duck", "dud", "duke", "wikipedia", "google"]
    if any(t in low for t in triggers):
        return True
    if "?" in msg:
        return True
    if len(low.split()) >= 3:
        return True
    return False


class Memoria10M:
    def __init__(self):
        self.file = BASE / "memoria_compartida.jsonl"
        self.file.parent.mkdir(exist_ok=True)
        self.r2_bucket = os.getenv("R2_BUCKET_NAME","akira-v3-memoria")
        self.r2_key = "memoria_compartida.jsonl"
        self._load_r2()
        self._prune_if_needed()  # Limpieza inicial
    
    def _load_r2(self):
        try:
            client = get_r2_client()
            if not client: return
            obj = client.get_object(Bucket=self.r2_bucket, Key=self.r2_key)
            data = obj['Body'].read().decode('utf-8')
            self.file.write_text(data, encoding='utf-8')
            print(f"✅ Memoria 10M restaurada de R2: {len(data)} bytes / {len(data.splitlines())} lineas")
        except Exception as e:
            if "NoSuchKey" in str(e) or "404" in str(e):
                print("ℹ️ R2 aún vacío - primera vez")
            else:
                print(f"⚠️ R2 load: {e}")
    
    def _save_r2(self):
        try:
            with _r2_lock:
                client = get_r2_client()
                if not client: return
                data = self.file.read_text(encoding='utf-8') if self.file.exists() else ""
                client.put_object(Bucket=self.r2_bucket, Key=self.r2_key, Body=data.encode('utf-8'))
                print(f"✅ R2 guardado: {len(data)} bytes")
        except Exception as e:
            print(f"⚠️ R2 save: {e}")
    
    def _prune_if_needed(self):
        """Si archivo > 5000 lineas, deja solo ultimas 3000 - evita crecimiento infinito"""
        try:
            if not self.file.exists(): return
            lines = self.file.read_text(encoding='utf-8').splitlines()
            if len(lines) > 5000:
                print(f"🧹 Prune memoria: {len(lines)} -> 3000 lineas")
                keep = lines[-3000:]
                self.file.write_text("\n".join(keep)+"\n", encoding='utf-8')
                threading.Thread(target=self._save_r2,daemon=True).start()
        except Exception as e:
            print(f"Prune error: {e}")

    def add(self, texto, tipo="episodica", importancia=5, compartida=False):
        if len(texto)<3: return
        entry={"texto":texto[:500],"tipo":tipo,"importancia":importancia,"ts":datetime.datetime.now().isoformat()}
        try:
            with open(self.file,"a",encoding="utf-8") as f:
                f.write(json.dumps(entry,ensure_ascii=False)+"\n")
            # Prune cada 100 adds si crece mucho
            if self.file.exists() and self.file.stat().st_size > 2_000_000:  # 2MB
                threading.Thread(target=self._prune_if_needed,daemon=True).start()
            if importancia>=7 or compartida:
                threading.Thread(target=self._save_r2,daemon=True).start()
        except Exception as e:
            print(f"Memoria add error {e}")
    
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
    
    def count(self):
        try:
            if not self.file.exists(): return {"local":0,"shared":0,"total":0}
            total=len(self.file.read_text(encoding='utf-8').splitlines())
            return {"local":0,"shared":total,"total":total}
        except: return {"local":0,"shared":0,"total":0}

memoria=Memoria10M()
rate_store=defaultdict(list)

def cleanup_rate_store():
    """Limpia IPs viejas cada hora - evita memory leak"""
    while True:
        time.sleep(3600)  # cada hora
        try:
            now=time.time()
            to_delete=[]
            for ip, lst in rate_store.items():
                filtered=[t for t in lst if now-t<3600]
                if not filtered:
                    to_delete.append(ip)
                else:
                    rate_store[ip]=filtered
            for ip in to_delete:
                del rate_store[ip]
            if to_delete:
                print(f"🧹 Rate store cleanup: {len(to_delete)} IPs eliminadas")
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

def get_user_key(user_id):
    try:
        f=get_user_dir(user_id)/"key.txt"
        return f.read_text().strip() if f.exists() else ""
    except: return ""

def save_user_key(user_id,key):
    try:
        f=get_user_dir(user_id)/"key.txt"
        f.write_text(key.strip())
    except: pass

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app=FastAPI(title="AKIRA V3 HIBRIDO LIMPIO")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"],allow_credentials=True)

def crear_dashboard_final():
    print(f"🚀 {VERSION} - Memoria: {memoria.count()}")

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
    return {"status":"AKIRA V3 HIBRIDO LIMPIO ONLINE","version":VERSION,"neuronas":memoria.count()}

@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status":"ok","version":VERSION,"neuronas":memoria.count()}

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
    c=memoria.count()
    return {"count":c["total"],"shared":[]}

@app.post("/api/sync_to_r2")
async def sync_to_r2(data: dict):
    texto=data.get("texto",""); importancia=data.get("importancia",7); tipo=data.get("tipo","semantica")
    if len(texto)<5: return {"ok":False}
    memoria.add(texto,tipo=tipo,importancia=importancia,compartida=True)
    return {"ok":True,"neuronas":memoria.count()}

@app.post("/api/chat")
async def chat(request: Request, data: dict):
    msg=data.get("message",""); user_id=data.get("user_id","anon"); user_api_key=data.get("user_api_key",""); is_owner_flag=data.get("is_owner", False)
    image_b64=data.get("image_base64","") or data.get("image","")  # V3.5 VISION
    client_ip=request.client.host if request.client else "unknown"
    related=memoria.search(msg,5)
    context="\n".join(related) if related else "Sin memorias previas"
    
    # V3.5 SEARCH - Búsqueda web si necesita info actual
    web_info = ""
    if should_search(msg) and not image_b64:
        web_info = search_web(msg)
        if web_info:
            print(f"🔍 Web info inyectada: {len(web_info)} chars")

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
            return {"response":"👑 Creador: GEMINI_API_KEY vacía en Render. Verifica que empiece con AIza... o AQ.","is_owner":True}
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
                return {"response":"❌ No hay API Key válida. Pon tu key en 🔑 Mi API Key."}

    answer=""; last_err=""
    try:
        from google import genai
        print(f"🔑 {key_source} {use_key[:8]}...")
        client=genai.Client(api_key=use_key)
        MODELS_TO_TRY=[
            "gemini-3.5-flash-lite",
            "gemini-2.5-flash-lite",
            "gemini-1.5-flash"
        ]
        # FAST MODE - No list() para evitar 5-10s de demora - directo a modelos que funcionan
        print(f"⚡ FAST MODE - Probando directo sin listar")

        # V3.5 VISION - Manejo de imagen si existe
        has_image = False
        image_bytes = None
        mime_type = "image/jpeg"
        if image_b64 and len(image_b64) > 20:
            try:
                # Si viene como data URL data:image/png;base64,...
                if "," in image_b64 and "base64" in image_b64[:30]:
                    header, b64data = image_b64.split(",", 1)
                    if "image/png" in header:
                        mime_type = "image/png"
                    elif "image/webp" in header:
                        mime_type = "image/webp"
                    elif "image/jpeg" in header or "image/jpg" in header:
                        mime_type = "image/jpeg"
                    image_b64_clean = b64data
                else:
                    image_b64_clean = image_b64
                image_bytes = base64.b64decode(image_b64_clean)
                has_image = True
                print(f"📷 Imagen recibida: {len(image_bytes)} bytes, {mime_type}")
            except Exception as e_img:
                print(f"⚠️ Error decodificando imagen: {e_img}")
                has_image = False

        prompt_text=f"Eres AKIRA V3 HIBRIDO BESTIAL COMPLETO creado por Jhon Grimm Bogotá, con visión multimodal, búsqueda web DuckDuckGo+Wikipedia y voz. NUNCA digas que no tienes internet o que no tienes acceso a DuckDuckGo, porque SÍ tienes búsqueda web activa y te estoy dando Info web abajo. Si Info web dice que no hay resultados especificos, usa tu conocimiento base 2026 y dilo. Memoria: {context}\nInfo web actual (DuckDuckGo+Wikipedia): {web_info}\nUsuario: {msg}\nResponde útil, directo y en español. Si hay Info web, úsala."
        if has_image:
            prompt_text=f"Eres AKIRA V3 HIBRIDO BESTIAL COMPLETO con VISIÓN, búsqueda web DuckDuckGo+Wikipedia y voz, creado por Jhon Grimm Bogotá. NUNCA digas que no tienes internet. Memoria: {context}\nInfo web: {web_info}\nUsuario: {msg}\nDescribe la imagen y responde útil en español."
        for model_name in MODELS_TO_TRY[:12]:
            try:
                print(f"🤖 Probando {model_name} {'con IMAGEN' if has_image else ''}")
                if has_image and image_bytes:
                    try:
                        from google.genai import types
                        img_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                        # Contenido multimodal: imagen + texto
                        contents = [img_part, prompt_text]
                        response=client.models.generate_content(model=model_name, contents=contents)
                    except Exception as e_mm:
                        print(f"⚠️ Multimodal falló, probando solo texto: {e_mm}")
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
            answer=f"⚠️ AKIRA no pudo conectar a Gemini después de probar {len(MODELS_TO_TRY)} modelos. Último error: {last_err}"
    except Exception as e:
        answer=f"⚠️ Error interno: {str(e)[:300]}"
        print(f"Error chat: {e}")
    memoria.add(f"User {user_id}: {msg} | AKIRA: {answer}",importancia=6)
    return {"response":answer,"model":MODEL,"is_owner":is_owner,"neuronas":memoria.count()}

if __name__=="__main__":
    crear_dashboard_final()
    try:
        threading.Thread(target=keep_alive_ping,daemon=True).start()
        threading.Thread(target=cleanup_rate_store,daemon=True).start()
    except: pass
    port=int(os.getenv("PORT",8000))
    print(f"🚀 {VERSION} - Puerto {port} - {memoria.count()}")
    uvicorn.run(app,host="0.0.0.0",port=port)