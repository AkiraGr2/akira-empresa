# HANDOFF TÉCNICO — Proyecto Akira
**Fecha:** 2026-09-29 (actualizado tras rediseño visual completo + Cytoscape + Oficina animada)
**De:** Sesión de Claude (rol: garante técnico) → próxima sesión de Claude
**Estado global:** 9 de 14 fases del Contrato V8 completadas + rediseño visual cerrado. Próxima: Fase 10 (Mission Engine).

---

## 0. AVISO CRÍTICO PARA LA PRÓXIMA SESIÓN

Antes de tocar cualquier código, leer este handoff completo. Contiene trabajo visual extenso hecho hoy que NO debe rehacerse. Resumen de lo nuevo que NO está en el handoff anterior:

1. Oficina con sprites pixel-art reales (pack CC0 de 2dPig).
2. Membrana migrada de Canvas 2D custom a Cytoscape.js (estilo Obsidian real).
3. Sidebar con 7 secciones (antes tenía 3).
4. Assets CC0 agregados al repo en `assets/office/`.
5. Cache-busting con `?v=akira-final-v5` en los scripts del index.html.

---

## 1. ROL DE CLAUDE EN ESTE PROYECTO

Claude actúa como **garante técnico** del proyecto Akira. Reglas fijadas en handoffs previos:

1. Distinguir siempre el estado real: 🟢 verificado / 🟡 parcial / 🔴 no existe / ⚪ futuro.
2. No inventar capacidades ni confundir arquitectura aspiracional con lo desplegado.
3. Una sola pregunta a la vez a Jhon.
4. Si el código real contradice un documento, señalarlo ANTES de modificar nada.
5. Nada se da por terminado sin prueba directa en producción.
6. No tocar Panel/Oficina (Fase 8 del Pasaporte) hasta que existan agentes reales.
7. Si una prueba no prueba lo que se cree, corregir la prueba antes de seguir.
8. Las decisiones técnicas las toma Claude. Jhon da apoyo y contexto de negocio.
9. Explicar en simple: Jhon no es programador.
10. Entregar archivos completos para copiar y pegar, siempre con el link.
11. Los links van siempre en texto plano, uno por línea, para copiar y pegar tal cual.
12. Cuando toque editar un archivo, entregarlo COMPLETO (no fragmentos, no "cambia esta línea").

---

## 2. CONTEXTO DEL PROYECTO

Jhon (freelance dev, Bogotá, Colombia) construye **Akira**, IA/colmena personal.

- **Frontend:** `AkiraGr2/akira-v3-frontend` → https://akiragr2.github.io/akira-v3-frontend/
- **Backend:** `AkiraGr2/akira-empresa` (`nexus.py`, FastAPI en Render) → https://akira-empresa.onrender.com
- **Owner:** bjhon9161@gmail.com
- Render plan gratis + UptimeRobot.
- Base de datos: **PostgreSQL en Neon**.
- R2 presente pero sin escritura real confirmada.
- **Google Client ID:** `148150327312-7k5g3go06tat9gv61c8v0rbbedcusoqn.apps.googleusercontent.com`
- Jhon usa **Android con Chrome**. Verificaciones vía navegador móvil o panel admin.

**Cómo auditar:** Claude NO puede abrir URLs de GitHub. Jhon pega el contenido del archivo en el chat, o usa Ctrl+F en GitHub para confirmar que una función existe.

**Links habituales:**
- Backend: `https://github.com/AkiraGr2/akira-empresa/blob/main/nexus.py`
- Persistencia: `https://github.com/AkiraGr2/akira-empresa/blob/main/persistence/<archivo>.py`
- Frontend HTML: `https://github.com/AkiraGr2/akira-v3-frontend/blob/main/index.html`
- Frontend JS: `https://github.com/AkiraGr2/akira-v3-frontend/tree/main/js`
- Health: `https://akira-empresa.onrender.com/health`
- Docs: `https://akira-empresa.onrender.com/docs`
- Persistence status: `https://akira-empresa.onrender.com/api/v8/persistence/status`

---

## 3. DECISIONES BLOQUEADAS (D001–D015)

- **D001:** Akira no depende de un único modelo.
- **D002:** Render no es memoria permanente.
- **D003:** IndexedDB = memoria local / hot cache.
- **D004:** R2 = almacenamiento persistente compartido.
- **D005:** self-model funcional, no afirmaciones de conciencia subjetiva.
- **D006:** toda memoria anunciada debe poder recuperarse.
- **D007:** todo aprendizaje produce registro persistente.
- **D008:** toda reparación produce pruebas/validación.
- **D009:** el Office muestra estados reales, no actividad simulada.
- **D010:** el Hive no absorbe automáticamente info privada.
- **D011:** acciones irreversibles requieren autorización humana.
- **D012:** no parches aislados sin revisar arquitectura.
- **D013:** primero arquitectura, después código coherente.
- **D014:** la versión de la interfaz no prueba que la capacidad exista.
- **D015:** fuente de verdad = documentos + código realmente desplegado.

---

## 4. ESTADO POR BLOQUE (B1-B5)

### B1 — Sesión firmada en el frontend
🟢 VERIFICADO. `akiraAuthHeaders()` envía `Authorization: Bearer <token>` no vencido. Pantalla Cuenta muestra "🔒 sesión verificada (propietario)".

### B2 — Confianza en cliente apagada
🟢 VERIFICADO. `AKIRA_TRUST_CLIENT_OWNER=0`. Frontend valida con `/api/v8/me`. `akira_auth.py` valida HMAC-SHA256.
🟡 Pendiente: rotación de clave admin expuesta en historial. Jhon decidió NO rotar (riesgo bajo).

### B3a — Contadores reales
🟢 VERIFICADO. `MembraneCounts` lee de Postgres. Si no hay datos, dice `available: false`.

### B3b — Ingesta real de memorias
🟢 VERIFICADO CON PRUEBA DE REINICIO. `POST /api/memory/ingest`. Sobrevivieron a múltiples reinicios.

### B3c — Recuperación real en el chat
🟢 VERIFICADO. `POST /api/memory/search`. Si no hay memorias, el prompt exige no afirmar recuerdos.

### B3c-fix — Identidad blindada
🟢 VERIFICADO. 20 frases prohibidas. Filtro `_sanitize_memory_content()`.

### B4 — Event loop no bloqueante
🟢 VERIFICADO. Gemini/Groq corren en `asyncio.to_thread()`.

### B5 — Pool de keys con rotación
🟢 VERIFICADO. `/health` expone `gemini_keys_count`, `groq_keys_count`, `gemini_keys_failed`.

### B5-extra — Extracción de PDF
🟢 VERIFICADO. `POST /api/extract-file` con PyMuPDF, límite 5MB.

---
## 5. FASES DEL CONTRATO V8 — CERRADAS

### FASE 5 — Self-model persistente
🟢 VERIFICADO CON PRUEBA DE REINICIO.
- Migración `002_self_model`. Entidad `self_model` (singleton `id="akira_primary"`).
- 11 campos JSONB.
- Endpoints: `GET /api/v8/self`, `PATCH /api/v8/self`.
- Evidencia: `version: 4` tras reinicio.

### FASE 6 — Grafo neuronal + aprendizaje persistente
🟢 VERIFICADO CON PRUEBA DE REINICIO.
- Migración `003_learning_graph`. 3 tablas: `learning_events`, `graph_nodes`, `graph_edges`.
- Métodos: `save_learning()`, `record_reuse()`, `create_node()`, `create_edge()`, `related_nodes()`.
- Métodos agregados HOY: `list_graph_nodes()`, `list_graph_edges()` en `persistence/service.py`.
- Endpoint NUEVO HOY: `GET /api/v8/graph/overview` (ver sección 9).
- Evidencia: `reuse_count: 1` tras reinicio. Y 2 nodos + 1 arista tras hoy.

### FASE 7 — Ciclo cognitivo persistente
🟢 VERIFICADO CON PRUEBA DE REINICIO.
- Migraciones `004`, `005`, `006`. Tablas `cognitive_cycles` y `cognitive_events` (append-only).
- 9 etapas: observe → interpret → reason → decide → act → observe_result → evaluate → learn → update_self_model.
- **Solo `reason` usa LLM.** Otras 8 etapas son lógica pura.

### FASE 8 — Tool Registry + invocaciones
🟢 VERIFICADO EN PRODUCCIÓN.
- Migración `007_tools_registry`. 2 tablas: `tools`, `tool_invocations`.
- Auto-seed al startup: 10 tools registradas.
- **10 tools:** web_search, memory_save, memory_search, graph_create_node, graph_related, learning_save, self_model_read, extract_pdf, image_generate, cognitive_cycle.

### FASE 9 — Agentes + tareas
🟢 VERIFICADO CON PRUEBA DE REINICIO + CONTRATO V8 s11 COMPLETO.

**Migración `009_agents_contract_v8`** — añade 4 columnas para cumplir Contrato V8 s11:
  - `agents.current_action` (TEXT)
  - `agent_tasks.model` (TEXT)
  - `agent_tasks.mission_id` (TEXT)
  - `agent_tasks.memory_used` (JSONB)

**5 agentes seeded:**
- `researcher` — tools: web_search, memory_search
- `memorizer` — tools: memory_save, memory_search
- `graph_builder` — tools: graph_create_node, graph_related
- `learner` — tools: learning_save, memory_save
- `internal` — tools: self_model_read, cognitive_cycle

**Contrato V8 s11 — los 11 campos, todos 🟢:**
`agent_id`, `task_id`, `status`, `model`, `start_time`, `current_action`, `tool`, `mission`, `result`, `errors`, `memory_used`.

**Evidencia:**
- 4 tareas `researcher → web_search completed` con duraciones reales (~6000ms cada una).
- Prueba de reinicio: 3 tareas → reinicio → 4 tareas. Sobrevivieron.
- Test V8 s11: `model="gemini-3.8-flash"` y `mission_id` guardados. Filtro por `mission_id` devolvió 2 tareas. `memory_used` persistió.

**Nota menor de diseño (no bug):** cuando el tool no usa LLM (ej. `memory_save`), el campo `model` guarda lo que el caller mande. En Fase 10 conviene que el runner infiera `model` solo cuando aplique.

---
## 6. REDISEÑO VISUAL — CERRADO HOY (2026-09-29)

### 6.1 — Sidebar nuevo (7 secciones)

Antes: 3 (Chat, Cuenta, Admin). Ahora: 7.

Orden actual:
1. 💬 Chat
2. 🧠 Membrana
3. 🏢 Oficina
4. 📊 Niveles
5. 💼 Upwork (stub)
6. 🔑 Cuenta
7. 👑 Admin (panel técnico puro, sin canvas embebidos)

Cada sección es una `div.section`. `showSection(name)` las activa y dispara `akira:section-shown` para que los canvas se inicialicen con el tamaño correcto.

### 6.2 — Membrana (estilo Obsidian real)

**Estado:** 🟢 FUNCIONAL con Cytoscape.js.

**Historial de iteraciones hoy:**
- V1: simulación con 27 nodos random → H-10 (violación de D009).
- V2–V4: Canvas 2D custom, física manual. Bugs: fuerzas acumuladas (nodos explotaban), waypoints diagonal cruzando muebles.
- V5–V8: iteraciones con Pixi.js → pantalla negra. Descartado.
- V9–V11: Canvas 2D custom con máquina de estados de gestos. Funcional pero limitado.
- **V12 (actual):** migración a **Cytoscape.js 3.30.2**.

**Cytoscape.js:**
- Licencia MIT. Gratis, sin atribución.
- CDN: `https://unpkg.com/cytoscape@3.30.2/dist/cytoscape.min.js`
- Cargado en `index.html` (permitido por CSP con `unpkg.com` en `script-src`).
- Contenedor: `<div id="membraneCy">` (Cytoscape NO usa `<canvas>`, usa un div).
- Layout: `cose` (incluido, sin plugins).
- Estilo: nodos sólidos color por tipo, aristas rectas, fondo negro puro.

**Lo que Cytoscape da gratis:**
- Pinch-zoom con anchor correcto.
- Pan con drag.
- Tap en nodo → selecciona + resalta vecinos + atenúa el resto.
- Doble-tap → encuadra todo.
- Drag de nodo individual.

**Colores por tipo (`NODE_TYPE_COLORS`):**
- concept `#8b5cf6`, person `#ec4899`, project `#f59e0b`, tool `#06b6d4`, experience `#10b981`, document `#a78bfa`, skill `#facc15`, error `#ef4444`, solution `#22c55e`, mission `#fb923c`.

**Endpoint consumido:** `GET /api/v8/graph/overview` (nuevo, ver sección 9).

### 6.3 — Oficina (Munder Difflin + 2dPig CC0)

**Estado:** 🟢 FUNCIONAL. 5 agentes reales caminando por pasillos.

**Pack de assets:** "Pixel Office Asset Pack" de 2dPig.
- Licencia CC0 (confirmada en LICENSE.txt y README.txt).
- Gratis, sin atribución obligatoria.
- Origen: https://2dpig.itch.io/pixel-office-asset-pack

**Archivos subidos a assets/office/:**
- LargePixelOffice.png (720x630) — escena completa limpia (los personajes decorativos y gatos se borraron con cleanup.pictures).
- PixelOffice.png (256x224) — escena original, sin usar.
- PixelOfficeAssets.png (256x160) — hoja con sprites sueltos, de aquí se recortan los 5 personajes.
- .gitkeep

**Coordenadas de los 5 sprites en PixelOfficeAssets.png (verificadas con image-map.net):**
- researcher: [2, 105, 17, 128] (15x23)
- memorizer: [19, 104, 38, 128] (19x24)
- graph_builder: [40, 107, 53, 128] (13x21)
- learner: [3, 132, 20, 155] (17x23)
- internal: [22, 132, 39, 155] (17x23)

**Waypoints / pasillos (verificados con image-map.net):**
- Pasillo horizontal grande: Y entre 338 y 372, uso Y = 355
- Pasillo vertical izquierdo: X entre 3 y 95, uso X = 49
- Pasillo vertical central: X entre 315 y 409, uso X = 362
- Pasillo vertical derecho: X entre 630 y 720, uso X = 675

**Routing de movimiento:** los agentes solo caminan en horizontal o vertical dentro de los pasillos. Nunca en diagonal. Función _buildPath(cx, cy, tx, ty) calcula la ruta pasando por los cruces.

**Comportamiento por estado:**
- idle → deambula por waypoints aleatorios (decoración).
- busy → vuelve a su HOME (escritorio base) y hace bobbing.
- error → LED rojo.

**Importante D009:** los estados son reales (vienen de /api/v8/agents). El caminar de idle es decoración. Los busy sí vuelven a su puesto real. Esto respeta D009.

**Escala de sprites:** SPRITE_SCALE = 2 (antes 3, se veían gigantes).

**Frames:** los sprites de 2dPig son poses únicas. No tienen animación de caminata. Solo se mueven y hacen bobbing. Para caminata real haría falta otro pack (ver sección 11).

---

### 6.4 — Niveles

🟢 FUNCIONAL. Lee de `GET /api/v8/self` y renderiza la lista F1–F14 con 🟢/🟡/🔴 según `capabilities`.

### 6.5 — Upwork (stub)

🟡 STUB. Solo tiene un textarea que manda la descripción a `/api/chat` pidiendo propuesta. No busca trabajos, no filtra, no aplica. El panel completo va dentro de Fase 10 (ver sección 12).

### 6.6 — Cache-busting

En `index.html`, los 4 `<script>` al final llevan `?v=akira-final-v5`:

<script src="./js/hybrid_sync.js?v=akira-final-v5"></script>
<script src="./js/obsidian_membrane.js?v=akira-final-v5"></script>
<script src="./js/akira_brain.js?v=akira-final-v5"></script>
<script src="./js/akira_extras.js?v=akira-final-v5"></script>

Esto evita el problema H-09 (Chrome Android cacheando versiones viejas).

---
## 7. HALLAZGOS — ESTADO FINAL

**Cerrados:**

- 🟢 H-01 — Akira alucinaba recuerdos (cerrado en B3c).
- 🟢 H-02 — Cuota Gemini agotada (cerrado en B5).
- 🟢 H-03 — 4 botones huérfanos (cerrado).
- 🟢 H-04 — Pool de keys muerto (cerrado en B5).
- 🟢 H-05 — `is_owner` viajando desde frontend (cerrado).
- 🟢 H-06 — GITHUB_REPO mal configurado (cerrado).
- 🟢 H-07 — `obsidian_membrane.js` fantasma (no aplicaba).
- 🟢 H-08 — Bug del `orderable` en `agents` causaba "Failed to fetch". Cerrado con fix en `core.py`.
- 🟢 H-09 — Caché HTTP de Chrome Android guardaba 401. Cerrado con cache-busting.
- 🟢 H-10 — Oficina y Membrana simuladas. Cerrado HOY.
  - Membrana: ahora lee de `graph_nodes`/`graph_edges` reales vía Cytoscape.js.
  - Oficina: ahora lee de `/api/v8/agents` real. Los 5 agentes reales caminando.
  - Lección: cuando algo se declara "simulado" y viola una decisión bloqueada, hay que atacarlo antes de seguir con otra fase.

**Pendientes:**

- 🟡 H-11 — `sw.js` desregistrado por `index.html`. El SW está bien escrito pero el `DOMContentLoaded` lo mata. Decisión pendiente: dejarlo off o rediseñar registro.
- 🟡 H-12 — Warning `fitz deprecated`. Cambiar `import fitz` por `import pymupdf` en `nexus.py` (2 lugares). Mantenimiento, 2 min.
- 🟡 Rotación de clave admin (decisión Jhon: no rotar).
- 🟡 Sprites de la Oficina son estáticos (sin animación de caminata). Ver sección 11 para opciones.

---
## 8. ARCHIVOS DEL PROYECTO

### 8.1 — Backend (`AkiraGr2/akira-empresa`)

- `nexus.py` — FastAPI. Modificado hoy: agregado `GET /api/v8/graph/overview`.
- `akira_auth.py` — Google + sesión HMAC.
- `membrane_compat.py` — contadores reales.
- `persistence/`:
  - `core.py` — errores, ENTITIES (10 entidades), validadores.
  - `service.py` — PersistenceService. Modificado hoy: agregados `list_graph_nodes()` y `list_graph_edges()`.
  - `api.py` — endpoint de estado de persistencia.
  - `runtime.py` — arranque aislado en hilo.
  - `inmemory.py` — repo para tests.
  - `postgres.py` — repo real con psycopg3.
  - `migrations.py` — 9 migraciones.
  - `selftest.py` — 9 tests automáticos.
- `requirements.txt` — con `psycopg[binary,pool]>=3.2`, `PyMuPDF`, etc.

---
### 8.2 — Frontend (`AkiraGr2/akira-v3-frontend`)

- `index.html` — Reescrito hoy. 7 secciones. Cytoscape.js cargado desde CDN. Cache-busting v5.
- `js/akira_brain.js` — chat, streaming, auto-repair. (sin tocar hoy)
- `js/hybrid_sync.js` — IndexedDB + POST `/api/memory/ingest`. (sin tocar hoy)
- `js/obsidian_membrane.js` — Reescrito hoy (V12.0). Membrana con Cytoscape, Oficina con 2dPig.
- `js/akira_extras.js` — toggleVoice, uploadFileToAkira, createFileAkira. (sin tocar hoy)
- `sw.js` — service worker con kill-switch (desregistrado).

### 8.3 — Assets (`AkiraGr2/akira-v3-frontend/assets/office/`)

- `LargePixelOffice.png` (720×630, 415 KB) — escena limpia.
- `PixelOffice.png` (256×224) — original, no usada.
- `PixelOfficeAssets.png` (256×160) — hoja de sprites.
- `.gitkeep`

---
### 8.4 — Base de datos (Neon Postgres)

**9 migraciones aplicadas:**

1. `001_memories_audit`
2. `002_self_model`
3. `003_learning_graph`
4. `004_cognitive_cycle`
5. `005_cognitive_events_idempotency`
6. `006_cognitive_events_textid`
7. `007_tools_registry`
8. `008_agents`
9. `009_agents_contract_v8`

**Estado actual:** 22+ memorias activas, 1 self-model (v4+), 10 tools, 5 agentes, 4+ tareas, 1+ learning, 1+ ciclos, 2 nodos de grafo + 1 arista.

---
## 9. ENDPOINTS DEL BACKEND

### Públicos

- `GET /health`, `GET /api/countermeasures`
- `GET /api/self-repair/status`, `/propose` (placeholders)
- `GET /api/brain/shared`, `/count`
- `GET /api/tools`
- `POST /api/sync_to_r2` (no-op), `POST /api/feedback` (no-op)
- `POST /api/auth/google`
- `GET /api/v8/auth/status`, `GET /api/v8/me`
- `POST /api/chat`, `POST /api/chat/stream`
- `POST /api/generate/image`, `POST /api/extract-file`

---
---
### Requieren sesión firmada

- `POST /api/memory/ingest`, `POST /api/memory/search`
- `GET /api/v8/self`, `PATCH /api/v8/self`
- `POST /api/v8/learning`, `GET /api/v8/learning/{id}`, `POST /api/v8/learning/{id}/reuse`
- `POST /api/v8/graph/node`, `GET /api/v8/graph/node/{id}`, `POST /api/v8/graph/edge`, `GET /api/v8/graph/related/{id}`
- `POST /api/v8/cognitive/cycle`, `GET /api/v8/cognitive/cycle/{id}`, `GET /api/v8/cognitive/cycles`
- `GET /api/v8/tools`, `GET /api/v8/tools/invocations`, `GET /api/v8/tools/{name}`, `POST /api/v8/tools/{name}/invoke`
- `GET /api/v8/agents` (query `?role=&status=`)
- `GET /api/v8/agents/{name}` (devuelve agente + `recent_tasks`)
- `POST /api/v8/agents/{name}/task` (acepta `tool_name`, `inputs`, `model`, `mission_id`)
- `GET /api/v8/tasks` (query `?agent_name=&status=&mission_id=&limit=`)
- `GET /api/v8/tasks/{task_id}`

---
### Endpoint nuevo (creado hoy)

- `GET /api/v8/graph/overview` — devuelve `{ok, nodes:[], edges:[], counts:{nodes, edges, by_type, by_relation}, generated_at}`. Requiere sesión firmada. Solo nodos/aristas con `status=active`. Uso: alimenta la Membrana de Cytoscape.

### Estado de persistencia

- `GET /api/v8/persistence/status`

---
## 10. FASES DEL CONTRATO V8 — DÓNDE ESTAMOS

- Fase 1 — Contrato Maestro ✅
- Fase 2 — Auditoría técnica ✅
- Fase 3 — Modelo de datos + persistencia ✅
- Fase 4 — Membrana + Memoria ✅
- Fase 5 — Self-model ✅
- Fase 6 — Grafo + aprendizaje ✅
- Fase 7 — Ciclo cognitivo ✅
- Fase 8 — Tools + Tool Registry ✅
- Fase 9 — Agentes ✅
- Rediseño Oficina/Membrana ✅ CERRADO HOY
- Fase 10 — Mission Engine 🔴 AQUÍ VAMOS AHORA
- Fase 11 — Self-repair real 🔴
- Fase 12 — Evolution Engine 🔴
- Fase 13 — Autonomía controlada ⚪
- Fase 14 — Auditoría V8 end-to-end ⚪

---
## 11. PENDIENTES DEL REDISEÑO VISUAL (no bloquean Fase 10)

Ninguno de estos bloquea Fase 10. Son mejoras futuras cuando haya tiempo/dinero:

1. **Sprites animados de la Oficina.** Los actuales son estáticos. Para caminata real haría falta:
   - Pack pagado de LimeZu "Modern Office" ($2.50 aprox): ambiente + personajes del mismo autor.
   - O pack CC0 con animación de caminata (buscar en itch.io "rpg character sprite sheet CC0").
   - O pack de Arlan_TR (Julia animada, CC0 informal) mezclado con 2dPig (choca un poco el estilo).

2. **Handoff actualizado.** Este archivo.

3. **H-11 (SW).** Decisión pendiente: dejarlo off o rediseñar.

4. **H-12 (fitz deprecated).** Cambiar `import fitz` por `import pymupdf`.

---
## 12. DISEÑO APROBADO PARA FASE 10

### Clarificación sobre secciones del panel

- **Niveles** = meta-información del proyecto. Qué fases van, qué falta. Para Jhon y Claude. No es funcionalidad de Akira. (Ya implementado como sección, solo lee self-model.)
- **Upwork** = caso de uso real de negocio. Akira busca trabajos, filtra, prepara propuestas, entrega proyectos freelance. Conecta directo con Fase 10: una oportunidad de Upwork = una misión.

### Lo que Jhon quiere en Upwork (visión)

- Poder tomar trabajos de programación de Upwork y que Akira + agentes hagan el trabajo técnico completo.
- Akira analiza la descripción, decide si es viable, propone un plan, escribe código, prueba, genera documentación, empaca todo listo para entregar.
- Jhon entrega (humano, por ToS de Upwork).
- Akira da instrucciones paso a paso de cómo entregar, a quién, qué decirle al cliente.

---
### Decisión de diseño de Fase 10 (a tomar)

- ¿Mission Engine planifica con LLM o con lógica pura?
  - Recomendación tentativa: planificación híbrida — LLM propone el plan, backend lo valida contra agentes y tools disponibles, humano (o política) autoriza antes de ejecutar. Respeta D011.
- ¿Cómo se relaciona una misión con el ciclo cognitivo (Fase 7)?
  - Recomendación: una misión es una cadena de ciclos cognitivos, uno por paso. No reemplazar Fase 7, componerla.

### Límites honestos

- Upwork tiene ToS. Automatizar aplicaciones o scraping masivo es contra sus reglas. Se puede hacer asistido (Akira prepara todo, Jhon aprueba y envía), no autónomo.
- Sin Fase 10 no hay orquestación. Los agentes hoy solo ejecutan una tarea a la vez.

---
## 13. CÓMO AUDITAR (regla 5)

Cuando Jhon diga "eso ya quedó", pedir el código real. Como Claude NO puede abrir URLs de GitHub:

- Forma A: Jhon pega el archivo completo en el chat.
- Forma B: Jhon usa Ctrl+F del navegador en GitHub y confirma que una función existe.

**Cuando un endpoint falla con "Failed to fetch" en el panel pero funciona en URL directa:**

1. Sospechar 500 sin CORS (ver H-08).
2. Revisar `orderable` de la entidad correspondiente en `core.py`.
3. Añadir cache-busting (`?_=Date.now()`) en el fetch del frontend.
4. Probar en incógnito para descartar caché.

**Cuando Chrome carga versión vieja:**

1. Borrar solo caché (chrome://settings/clearBrowserData → "Última hora").
2. O subir el `?v=` en los `<script>` del `index.html`.

**Verificar que un assets está bien subido:**

- Abrir la URL directa: `https://akiragr2.github.io/akira-v3-frontend/assets/office/<archivo>.png`
- Si aparece la imagen, está OK.

**Verificar que Cytoscape cargó:**

- En la consola del navegador: `typeof window.cytoscape` debería devolver `"function"`. Si devuelve `"undefined"`, el CDN no cargó.

---
## 14. LIMITACIONES DE CLAUDE

- NO puede abrir URLs de GitHub directamente.
- NO puede ver videos, imágenes en movimiento, ni ejecutar código.
- NO puede ver el render final de la UI. Solo ve capturas estáticas que Jhon manda.
- Jhon usa Android con Chrome. Verificaciones desde panel admin del frontend o abriendo URLs en navegador móvil.
- Chrome Android cachea respuestas 401 y assets estáticos agresivamente. Usar incógnito para verificar comportamiento limpio.

---
## 15. REGLA OPERATIVA

- Cada "eso ya quedó" → pedir código real antes de marcar 🟢.
- Cada prueba debe probar lo que se cree. Corregir si no.
- Archivos completos para copiar y pegar, siempre con el link.
- Explicar en simple antes de cada cambio.
- Nunca devolver a buscar — si ya lo pasaste, volver a pasarlo.
- Links en texto plano, uno por línea, sin formato que dificulte copiar y pegar.
- Prueba de reinicio obligatoria para cualquier capacidad que se declare persistente.
- Cuando Jhon pide "link pa ver", responder con una sola línea en bloque de código, sin adornos.

---

## 16. FRASE DE CONTINUIDAD

AKIRA NO SE CONSTRUYE A BASE DE PARCHES.

PRIMERO: ENTENDER.
DESPUÉS: DISEÑAR.
DESPUÉS: CONSTRUIR.
DESPUÉS: PROBAR.
DESPUÉS: APRENDER.
Y SOLO ENTONCES: EVOLUCIONAR.

---
## 17. RESUMEN EJECUTIVO PARA LA PRÓXIMA SESIÓN

**Si acabas de llegar y tienes 30 segundos:**

1. Fases 1–9 del Contrato V8: cerradas y verificadas.
2. Rediseño visual (Membrana + Oficina): cerrado hoy. Membrana usa Cytoscape.js. Oficina usa sprites 2dPig CC0.
3. Lo próximo es Fase 10: Mission Engine. El diseño está en la sección 12.
4. Antes de tocar código: preguntar a Jhon si quiere arrancar Fase 10 o resolver algún pendiente visual primero.
5. Reglas de oro: archivos completos, links texto plano, una pregunta a la vez, verificar antes de declarar terminado.

---

FIN DEL HANDOFF — 2026-09-29 (tras Fase 9 + rediseño visual cerrado + Cytoscape + Oficina animada).