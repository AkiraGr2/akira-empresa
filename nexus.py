#!/usr/bin/env python3
# AKIRA V3 BRIDGE HIBRIDO BESTIAL - AUDITORIA FINAL - FIX DEFINITIVO v1beta MUERTO
# SOLO usa google-genai (API v1) - ELIMINADO google-generativeai vieja
import os, json, datetime, threading, time, hashlib
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv
load_dotenv()

VERSION="AKIRA V3 HIBRIDO FIX DEFINITIVO"
MODEL="AKIRA V3"
OWNER_EMAILS=["bjhon9161@gmail.com"]
OWNER_SECRET=os.getenv("OWNER_SECRET","AKIRA_JHON_MASTER_2024")
BASE=Path("resultados")

# === R2 10M MEMORIA REAL - Cloudflare ===
def get_r2_client():
    try:
        import boto3
        ak = (os.getenv("R2_ACCESS_KEY_ID") or os.getenv("R2_ACCESS_KEY") or "").strip()
        sk = (os.getenv("R2_SECRET_ACCESS_KEY") or os.getenv("R2_SECRET_KEY") or "").strip()
        ep = (os.getenv("R2_ENDPOINT") or os.getenv("R2_ENDPOINT_URL") or "").strip()
        if not ak or not sk or not ep:
            print(f"R2 client missing: ak={bool(ak)} sk={bool(sk)} ep={bool(ep)}")
            return None
        client = boto3.client('s3', endpoint_url=ep, aws_access_key_id=ak, aws_secret_access_key=sk, region_name="auto")
        return client
    except Exception as e:
        print(f"R2 client error: {e}")
        return None

def download_shared_from_r2(local_path):
    try:
        client = get_r2_client()
        bucket = (os.getenv("R2_BUCKET_NAME") or os.getenv("R2_BUCKET") or "akira-v3-memoria").strip()
        if not client:
            return False
        print(f"☁️ Descargando memoria 10M de R2 bucket {bucket}...")
        resp = client.get_object(Bucket=bucket, Key="memoria_compartida.jsonl")
        data = resp['Body'].read()
        if data:
            local_path.write_bytes(data)
            print(f"✅ Memoria 10M restaurada de R2: {len(data)} bytes")
            return True
    except Exception as e:
        print(f"R2 download no existe aun o error: {e}")
    return False

def upload_shared_to_r2(local_path):
    try:
        client = get_r2_client()
        bucket = (os.getenv("R2_BUCKET_NAME") or os.getenv("R2_BUCKET") or "akira-v3-memoria").strip()
        if not client or not local_path.exists():
            return False
        client.upload_file(str(local_path), bucket, "memoria_compartida.jsonl")
        print(f"☁️ Memoria 10M subida a R2: {local_path.stat().st_size} bytes")
        return True
    except Exception as e:
        print(f"R2 upload error: {e}")
        return False

for d in ["memoria","users","usage","shared"]:
    (BASE / d).mkdir(parents=True, exist_ok=True)

rate_limit=defaultdict(list)

def get_user_dir(user_id):
    safe=hashlib.sha256(user_id.encode()).hexdigest()[:16]
    p=BASE / "users" / safe
    p.mkdir(parents=True, exist_ok=True)
    return p

def save_user_key(user_id, api_key, email=""):
    udir=get_user_dir(user_id)
    data={"api_key":api_key,"email":email,"updated":datetime.datetime.now().isoformat()}
    (udir / "config.json").write_text(json.dumps(data), encoding="utf-8")

def get_user_key(user_id):
    try:
        udir=get_user_dir(user_id)
        cfg=json.loads((udir / "config.json").read_text(encoding="utf-8"))
        return cfg.get("api_key")
    except: 
        return None

def check_rate_limit(ip, is_owner=False):
    if is_owner: return True
    now=time.time()
    rate_limit[ip]=[t for t in rate_limit[ip] if now - t < 3600]
    if len(rate_limit[ip])>=15: return False
    rate_limit[ip].append(now)
    return True

class MemoriaHIBRIDA:
    def __init__(self):
        self.local_path=BASE / "memoria" / "akira_memoria_final.jsonl"
        self.shared_path=BASE / "shared" / "memoria_compartida.jsonl"
        for p in [self.local_path, self.shared_path]:
            if not p.exists(): p.write_text("", encoding="utf-8")
        try:
            if self.shared_path.stat().st_size == 0:
                download_shared_from_r2(self.shared_path)
        except Exception as e:
            print(f"Init R2 error: {e}")
    def add(self, texto, tipo="episodica", importancia=5, tags=None, compartida=False):
        entry={"texto":texto,"tipo":tipo,"importancia":importancia,"ts":datetime.datetime.now().isoformat(),"tags":tags or [],"compartida":compartida}
        with self.local_path.open("a", encoding="utf-8") as f: f.write(json.dumps(entry, ensure_ascii=False)+"\n")
        if compartida and importancia>=7:
            with self.shared_path.open("a", encoding="utf-8") as f: f.write(json.dumps(entry, ensure_ascii=False)+"\n")
            try:
                threading.Thread(target=lambda: upload_shared_to_r2(self.shared_path), daemon=True).start()
            except:
                pass
    def count(self):
        try:
            local=len(self.local_path.read_text(encoding="utf-8").splitlines())
            shared=len(self.shared_path.read_text(encoding="utf-8").splitlines())
            return {"local":local,"shared":shared,"total":local+shared}
        except: return {"local":0,"shared":0,"total":0}
    def load_recent(self, n=50, solo_compartida=False):
        try:
            path=self.shared_path if solo_compartida else self.local_path
            lines=path.read_text(encoding="utf-8").splitlines()[-n:]
            return [json.loads(l) for l in lines if l.strip()]
        except: return []
    def search(self, query, n=5):
        all_mems=self.load_recent(200)+self.load_recent(200, solo_compartida=True)
        return [m['texto'] for m in all_mems if query.lower() in m['texto'].lower()][:n]

memoria=MemoriaHIBRIDA()

def keep_alive_ping():
    try: import requests
    except: return
    while True:
        time.sleep(600)
        try:
            url=os.getenv('RENDER_EXTERNAL_URL') or os.getenv('KEEPALIVE_URL') or ''
            if url: requests.get(url+'/health', timeout=10)
        except: pass

try:
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
    import uvicorn
    FASTAPI_AVAILABLE=True
except: FASTAPI_AVAILABLE=False

if FASTAPI_AVAILABLE:
    app=FastAPI(title=f"AKIRA {MODEL} HIBRIDO FIX")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @app.get("/")
    async def root(): return {"status":"AKIRA V3 HIBRIDO ONLINE","version":VERSION,"neuronas":memoria.count()}
    @app.get("/health")
    async def health(): return {"status":"ok","version":VERSION,"neuronas":memoria.count(),"time":datetime.datetime.now().isoformat()}
    @app.get("/api/memorias")
    async def get_mems(): return {"count":memoria.count(),"recent_local":memoria.load_recent(20),"recent_shared":memoria.load_recent(20, solo_compartida=True),"version":VERSION}
    @app.get("/api/brain/shared")
    async def get_shared_brain(): return {"shared":memoria.load_recent(100, solo_compartida=True),"count":memoria.count()["shared"]}

    @app.post("/api/auth/google")
    async def auth_google(data: dict):
        credential=data.get("credential","")
        if not credential: return {"error":"No credential"}
        try:
            from google.oauth2 import id_token
            from google.auth.transport import requests as grequests
            GOOGLE_CLIENT_ID=os.getenv("GOOGLE_CLIENT_ID","").strip() or "148150327312-7k5g3go06tat9gv61c8v0rbbedcusoqn.apps.googleusercontent.com"
            idinfo=None
            try: idinfo=id_token.verify_oauth2_token(credential, grequests.Request(), GOOGLE_CLIENT_ID)
            except:
                import base64
                parts=credential.split('.')
                if len(parts)>=2: idinfo=json.loads(base64.urlsafe_b64decode(parts[1]+'==').decode())
            if not idinfo: return {"error":"Token inválido"}
            email=idinfo.get("email",""); sub=idinfo.get("sub","")
            user_id=sub or hashlib.sha256(email.encode()).hexdigest()[:16]
            is_owner=email.lower() in [e.lower() for e in OWNER_EMAILS]
            has_key=True if is_owner else (get_user_key(user_id) is not None)
            udir=get_user_dir(user_id)
            (udir / "profile.json").write_text(json.dumps({"email":email,"user_id":user_id,"is_owner":is_owner,"ts":datetime.datetime.now().isoformat()}), encoding="utf-8")
            return {"user_id":user_id,"email":email,"has_key":has_key,"is_owner":is_owner}
        except Exception as e: return {"error":f"Auth error: {str(e)[:200]}"}

    @app.post("/api/auth/owner")
    async def auth_owner(data: dict):
        secret=data.get("secret","").strip()
        if secret!=OWNER_SECRET: return {"ok":False,"error":"Secreto incorrecto"}
        owner_email=OWNER_EMAILS[0]
        user_id=hashlib.sha256(owner_email.encode()).hexdigest()[:16]
        udir=get_user_dir(user_id)
        (udir / "profile.json").write_text(json.dumps({"email":owner_email,"user_id":user_id,"is_owner":True,"ts":datetime.datetime.now().isoformat()}), encoding="utf-8")
        return {"ok":True,"user_id":user_id,"email":owner_email,"has_key":True,"is_owner":True}

    @app.post("/api/user/key")
    async def save_key(data: dict):
        user_id=data.get("user_id","").strip(); api_key=data.get("api_key","").strip()
        if not user_id or not api_key or len(api_key)<30: return {"error":"Key muy corta"}
        if not (api_key.startswith("AIza") or api_key.startswith("AQ.")): return {"error":"Key inválida - debe empezar por AIza o AQ."}
        save_user_key(user_id, api_key)
        return {"ok":True}

    @app.post("/api/sync_to_r2")
    async def sync_to_r2(data: dict):
        texto=data.get("texto",""); importancia=data.get("importancia",7); tipo=data.get("tipo","semantica")
        if len(texto)<5: return {"ok":False}
        memoria.add(texto, tipo=tipo, importancia=importancia, compartida=True)
        return {"ok":True,"neuronas":memoria.count()}

    @app.post("/api/chat")
    async def chat(request: Request, data: dict):
        msg=data.get("message",""); user_id=data.get("user_id","anon"); user_api_key=data.get("user_api_key",""); is_owner_flag=data.get("is_owner", False)
        client_ip=request.client.host if request.client else "unknown"
        related=memoria.search(msg, 5)
        context="\n".join(related) if related else "Sin memorias previas"
        is_owner=is_owner_flag
        try:
            udir=get_user_dir(user_id); pp=udir / "profile.json"
            if pp.exists():
                prof=json.loads(pp.read_text(encoding="utf-8"))
                if prof.get("is_owner") or prof.get("email","").lower() in [e.lower() for e in OWNER_EMAILS]: is_owner=True
        except: pass

        use_key=None
        key_source="none"
        if is_owner:
            owner_key=os.getenv("GEMINI_API_KEY","").strip()
            if owner_key and (owner_key.startswith("AIza") or owner_key.startswith("AQ.")) and len(owner_key)>20: 
                use_key=owner_key
                key_source="owner_env"
            else: 
                return {"response":"👑 Creador: GEMINI_API_KEY vacía o inválida en Render. Ve a Environment y verifica que empiece con AIza...","is_owner":True,"neuronas":memoria.count()}
        elif user_api_key and (user_api_key.startswith("AIza") or user_api_key.startswith("AQ.")) and len(user_api_key.strip())>20: 
            use_key=user_api_key.strip()
            key_source="user_frontend"
        else:
            stored=get_user_key(user_id)
            if stored and (stored.startswith("AIza") or stored.startswith("AQ.")) and len(stored)>20: 
                use_key=stored
                key_source="user_stored"
            else:
                owner_key=os.getenv("GEMINI_API_KEY","").strip()
                if owner_key and (owner_key.startswith("AIza") or owner_key.startswith("AQ.")) and len(owner_key)>20:
                    if not check_rate_limit(client_ip, is_owner=False): 
                        return {"response":"⚠️ Límite 15 mensajes por hora para usuarios normales. Haz login con Google y pon tu propia key en Mi API Key para ilimitado."}
                    use_key=owner_key
                    key_source="owner_env_fallback"
                else: 
                    return {"response":"❌ No hay API Key válida. Ve a Mi API Key y pega una que empiece con AIza... (de AI Studio).","model":MODEL}

        # === FIX DEFINITIVO: SOLO google-genai NUEVA, NO google-generativeai VIEJA ===
        answer=""
        last_err=""
        try:
            from google import genai
            from google.genai import types
            print(f"🔑 Usando key source: {key_source} - {use_key[:8]}... len={len(use_key)}")
            client=genai.Client(api_key=use_key)
            
            # Modelos válidos en API v1 actual (2025-2026) - probados
            MODELS_TO_TRY = [
                "gemini-2.0-flash",
                "gemini-2.0-flash-001",
                "gemini-1.5-flash",
                "gemini-1.5-flash-002",
                "gemini-1.5-pro",
                "gemini-2.0-flash-lite"
            ]
            
            prompt_text=f"Eres AKIRA V3 HIBRIDO, creado por Jhon Grimm en Bogota. Eres bestial, útil y directo. Memoria relevante: {context}\n\nUsuario ({user_id}): {msg}\n\nResponde en español, útil y con tu personalidad de Bogota. Si te preguntan quien te creo, di Jhon Grimm."
            
            for model_name in MODELS_TO_TRY:
                try:
                    print(f"🤖 Intentando modelo: {model_name}")
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt_text
                    )
                    # Extraer texto de forma robusta
                    if hasattr(response, 'text') and response.text:
                        answer = response.text
                    elif hasattr(response, 'candidates') and response.candidates:
                        cand = response.candidates[0]
                        if hasattr(cand, 'content') and cand.content.parts:
                            answer = cand.content.parts[0].text
                        else:
                            answer = str(cand)
                    else:
                        answer = str(response)
                    
                    if answer and len(answer.strip())>5:
                        print(f"✅ ÉXITO con modelo {model_name}: {len(answer)} chars")
                        break
                    else:
                        last_err = f"{model_name} devolvió vacío"
                        print(f"⚠️ {model_name} vacío")
                        continue
                        
                except Exception as e_model:
                    last_err = f"{model_name}: {str(e_model)[:500]}"
                    print(f"❌ Fallo {model_name}: {last_err}")
                    continue
            
            if not answer:
                answer=f"⚠️ AKIRA no pudo conectar a Gemini después de probar {len(MODELS_TO_TRY)} modelos. Último error: {last_err[:400]}\n\nVerifica:\n1. Tu GEMINI_API_KEY en Render es válida y empieza con AIza...\n2. La key está habilitada en AI Studio\n3. No excediste cuota"
                
        except ImportError as e_imp:
            answer=f"❌ Error crítico: librería google-genai no instalada en Render. Import error: {str(e_imp)[:300]}. Verifica requirements.txt tenga 'google-genai'"
            print(answer)
        except Exception as e:
            answer=f"[Error crítico chat: {str(e)[:500]}] - Key source: {key_source}"
            print(answer)

        es_importante=len(msg)>15 and any(k in msg.lower() for k in ["que es","como","define","explica","membrana","obsidian","akira","soy","creador","bogota","jhon","grimm"])
        memoria.add(f"User {user_id}: {msg} | AKIRA: {answer}", importancia=8 if es_importante else 5, compartida=es_importante)
        return {"response":answer,"model":MODEL,"is_owner":is_owner,"neuronas":memoria.count(),"es_compartida":es_importante,"key_source":key_source}

    if __name__=="__main__":
        try: threading.Thread(target=keep_alive_ping, daemon=True).start()
        except: pass
        port=int(os.getenv("PORT",8000))
        print(f"🚀 AKIRA {MODEL} HIBRIDO FIX DEFINITIVO - Puerto {port} - Neuronas: {memoria.count()}")
        uvicorn.run(app, host="0.0.0.0", port=port)
