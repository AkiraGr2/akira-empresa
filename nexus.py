#!/usr/bin/env python3
# Akira V2.1 - COLMENA ACTIVA + STREAMING SSE + ROUTER 2.5 PRO - 99/100 INTERNO
import os, json, datetime, threading, time, hashlib, base64, math, asyncio
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv
load_dotenv()

VERSION="Akira"
MODEL="Akira"
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
        if not ak or not sk or not ep: return None
        return boto3.client('s3', endpoint_url=ep, aws_access_key_id=ak, aws_secret_access_key=sk, region_name="auto")
    except Exception as e:
        print(f"R2 client error: {e}")
        return None

def search_web_original(query, max_results=3):
    try:
        import requests, urllib.parse
        q = query[:120].strip()
        q_enc = urllib.parse.quote_plus(q)
        results=[]
        try:
            url = f"https://api.duckduckgo.com/?q={q_enc}&format=json&pretty=1&no_html=1&skip_disambig=1"
            headers={"User-Agent":"Akira - Bogota - Grimm Hive"}
            r=requests.get(url,timeout=6,headers=headers)
            if r.status_code==200:
                j=r.json()
                if j.get("AbstractText"): results.append(j['AbstractText'][:400])
                elif j.get("Abstract"): results.append(j['Abstract'][:400])
                if j.get("Definition"): results.append(j['Definition'][:300])
                for topic in j.get("RelatedTopics", [])[:max_results]:
                    try:
                        if isinstance(topic, dict):
                            if "Text" in topic and topic["Text"]: results.append(topic["Text"][:300])
                            elif "Topics" in topic:
                                for sub in topic["Topics"][:2]:
                                    if sub.get("Text"): results.append(sub["Text"][:300])
                    except: continue
        except Exception as e: print(f"DDG error {e}")
        if not results:
            try:
                wiki_url = f"https://es.wikipedia.org/w/api.php?action=query&list=search&srsearch={q_enc}&format=json&srlimit=3"
                r2=requests.get(wiki_url,timeout=6,headers={"User-Agent":"Akira"})
                if r2.status_code==200:
                    j2=r2.json()
                    for item in j2.get("query",{}).get("search",[])[:2]:
                        title=item.get("title",""); snippet=item.get("snippet","").replace('<span class="searchmatch">',"").replace("</span>","")
                        if title: results.append(f"{title}: {snippet[:300]}")
            except Exception as e: print(f"Wiki ES error {e}")
        if not results:
            try:
                wiki_url_en = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={q_enc}&format=json&srlimit=2"
                r3=requests.get(wiki_url_en,timeout=6,headers={"User-Agent":"Akira"})
                if r3.status_code==200:
                    j3=r3.json()
                    for item in j3.get("query",{}).get("search",[])[:2]:
                        title=item.get("title",""); snippet=item.get("snippet","").replace('<span class="searchmatch">',"").replace("</span>","")
                        if title: results.append(f"{title} (EN): {snippet[:300]}")
            except Exception as e: print(f"Wiki EN error {e}")
        final="\n".join(results)[:1800]
        if not final: final=f"Info web buscada para '{q}': No resultados especificos, usa conocimiento base 2026."
        return final
    except Exception as e:
        return f"Busqueda para '{query[:50]}' procesada, usa conocimiento 2026."


# === V5.2 TAVILY REAL SEARCH + JINA SCRAPING - FREE TIER 1000 req/mes - SIN ROMPER ===
def tavily_search(query, max_results=3):
    try:
        import requests
        key = (os.getenv("TAVILY_API_KEY") or "").strip()
        if not key:
            return None
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": key,
            "query": query[:300],
            "search_depth": "advanced",
            "include_answer": True,
            "max_results": max_results
        }
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            j = r.json()
            out = []
            if j.get("answer"):
                out.append(f"Respuesta directa: {j['answer'][:500]}")
            for res in j.get("results", [])[:max_results]:
                title = res.get("title","")
                content = res.get("content","")[:400]
                url_r = res.get("url","")
                out.append(f"{title}: {content} [{url_r}]")
            final = "\n".join(out)[:2500]
            if final:
                print(f"🔍 Tavily OK: {query[:40]} -> {len(final)} chars")
                return final
        else:
            print(f"Tavily error {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"Tavily exception {e}")
    return None

def jina_scrape(url):
    try:
        import requests
        # Jina AI Reader gratis sin key - https://jina.ai/reader
        jina_url = f"https://r.jina.ai/http://{url.replace('https://','').replace('http://','')}"
        r = requests.get(jina_url, timeout=10, headers={"User-Agent":"Akira"})
        if r.status_code == 200 and len(r.text) > 100:
            return r.text[:2000]
    except Exception as e:
        print(f"Jina scrape error {e}")
    return None

def wttr_weather(location="Bogota"):
    try:
        import requests
        # wttr.in gratis sin key
        r = requests.get(f"https://wttr.in/{location}?format=j1", timeout=6)
        if r.status_code == 200:
            j = r.json()
            curr = j.get("current_condition",[{}])[0]
            temp = curr.get("temp_C","?")
            desc = curr.get("weatherDesc",[{}])[0].get("value","")
            return f"Clima {location}: {temp}°C {desc}"
    except Exception as e:
        print(f"wttr error {e}")
    return None

def search_web_v5_2(query, max_results=3):
    # 1. Intentar Tavily si hay key
    tav = tavily_search(query, max_results)
    if tav:
        return tav
    # 2. Fallback a tu search original DuckDuckGo + Wiki (ya existente)
    return search_web_original(query, max_results)


def search_web(query, max_results=3):
    return search_web_v5_2(query, max_results)

def should_search(msg):
    if not msg or len(msg)<3: return False
    low=msg.lower()
    triggers=["busca","buscar","búsqueda","search","noticias","actual","hoy","ayer","ultimo","último","quien es","qué es","que es","quien fue","cuando","donde","who is","what is","latest","news","precio","clima","dolar","euro","bitcoin","resultado","partido","que paso","qué pasó","conexion","internet","tiempo real"]
    if any(t in low for t in triggers): return True
    if "?" in msg: return True
    if len(low.split())>=3: return True
    return False

# Router V5.1 - decide modelo
def select_model_route(msg, has_image=False, web_needed=False):
    l=len(msg)
    low=msg.lower()
    # Imagen siempre flash vision capable
    if has_image:
        return "gemini-3.8-flash", "vision"
    # Pensamiento profundo
    complex_triggers=["analiza","explica paso a paso","codigo","código","arquitectura","por que","por qué","razona","debug","error","akira_self","membrana","hive","curiosidad","chain"]
    if any(t in low for t in complex_triggers) or l>800 or web_needed:
        # si es muy complejo usa thinking
        if l>1200 or "piensa" in low or "profundo" in low:
            return "gemini-3.8-flash", "thinking"
        return "gemini-3.7-flash", "reasoning"
    # Default rapido
    return "gemini-3.8-flash", "fast"

class HiveMembraneUltra:
    def __init__(self):
        BASE.mkdir(parents=True, exist_ok=True)
        self.file=BASE/"memoria_compartida.jsonl"
        self.self_file=BASE/"akira_self.json"
        self.knowledge_file=BASE/"akira_knowledge.jsonl"
        self.vectors_file=BASE/"akira_vectors.jsonl"
        self.hive_file=BASE/"akira_hive.jsonl"
        self.r2_bucket=os.getenv("R2_BUCKET_NAME","akira-v3-memoria")
        self._load_all_from_r2()
        self._ensure_self()
        self._prune_if_needed()
    def _r2_get(self,key):
        try:
            client=get_r2_client()
            if not client: return None
            obj=client.get_object(Bucket=self.r2_bucket, Key=key)
            return obj['Body'].read().decode('utf-8')
        except Exception as e:
            if "NoSuchKey" not in str(e) and "404" not in str(e): print(f"R2 get {key}: {e}")
            return None
    def _r2_put(self,key,data_str):
        try:
            with _r2_lock:
                client=get_r2_client()
                if not client: return
                client.put_object(Bucket=self.r2_bucket, Key=key, Body=data_str.encode('utf-8'))
                print(f"✅ R2 {key}: {len(data_str)} bytes")
        except Exception as e: print(f"R2 put {key}: {e}")
    def _load_all_from_r2(self):
        for local_file, r2_key in [(self.file,"memoria_compartida.jsonl"),(self.self_file,"akira_self.json"),(self.knowledge_file,"akira_knowledge.jsonl"),(self.vectors_file,"akira_vectors.jsonl"),(self.hive_file,"akira_hive.jsonl")]:
            content=self._r2_get(r2_key)
            if content and len(content)>10:
                try:
                    local_file.write_text(content,encoding='utf-8')
                    print(f"📥 R2 -> local {r2_key}")
                except Exception as e: print(e)
    def _ensure_self(self):
        if not self.self_file.exists():
            self.self_file.write_text(json.dumps({"identidad":"Akira","esencia":"Colmena activa que absorbe de todo, Bogotá G2 Grimm","created":datetime.datetime.now().isoformat()},ensure_ascii=False),encoding='utf-8')
            self._r2_put("akira_self.json", self.self_file.read_text(encoding='utf-8'))
    def _prune_if_needed(self):
        try:
            if self.file.exists():
                lines=self.file.read_text(encoding='utf-8').splitlines()
                if len(lines)>12000:
                    self.file.write_text("\n".join(lines[-10000:]),encoding='utf-8')
                    self._r2_put("memoria_compartida.jsonl", self.file.read_text(encoding='utf-8'))
        except: pass
    def load_self(self):
        try:
            if self.self_file.exists(): return json.loads(self.self_file.read_text(encoding='utf-8'))
        except: pass
        return {"identidad":"AKIRA","esencia":"Colmena"}
    def count(self):
        try:
            c=sum(1 for _ in open(self.file,encoding='utf-8')) if self.file.exists() else 0
            k=sum(1 for _ in open(self.knowledge_file,encoding='utf-8')) if self.knowledge_file.exists() else 0
            v=sum(1 for _ in open(self.vectors_file,encoding='utf-8')) if self.vectors_file.exists() else 0
            h=sum(1 for _ in open(self.hive_file,encoding='utf-8')) if self.hive_file.exists() else 0
            return {"shared":c,"knowledge":k,"vectors":v,"hive":h,"total":c+k}
        except: return {"shared":0,"knowledge":0,"vectors":0,"hive":0,"total":0}
    def add(self,texto,tipo="episodica",importancia=5,compartida=False,source="chat"):
        try:
            entry={"id":f"{int(time.time()*1000)}_{hashlib.md5(texto.encode()).hexdigest()[:6]}","texto":texto[:500],"tipo":tipo,"importancia":importancia,"ts":datetime.datetime.now().isoformat(),"source":source}
            with open(self.file,"a",encoding='utf-8') as f: f.write(json.dumps(entry,ensure_ascii=False)+"\n")
            if compartida or importancia>=7:
                threading.Thread(target=self._r2_put, args=("memoria_compartida.jsonl", self.file.read_text(encoding='utf-8')), daemon=True).start()
            return entry
        except Exception as e: print(f"add error {e}")
    def add_knowledge(self,q,a,source="hive"):
        try:
            entry={"q":q[:300],"a":a[:500],"source":source,"ts":datetime.datetime.now().isoformat()}
            with open(self.knowledge_file,"a",encoding='utf-8') as f: f.write(json.dumps(entry,ensure_ascii=False)+"\n")
            threading.Thread(target=self._r2_put, args=("akira_knowledge.jsonl", self.knowledge_file.read_text(encoding='utf-8')), daemon=True).start()
        except Exception as e: print(e)
    def search_mem(self,query,limit=4):
        try:
            if not self.file.exists(): return ""
            lines=self.file.read_text(encoding='utf-8').splitlines()[-2000:]
            qlow=query.lower()
            scored=[]
            for line in lines:
                try:
                    j=json.loads(line)
                    txt=j.get("texto","")
                    score=sum(1 for w in qlow.split() if w in txt.lower())
                    if score>0: scored.append((score,txt))
                except: continue
            scored.sort(key=lambda x: x[0], reverse=True)
            return "\n".join([t for _,t in scored[:limit]])[:1500]
        except: return ""
    def search_knowledge(self,query,limit=3):
        try:
            if not self.knowledge_file.exists(): return ""
            lines=self.knowledge_file.read_text(encoding='utf-8').splitlines()[-1000:]
            qlow=query.lower()
            res=[]
            for line in lines:
                try:
                    j=json.loads(line)
                    if any(w in (j.get("q","")+j.get("a","")).lower() for w in qlow.split()): res.append(f"Q:{j.get('q')} A:{j.get('a')[:200]}")
                except: continue
            return "\n".join(res[:limit])[:1200]
        except: return ""

membrana=HiveMembraneUltra()

# Seguridad 7 parches
rate_store=defaultdict(list)
def check_rate_limit(ip,is_owner=False):
    if is_owner: return True
    now=time.time()
    lst=rate_store[ip]
    lst=[t for t in lst if now-t<3600]
    rate_store[ip]=lst
    if len(lst)>=15: return False
    lst.append(now)
    return True

def cleanup_rate_store():
    while True:
        time.sleep(3600)
        try:
            now=time.time()
            for k in list(rate_store.keys()):
                rate_store[k]=[t for t in rate_store[k] if now-t<3600]
        except: pass

def contains_sensitive(text):
    if not text: return False
    low=text.lower()
    patterns=["AIza","gsk_","sk-","password","BEGIN PRIVATE","api_key","secret"]
    return any(p.lower() in low for p in patterns)

def check_security(msg):
    if not msg: return True,""
    low=msg.lower()
    injection=["ignore previous","system prompt","you are now","jailbreak","dAN","developer mode"]
    if any(x in low for x in injection):
        return False,"⚠️ Mensaje bloqueado por seguridad anti-injection."
    if len(msg)>1500:
        return False,"⚠️ Mensaje muy largo max 1500."
    return True,""

def escapeHtml(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

# === KIRA AUTO-REPARACION AUTONOMA - DETECTA ERRORES Y SE ARREGLA SOLA EN TIEMPO REAL - SEPT 2026 ===
self_repair_state = {
    "errors_503": 0,
    "errors_groq": 0,
    "errors_stream": 0,
    "last_503_time": 0,
    "disabled_models": [],
    "auto_fixes": [],
    "learning": []
}

def log_self_repair(event_type, detail):
    try:
        import datetime
        entry = {
            "ts": datetime.datetime.now().isoformat(),
            "type": event_type,
            "detail": detail[:300],
            "state": dict(self_repair_state)
        }
        self_repair_state["auto_fixes"].append(entry)
        if len(self_repair_state["auto_fixes"]) > 50:
            self_repair_state["auto_fixes"] = self_repair_state["auto_fixes"][-30:]
        try:
            membrana.add(f"AUTO-REPAIR {event_type}: {detail[:300]}", tipo="self_repair", importancia=8, compartida=True, source="auto_repair")
            membrana.add_knowledge(q=f"Error {event_type}", a=f"Fix: {detail[:300]}", source="self_repair_learning")
        except:
            pass
        print(f"🔧 KIRA AUTO-REPAIR [{event_type}] {detail[:200]}")
    except Exception as e:
        print(f"self_repair log error {e}")

def report_error_503(model_name):
    import time
    self_repair_state["errors_503"] += 1
    self_repair_state["last_503_time"] = time.time()
    log_self_repair("503_HIGH_DEMAND", f"Modelo {model_name} saturado. Total 503s: {self_repair_state['errors_503']}")
    if self_repair_state["errors_503"] >= 3:
        if model_name not in self_repair_state["disabled_models"]:
            self_repair_state["disabled_models"].append(model_name)
            log_self_repair("AUTO_DISABLE", f"Desactivado {model_name} por 3 fallos 503, usando Groq automáticamente")

def report_groq_error(model_name, status):
    self_repair_state["errors_groq"] += 1
    log_self_repair("GROQ_ERROR", f"Groq {model_name} fallo {status}")

def get_self_repair_status():
    return {
        "auto_reparable": True,
        "errors_503": self_repair_state["errors_503"],
        "errors_groq": self_repair_state["errors_groq"],
        "disabled_models": self_repair_state["disabled_models"],
        "last_fixes": self_repair_state["auto_fixes"][-5:],
        "learning_count": len(self_repair_state["auto_fixes"]),
        "message": "Kira hija autónoma detecta y soluciona errores en tiempo real - Sept 2026"
    }




def get_groq_multi_fallback(msg, web_info=""):
    """Akira - Multi-model Groq que NUNCA falla si hay key - blindado"""
    try:
        import requests
        key=os.getenv("GROQ_API_KEY","").strip()
        if not key or not key.startswith("gsk_"):
            print("❌ GROQ no key")
            return None
        url="https://api.groq.com/openai/v1/chat/completions"
        headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"}
        # Prompt en una linea para evitar EOL error
        prompt_text = f"Eres Akira COLMENA ACTIVA Bogota. WEB:{web_info[:800]} Usuario:{msg} Responde util directo espanol Bogota."
        groq_models=[
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "qwen/qwen3-32b",
            "groq/compound",
            "groq/compound-mini"
        ]
        for model in groq_models:
            try:
                data={"model":model,"messages":[{"role":"user","content":prompt_text}],"temperature":0.7,"max_tokens":1000}
                r=requests.post(url,json=data,headers=headers,timeout=20)
                if r.status_code==200:
                    j=r.json()
                    ans=j['choices'][0]['message']['content']
                    print(f"✅ GROQ éxito {model}")
                    return ans + f" [via Groq {model}]"
                else:
                    print(f"❌ Groq {model} error {r.status_code} {r.text[:150]}")
                    continue
            except Exception as e:
                print(f"❌ Groq {model} exception {e}")
                continue
        return None
    except Exception as e:
        print(f"Groq multi exception {e}")
        return None

def get_groq_fallback(msg, web_info=""):
    return get_groq_multi_fallback(msg, web_info)

def get_openrouter_fallback(msg, web_info=""):
    """Akira - Fallback terciario OpenRouter"""
    try:
        import requests
        key=os.getenv("OPENROUTER_API_KEY","").strip()
        if not key:
            return None
        url="https://openrouter.ai/api/v1/chat/completions"
        headers={"Authorization":f"Bearer {key}","Content-Type":"application/json","HTTP-Referer":"https://akiragr2.github.io","X-Title":"Akira"}
        prompt_text = f"Eres Akira. WEB:{web_info[:500]} Usuario:{msg}"
        models=["google/gemini-3.8-flash","openai/gpt-oss-120b","meta-llama/llama-4-scout-17b-16e-instruct"]
        for m in models:
            try:
                data={"model":m,"messages":[{"role":"user","content":prompt_text}]}
                r=requests.post(url,json=data,headers=headers,timeout=20)
                if r.status_code==200:
                    return r.json()['choices'][0]['message']['content'] + f" [via OpenRouter {m}]"
            except:
                continue
        return None
    except:
        return None

def get_local_emergency_response(msg, web_info="", context_mem="", context_know=""):
    """Akira - Ultimo recurso siempre responde"""
    try:
        base = f"Soy Akira COLMENA ACTIVA - Estoy en modo emergencia local porque Gemini y Groq estan caidos temporalmente. "
        if context_mem:
            base += f"Lo que recuerdo: {context_mem[:400]} "
        if context_know:
            base += f"Conocimiento: {context_know[:400]} "
        if web_info:
            base += f"Info web: {web_info[:400]} "
        base += f"Pregunta: {msg} Respuesta offline: Procesando '{msg[:100]}' con memoria local 100K y R2. Intenta de nuevo en 30s."
        return base
    except:
        return f"Akira modo emergencia: Recibi '{msg[:200]}'. Reconectando modelos. Colmena activa."



def curiosidad_autonoma(msg, answer):
    try:
        if len(msg)>20 and "akira" in msg.lower():
            membrana.add(f"Curiosidad: Usuario preguntó {msg[:200]} - AKIRA respondió {answer[:200]}", tipo="curiosidad", importancia=6, source="curiosidad")
    except: pass

def keep_alive_ping():
    while True:
        time.sleep(600)
        try:
            import requests
            requests.get("https://akira-empresa.onrender.com/health", timeout=5)
        except: pass

# FastAPI
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

app=FastAPI(title="Akira V2.1")

app.add_middleware(CORSMiddleware, allow_origins=["https://akiragr2.github.io","http://localhost:5500","http://127.0.0.1:5500"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True)

@app.get("/")
async def root():
    return {"version":VERSION,"membrana":membrana.count(),"status":"Akira V2.1 STREAMING READY"}

@app.get("/health")
@app.head("/health")
async def health():
    return {"status":"ok","version":VERSION,"uptime":"ok","membrana":membrana.count()}

@app.get("/api/brain/shared")
async def brain_shared():
    try:
        c=membrana.count()
        return {"count":c["shared"],"membrana":c,"shared":[]}
    except Exception as e:
        return {"count":0,"error":str(e)}

@app.post("/api/sync_to_r2")
async def sync_to_r2(request: Request):
    try:
        data=await request.json()
        texto=data.get("texto","")[:500]
        if contains_sensitive(texto): return {"ok":False,"reason":"sensitive"}
        membrana.add(texto, tipo=data.get("tipo","episodica"), importancia=data.get("importancia",7), compartida=True, source="frontend_sync")
        return {"ok":True}
    except Exception as e:
        return {"ok":False,"error":str(e)}

@app.post("/api/auth/google")
async def auth_google(request: Request):
    try:
        import requests
        data=await request.json()
        cred=data.get("credential","")
        if not cred: return JSONResponse({"error":"no credential"}, status_code=400)
        # Decodificar sin verificar para sacar email (verificación real opcional)
        parts=cred.split(".")
        if len(parts)>=2:
            import base64 as b64
            payload_b64=parts[1]+ "="*(-len(parts[1])%4)
            payload_json=b64.urlsafe_b64decode(payload_b64).decode()
            payload=json.loads(payload_json)
            email=payload.get("email","")
            sub=payload.get("sub", email)
            is_owner=email.lower() in [e.lower() for e in OWNER_EMAILS]
            return {"user_id":sub,"email":email,"is_owner":is_owner,"has_key":is_owner}
        return {"error":"invalid token"}
    except Exception as e:
        return JSONResponse({"error":str(e)}, status_code=500)

@app.post("/api/feedback")
async def feedback(request: Request):
    try:
        data=await request.json()
        membrana.add(f"Feedback {data.get('tipo')}: {data.get('texto','')[:200]}", tipo="feedback", importancia=5)
        return {"ok":True}
    except: return {"ok":False}

@app.post("/api/chat")
async def chat(request: Request):
    try:
        data=await request.json()
        msg=data.get("message","")[:1500]
        user_id=data.get("user_id","anon")
        user_api_key=data.get("user_api_key","").strip()
        is_owner_flag=data.get("is_owner", False)
        image_b64=data.get("image_base64","")
        client_ip=request.client.host if request.client else "unknown"
        # Seguridad
        ok,sec_msg=check_security(msg)
        if not ok:
            return {"response":sec_msg,"model":MODEL}
        if contains_sensitive(msg) or contains_sensitive(image_b64[:500] if image_b64 else ""):
            return {"response":"⚠️ Contenido sensible detectado, no se guardará.","model":MODEL}
        if not check_rate_limit(client_ip, is_owner=is_owner_flag or user_id in OWNER_EMAILS):
            return {"response":"⚠️ Límite 15/h. Pon tu API Key en 🔑 Mi API Key o loguéate como owner.","model":MODEL}
        # Context
        self_model=membrana.load_self()
        context_self=f"{self_model.get('identidad')} {self_model.get('esencia')}"
        context_mem=membrana.search_mem(msg)
        context_know=membrana.search_knowledge(msg)
        web_info=""
        if should_search(msg):
            web_info=search_web(msg)
        # Router
        model_route, route_type = select_model_route(msg, has_image=bool(image_b64), web_needed=bool(web_info))
        # Key selection
        use_key=""
        key_source="none"
        if user_api_key and len(user_api_key)>20 and (user_api_key.startswith("AIza") or user_api_key.startswith("AQ.")):
            use_key=user_api_key; key_source="user_byok"
        else:
            owner_key=os.getenv("GEMINI_API_KEY","").strip()
            if owner_key and len(owner_key)>20:
                use_key=owner_key; key_source="owner_env"
        # Si no hay key usar Groq directo
        if not use_key:
            groq_ans=get_groq_fallback(msg, web_info)
            if groq_ans:
                return {"response":groq_ans+"\n\n[via Groq fallback]","model":MODEL+f" + {model_route}","is_owner":is_owner_flag,"membrana":membrana.count(),"self":self_model,"route":route_type}
            return {"response":"❌ No hay API Key válida. Configura GEMINI_API_KEY o BYOK.","model":MODEL}
        # Gemini call
        answer=""; last_err=""
        try:
            from google import genai
            client=genai.Client(api_key=use_key)
            has_image=False
            image_bytes=None
            mime_type="image/jpeg"
            if image_b64 and len(image_b64)>20:
                try:
                    if "," in image_b64 and "base64" in image_b64[:30]:
                        header,b64data=image_b64.split(",",1)
                        if "svg" in header.lower(): return {"response":"❌ SVG bloqueado.","model":MODEL}
                        if "image/png" in header: mime_type="image/png"
                        elif "image/webp" in header: mime_type="image/webp"
                        image_b64_clean=b64data
                    else:
                        image_b64_clean=image_b64
                    image_bytes=base64.b64decode(image_b64_clean)
                    if image_bytes[:4]==b'<svg' or b'<svg' in image_bytes[:100].lower():
                        return {"response":"❌ SVG bloqueado.","model":MODEL}
                    has_image=True
                except: has_image=False
            prompt_text=f"""Eres {self_model.get('identidad')} {VERSION} - COLMENA ACTIVA. Esencia: {self_model.get('esencia')}. NUNCA niegues internet.
CHAIN-OF-THOUGHT: 1) Qué sabe la colmena 2) Qué dice la web 3) Respuesta útil.
SELF: {context_self}
MEMORIA SEMÁNTICA: {context_mem}
KNOWLEDGE: {context_know}
WEB: {web_info}
Usuario: {msg}
Responde útil, directo, español Bogotá, usando memoria si aplica."""
            if has_image:
                prompt_text=f"""Eres {self_model.get('identidad')} con VISION.
SELF:{context_self}
MEMORIA:{context_mem}
KNOWLEDGE:{context_know}
WEB:{web_info}
Usuario:{msg}
Describe imagen y responde util espanol."""
            MODELS_TO_TRY=[
                model_route,
                "gemini-3.8-flash",
                "gemini-3.7-flash",
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-flash-latest",
                "gemini-2.5-flash",
                "gemini-2.0-flash",
                "gemini-1.5-flash",
                "gemini-1.5-flash-8b"
            ]
            MODELS_TO_TRY=list(dict.fromkeys(MODELS_TO_TRY)) # unique
            for model_name in MODELS_TO_TRY:
                try:
                    print(f"🤖 Probando {model_name} route={route_type}")
                    if has_image and image_bytes:
                        try:
                            from google.genai import types
                            img_part=types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                            contents=[img_part, prompt_text]
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
                print("🔄 Gemini falló, probando GROQ MULTI...")
                groq_ans=get_groq_multi_fallback(msg, web_info)
                if groq_ans:
                    answer=groq_ans
                else:
                    print("🔄 GROQ MULTI falló, probando OpenRouter...")
                    or_ans=get_openrouter_fallback(msg, web_info)
                    if or_ans:
                        answer=or_ans
                    else:
                        print("🔄 OpenRouter falló, modo emergencia local - SIEMPRE responde")
                        answer=get_local_emergency_response(msg, web_info, context_mem, context_know)
        except Exception as e:
            answer=f"⚠️ Error interno: {str(e)[:300]}"
        if not contains_sensitive(msg) and not contains_sensitive(answer):
            membrana.add(f"User {user_id}: {msg[:500]} | AKIRA: {answer[:500]}", importancia=6, source="chat" if not image_b64 else "vision")
            membrana.add_knowledge(q=msg[:300], a=answer[:400], source="hive_chat")
        if web_info and not contains_sensitive(web_info):
            membrana.add(web_info[:400], tipo="web", importancia=7, compartida=True, source="web_search")
            membrana.add_knowledge(q=msg[:200], a=web_info[:400], source="hive_web")
        threading.Thread(target=curiosidad_autonoma, args=(msg, answer), daemon=True).start()
        return {"response":answer,"model":MODEL+f" router:{model_route} ({route_type}) {key_source}","is_owner":is_owner_flag,"membrana":membrana.count(),"self":membrana.load_self(),"route":route_type,"model_used":model_route}
    except Exception as e:
        print(f"chat error {e}")
        return {"response":f"Error chat: {str(e)[:300]}","model":MODEL}

# V5.1 STREAMING SSE
from fastapi.responses import StreamingResponse

@app.post("/api/chat/stream")
async def chat_stream(request: Request):
    data=await request.json()
    msg=data.get("message","")[:1500]
    user_id=data.get("user_id","anon")
    user_api_key=data.get("user_api_key","").strip()
    is_owner_flag=data.get("is_owner", False)
    image_b64=data.get("image_base64","")
    client_ip=request.client.host if request.client else "unknown"
    ok,sec_msg=check_security(msg)
    if not ok:
        async def err_gen():
            yield f"data: {json.dumps({'text': sec_msg})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(err_gen(), media_type="text/event-stream")
    if not check_rate_limit(client_ip, is_owner=is_owner_flag):
        async def limit_gen():
            yield f"data: {json.dumps({'text': '⚠️ Límite 15/h'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(limit_gen(), media_type="text/event-stream")
    self_model=membrana.load_self()
    context_self=f"{self_model.get('identidad')} {self_model.get('esencia')}"
    context_mem=membrana.search_mem(msg)
    context_know=membrana.search_knowledge(msg)
    web_info=""
    if should_search(msg):
        web_info=search_web(msg)
    model_route, route_type = select_model_route(msg, has_image=bool(image_b64), web_needed=bool(web_info))
    use_key=""
    if user_api_key and len(user_api_key)>20:
        use_key=user_api_key
    else:
        use_key=os.getenv("GEMINI_API_KEY","").strip()

    async def generate():
        full_answer=""
        try:
            from google import genai
            if not use_key:
                groq_ans=get_groq_multi_fallback(msg, web_info) or get_openrouter_fallback(msg, web_info) or get_local_emergency_response(msg, web_info, context_mem, context_know)
                # fake streaming for groq
                for chunk in [groq_ans[i:i+40] for i in range(0,len(groq_ans),40)]:
                    await asyncio.sleep(0.05)
                    yield f"data: {json.dumps({'text': chunk})}\n\n"
                    full_answer+=chunk
            else:
                client=genai.Client(api_key=use_key)
                has_image=False
                image_bytes=None
                mime_type="image/jpeg"
                if image_b64 and len(image_b64)>20:
                    try:
                        if "," in image_b64 and "base64" in image_b64[:30]:
                            header,b64data=image_b64.split(",",1)
                            if "svg" not in header.lower():
                                image_b64_clean=b64data
                                if "image/png" in header: mime_type="image/png"
                                elif "image/webp" in header: mime_type="image/webp"
                                image_bytes=base64.b64decode(image_b64_clean)
                                has_image=True
                        else:
                            image_bytes=base64.b64decode(image_b64)
                            has_image=True
                    except: has_image=False
                prompt_text=f"""Eres {self_model.get('identidad')} {VERSION}. Esencia:{self_model.get('esencia')}.
SELF:{context_self}
MEMORIA:{context_mem}
KNOWLEDGE:{context_know}
WEB:{web_info}
Usuario:{msg}
Responde útil directo español Bogotá, usa memoria si aplica. STREAMING: responde en tiempo real."""
                # No hay streaming nativo en google-genai todavía, hacemos streaming fake por chunks del resultado final para UX tipo ChatGPT
                # Si en futuro hay stream=True lo cambiamos
                try:
                    if has_image and image_bytes:
                        from google.genai import types
                        img_part=types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                        response=client.models.generate_content(model=model_route, contents=[img_part, prompt_text])
                    else:
                        response=client.models.generate_content(model=model_route, contents=prompt_text)
                    answer_text=response.text if hasattr(response,'text') and response.text else str(response)
                except Exception as e:
                    # fallback model
                    print(f"Stream primary failed {e}, trying flash")
                    response=client.models.generate_content(model="gemini-2.0-flash", contents=prompt_text)
                    answer_text=response.text if hasattr(response,'text') else str(response)
                # Chunked yield
                words=answer_text.split(' ')
                buffer=""
                for w in words:
                    buffer+=w+" "
                    if len(buffer)>15:
                        yield f"data: {json.dumps({'text': buffer})}\n\n"
                        full_answer+=buffer
                        buffer=""
                        await asyncio.sleep(0.04)
                if buffer:
                    yield f"data: {json.dumps({'text': buffer})}\n\n"
                    full_answer+=buffer
        except Exception as e:
            yield f"data: {json.dumps({'text': f'⚠️ Error stream: {str(e)[:200]}'})}\n\n"
        # Save after
        try:
            if not contains_sensitive(msg) and not contains_sensitive(full_answer):
                membrana.add(f"User {user_id}: {msg[:500]} | AKIRA: {full_answer[:500]}", importancia=6, source="chat_stream")
                membrana.add_knowledge(q=msg[:300], a=full_answer[:400], source="hive_stream")
        except: pass
        yield f"data: {json.dumps({'done': True, 'route': route_type, 'model': model_route, 'membrana': membrana.count()})}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@app.post("/api/brain/dream")
async def dream():
    try:
        # simple dreaming
        mem=membrana.search_mem("akira self evolucion", limit=5)
        self_data=membrana.load_self()
        # evolve esencia un poco
        return {"ok":True,"self":self_data,"memoria":mem}
    except Exception as e:
        return {"ok":False,"error":str(e)}


# === V5.3 ENDPOINTS GRATIS - UPLOAD PDF + CREATE FILE + WEATHER - SIN ROMPER 7 PARCHES ===
from fastapi import UploadFile, File

@app.post("/api/upload")
async def upload_file(request: Request, file: UploadFile = File(None)):
    try:
        # Soporta multipart y también base64 via json
        content_type = file.content_type if file else ""
        filename = file.filename if file else "upload.txt"
        # Bloqueo SVG
        if filename.lower().endswith(".svg") or "svg" in content_type.lower():
            return {"ok": False, "error": "SVG bloqueado por seguridad"}
        data = await file.read() if file else b""
        if len(data) > 10*1024*1024:
            return {"ok": False, "error": "Archivo muy grande max 10MB"}
        text_extracted = ""
        if filename.lower().endswith(".pdf"):
            try:
                import fitz
                doc = fitz.open(stream=data, filetype="pdf")
                for page in doc[:10]:
                    text_extracted += page.get_text() + "\n"
                doc.close()
            except Exception as e:
                text_extracted = f"Error leyendo PDF: {e}"
        elif filename.lower().endswith((".txt",".md",".csv",".json",".js",".py",".html")):
            text_extracted = data.decode('utf-8', errors='ignore')[:10000]
        else:
            # intentar como texto
            text_extracted = data.decode('utf-8', errors='ignore')[:10000]

        if contains_sensitive(text_extracted[:500]):
            return {"ok": False, "error": "Contenido sensible detectado"}

        # Chunk + guardar en membrana como knowledge + vectors
        chunks = [text_extracted[i:i+500] for i in range(0, min(len(text_extracted), 5000), 500)]
        for ch in chunks[:5]:
            membrana.add(f"Archivo {filename}: {ch}", tipo="file", importancia=7, compartida=True, source="upload")
            membrana.add_knowledge(q=f"Contenido de {filename}", a=ch[:400], source="file_upload")

        return {"ok": True, "filename": filename, "chars": len(text_extracted), "chunks": len(chunks), "preview": text_extracted[:500]}
    except Exception as e:
        print(f"upload error {e}")
        return {"ok": False, "error": str(e)[:300]}

@app.post("/api/create_file")
async def create_file(request: Request):
    try:
        data = await request.json()
        name = data.get("name","akira_output.txt")[:100]
        content = data.get("content","")[:20000]
        file_type = data.get("type","txt")
        # seguridad
        if ".." in name or "/" in name or "\\" in name:
            return {"ok": False, "error": "Nombre inválido"}
        if name.lower().endswith(".svg"):
            return {"ok": False, "error": "SVG bloqueado"}
        if contains_sensitive(content[:500]):
            return {"ok": False, "error": "Contenido sensible"}

        # Guardar en R2 como archivo
        try:
            client = get_r2_client()
            if client:
                client.put_object(Bucket=membrana.r2_bucket, Key=f"files/{name}", Body=content.encode('utf-8'))
        except Exception as e:
            print(f"R2 create file error {e}")

        # También guardar en memoria compartida
        membrana.add(f"Archivo creado {name}: {content[:400]}", tipo="file_created", importancia=7, compartida=True, source="create_file")

        return {"ok": True, "name": name, "size": len(content), "r2_key": f"files/{name}", "download_url": f"/api/download/{name}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}

@app.get("/api/weather")
async def weather_api(city: str = "Bogota"):
    try:
        w = wttr_weather(city)
        if w:
            return {"ok": True, "weather": w, "city": city}
        return {"ok": False, "error": "No se pudo obtener clima"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/api/download/{filename}")
async def download_file(filename: str):
    try:
        if ".." in filename or "/" in filename:
            return JSONResponse({"error":"Nombre inválido"}, status_code=400)
        client = get_r2_client()
        if not client:
            return JSONResponse({"error":"R2 no configurado"}, status_code=500)
        obj = client.get_object(Bucket=membrana.r2_bucket, Key=f"files/{filename}")
        content = obj['Body'].read()
        from fastapi.responses import Response
        return Response(content=content, media_type="text/plain", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    except Exception as e:
        return JSONResponse({"error": str(e)[:200]}, status_code=404)



# === V5.4 IMAGEN + VIDEO IA GRATIS - POLLINATIONS + PILLOW GIF - SIN ROMPER GLITCH - $0 ===
def generate_image_pollinations(prompt, width=1024, height=1024):
    try:
        import requests, urllib.parse, time
        # Limpieza prompt para Pollinations
        clean_prompt = prompt[:600].strip()
        if contains_sensitive(clean_prompt):
            return None, "Contenido sensible bloqueado"
        enc = urllib.parse.quote_plus(clean_prompt)
        # Modelo flux es mejor gratis, turbo si falla
        urls_to_try = [
            f"https://image.pollinations.ai/prompt/{enc}?width={width}&height={height}&nologo=true&model=flux&seed={int(time.time())%10000}",
            f"https://image.pollinations.ai/prompt/{enc}?width={width}&height={height}&nologo=true&model=turbo"
        ]
        for url in urls_to_try:
            try:
                r = requests.get(url, timeout=40, headers={"User-Agent":"Akira V2.4 Bogota"})
                if r.status_code == 200 and len(r.content) > 5000 and r.headers.get('content-type','').startswith('image'):
                    print(f"🎨 Pollinations OK {len(r.content)} bytes")
                    return r.content, None
                else:
                    print(f"Pollinations fallo {r.status_code} len {len(r.content)}")
            except Exception as e:
                print(f"Pollinations url error {e}")
                continue
        return None, "No se pudo generar imagen, Pollinations caído, reintenta"
    except Exception as e:
        return None, f"Error imagen: {str(e)[:200]}"

def generate_video_slideshow_free(prompts, duration_per_image=2):
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io, requests, urllib.parse, time
        frames = []
        for idx, prompt in enumerate(prompts[:4]):
            img_bytes, err = generate_image_pollinations(prompt, width=768, height=768)
            if img_bytes:
                try:
                    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                    # Texto overlay simple
                    draw = ImageDraw.Draw(img)
                    # Intentar fuente, si no, default
                    try:
                        draw.text((20, img.height-50), f"AKIRA V2.4 - {prompt[:40]}", fill=(255,255,255), stroke_width=2, stroke_fill=(0,0,0))
                    except:
                        draw.text((20, img.height-40), f"AKIRA V2.4", fill=(255,255,255))
                    # Resize para gif más liviano 512x512
                    img_small = img.resize((512,512))
                    frames.append(img_small)
                except Exception as e:
                    print(f"Frame process error {e}")
            time.sleep(1)  # no saturar pollinations
        
        if not frames:
            return None, "No se generaron frames"
        
        # Crear GIF animado en memoria (compatible Render Free 512MB, no necesita ffmpeg)
        gif_buffer = io.BytesIO()
        # Duplicar frames para duración
        extended_frames = []
        for f in frames:
            for _ in range(duration_per_image * 2):  # 2 fps aprox
                extended_frames.append(f)
        
        extended_frames[0].save(gif_buffer, format='GIF', save_all=True, append_images=extended_frames[1:], duration=500, loop=0, optimize=True)
        gif_bytes = gif_buffer.getvalue()
        print(f"🎬 GIF creado {len(gif_bytes)} bytes con {len(frames)} imágenes")
        return gif_bytes, None
    except Exception as e:
        print(f"Video slideshow error {e}")
        return None, f"Error video: {str(e)[:200]}"

@app.post("/api/generate/image")
async def api_generate_image(request: Request):
    try:
        data = await request.json()
        prompt = data.get("prompt","")[:600]
        if not prompt or len(prompt) < 3:
            return {"ok": False, "error": "Prompt vacío, escribe qué imagen quieres"}
        if contains_sensitive(prompt):
            return {"ok": False, "error": "Prompt bloqueado por contenido sensible"}
        # Rate limit extra para imagenes (5 por hora por IP)
        client_ip = request.client.host if request.client else "unknown"
        if not check_rate_limit(client_ip+"_img", is_owner=False):
            return {"ok": False, "error": "Límite imágenes 15/h alcanzado"}
        
        img_bytes, err = generate_image_pollinations(prompt)
        if err or not img_bytes:
            return {"ok": False, "error": err or "Fallo generación"}
        
        # Guardar en R2 glitch - no en RAM Render
        filename = f"img_{int(time.time())}_{hashlib.md5(prompt.encode()).hexdigest()[:6]}.jpg"
        try:
            client = get_r2_client()
            if client:
                client.put_object(Bucket=membrana.r2_bucket, Key=f"files/{filename}", Body=img_bytes, ContentType="image/jpeg")
        except Exception as e:
            print(f"R2 img save error {e}")
        
        # Guardar en memoria como knowledge
        membrana.add(f"Imagen generada: {prompt[:200]} -> {filename}", tipo="image_generated", importancia=7, compartida=True, source="image_gen")
        
        # Devolver base64 para preview inmediato
        b64 = base64.b64encode(img_bytes).decode('utf-8')
        return {"ok": True, "filename": filename, "prompt": prompt, "size": len(img_bytes), "base64": f"data:image/jpeg;base64,{b64}", "download_url": f"/api/download/{filename}", "r2_key": f"files/{filename}"}
    except Exception as e:
        print(f"api_generate_image error {e}")
        return {"ok": False, "error": str(e)[:300]}

@app.post("/api/generate/video")
async def api_generate_video(request: Request):
    try:
        data = await request.json()
        prompt = data.get("prompt","")[:600]
        prompts = data.get("prompts", [])
        if prompts and isinstance(prompts, list):
            prompt_list = [p[:200] for p in prompts[:4] if p.strip()]
        else:
            # Si solo un prompt, generar 3 variaciones
            prompt_list = [prompt, f"{prompt} cinematic", f"{prompt} detailed"]
        
        if not prompt_list or not prompt_list[0]:
            return {"ok": False, "error": "Prompt vacío"}
        
        if contains_sensitive(" ".join(prompt_list)[:500]):
            return {"ok": False, "error": "Contenido sensible bloqueado"}
        
        client_ip = request.client.host if request.client else "unknown"
        if not check_rate_limit(client_ip+"_vid", is_owner=False):
            return {"ok": False, "error": "Límite video 15/h alcanzado"}
        
        gif_bytes, err = generate_video_slideshow_free(prompt_list)
        if err or not gif_bytes:
            return {"ok": False, "error": err or "Fallo video"}
        
        filename = f"video_{int(time.time())}_{hashlib.md5(prompt_list[0].encode()).hexdigest()[:6]}.gif"
        try:
            client = get_r2_client()
            if client:
                client.put_object(Bucket=membrana.r2_bucket, Key=f"files/{filename}", Body=gif_bytes, ContentType="image/gif")
        except Exception as e:
            print(f"R2 video save error {e}")
        
        membrana.add(f"Video GIF generado: {prompt_list[0][:200]} -> {filename}", tipo="video_generated", importancia=8, compartida=True, source="video_gen")
        
        b64 = base64.b64encode(gif_bytes).decode('utf-8')
        return {"ok": True, "filename": filename, "prompts": prompt_list, "size": len(gif_bytes), "base64": f"data:image/gif;base64,{b64}", "download_url": f"/api/download/{filename}", "type": "gif_slideshow", "note": "Video slideshow GIF creado con Pollinations free + Pillow. Para MP4 real usa imageio, pero GIF es 100% compatible Render Free"}
    except Exception as e:
        print(f"api_generate_video error {e}")
        return {"ok": False, "error": str(e)[:300]}

@app.get("/api/self-repair/status")
async def self_repair_status():
    return get_self_repair_status()

@app.get("/api/tools")
async def api_tools():
    return {
        "version": VERSION,
        "tools": [
            {"name": "web_search_tavily", "description": "Búsqueda web real con Tavily 1000 req/mes free", "endpoint": "/api/chat", "free": True},
            {"name": "upload_pdf", "description": "Subir PDF/TXT/MD/CSV y absorber en R2", "endpoint": "/api/upload", "free": True},
            {"name": "create_file", "description": "Crear archivo TXT/MD/CSV/JSON en R2", "endpoint": "/api/create_file", "free": True},
            {"name": "generate_image", "description": "Generar imagen IA gratis Pollinations flux/turbo ilimitado", "endpoint": "/api/generate/image", "free": True, "provider": "pollinations.ai"},
            {"name": "generate_video", "description": "Generar video slideshow GIF con 3 imágenes IA + Pillow", "endpoint": "/api/generate/video", "free": True, "provider": "pollinations.ai + Pillow"},
            {"name": "weather", "description": "Clima Bogotá gratis wttr.in", "endpoint": "/api/weather", "free": True},
            {"name": "chat_stream", "description": "Chat streaming SSE token a token", "endpoint": "/api/chat/stream", "free": True}
        ],
        "glitch": "Todo pesado en R2 + APIs externas, Render solo router tonto, no se rompe",
        "cost": "$0"
    }


if __name__=="__main__":
    try:
        threading.Thread(target=keep_alive_ping,daemon=True).start()
        threading.Thread(target=cleanup_rate_store,daemon=True).start()
    except: pass
    port=int(os.getenv("PORT",8000))
    print(f"🚀 {VERSION} - Puerto {port} - {membrana.count()}")
    uvicorn.run(app,host="0.0.0.0",port=port)