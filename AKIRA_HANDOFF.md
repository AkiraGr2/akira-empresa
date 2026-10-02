# AKIRA V8 — HANDOFF MAESTRO / ESTADO DEL PROYECTO

Fecha de corte: 2026-10-02
Propósito: preservar contexto técnico, decisiones, errores encontrados, correcciones, pruebas y próximos pasos para continuar Akira sin perder aprendizaje.

---

## 0. REGLA PERMANENTE DE DESARROLLO

Toda modificación de Akira debe seguir:

**Analizar → auditar → modificar → volver a auditar → verificar → probar → solo entonces darlo por cerrado.**

Principios:
- Priorizar soluciones gratuitas.
- No asumir que el usuario pagará, agregará tarjeta o comprará créditos.
- No pedir API keys ni secretos al usuario.
- Si hay cambios en Render/OpenRouter, indicar exactamente qué tocar y qué NO tocar.
- El asistente actúa como garante técnico: debe revisar código, detectar regresiones, auditar después de modificar y proponer mejoras cuando sean necesarias.
- No declarar una tarea cerrada solo porque compila: debe existir verificación funcional cuando sea posible.

---

## 1. PROYECTO

Proyecto: **Akira V8**

Repositorios:
- Frontend: `AkiraGr2/akira-v3-frontend`
- Backend: `AkiraGr2/akira-empresa`

Backend principal:
- `nexus.py`
- `akira_auth.py`
- `membrane_compat.py`
- `persistence/`
  - core
  - service
  - api
  - runtime
  - inmemory
  - postgres
  - migrations
  - selftest
- `requirements.txt`

Frontend:
- `index.html`
- `js/akira_admin.js` — módulo administrativo estable; evitar tocarlo sin necesidad.
- `js/akira_missions_panel.js` — panel de misiones.
- `js/akira_brain.js` — chat/cerebro/contexto.

---

## 2. ESTADO ACTUAL

Render está **Live** después de la última limpieza.

Último commit backend:
`95c9f3e7f1d79d2ac3adcdb0422839a12bb41cc7`

Ese commit retiró el modo temporal usado para probar OpenRouter.

La arquitectura normal de proveedores quedó:

**Gemini → Groq → OpenRouter Free**

OpenRouter se probó realmente y respondió correctamente mediante:
- router: `openrouter/free`
- modelo seleccionado en la prueba: `openai/gpt-oss-120b`

No se agregó tarjeta ni se realizó pago.

La variable temporal:
`AKIRA_FORCE_OPENROUTER_TEST=1`

fue usada solo durante la prueba y después retirada del código. Debe permanecer eliminada de Render/Environment.

---

## 3. OPENROUTER — ESTADO Y APRENDIZAJE

El usuario creó manualmente una API key de OpenRouter:
- nombre: `akira-production`
- expiración: sin expiración
- credit limit: Custom amount = `0`
- reset: N/A
- BYOK usage incluido: off

El usuario confirmó que esta key es diferente de la key automática que apareció posteriormente en onboarding/workspace.

La key que interesa a Akira es la que el usuario colocó en Render bajo:

`OPENROUTER_API_KEY`

Nunca pedir ni imprimir la key.

Objetivo: usar OpenRouter exclusivamente como **fallback gratuito**.

Configuración de Akira:
`model = openrouter/free`

OpenRouter debe poder seleccionar un modelo gratuito disponible. La disponibilidad de modelos gratuitos puede cambiar.

Prueba controlada:
1. Se agregó temporalmente `AKIRA_FORCE_OPENROUTER_TEST=1`.
2. El modo estaba limitado al owner.
3. Se forzó exclusivamente OpenRouter.
4. Usuario envió: “Prueba de OpenRouter. Responde solamente: OPENROUTER OK”.
5. Akira respondió:
   **“Soy Akira V7.3. OPENROUTER OK (via openai/gpt-oss-120b)”**
6. Esto confirmó funcionalmente que la key configurada en Render puede hacer una petición mediante OpenRouter Free.
7. Después se eliminó el modo temporal.

Commit de prueba temporal:
`4c30ef530e9fb96868cb248a760dbdbbc88edf92`

Commit de limpieza:
`95c9f3e7f1d79d2ac3adcdb0422839a12bb41cc7`

Auditoría posterior a limpieza:
- `AKIRA_FORCE_OPENROUTER_TEST`: ausente.
- modo forzado: ausente.
- fallback normal Groq: presente.
- fallback normal OpenRouter: presente.
- rama Gemini: presente.

---

## 4. GEMINI — ERROR REAL ENCONTRADO Y APRENDIZAJE

Primera prueba de contexto:
- Akira recordó correctamente un nombre de proyecto dentro de la conversación.
- La respuesta apareció vía `openai/gpt-oss-120b`, mostrando que Gemini no estaba respondiendo y Groq estaba actuando como fallback.

Luego se revisaron Render Logs.

Primer error real:
`400 INVALID_ARGUMENT`
con mensaje equivalente a:
**“Manual set deadline 8s is too short. Minimum allowed deadline is 10s.”**

Causa:
- Google GenAI SDK no aceptaba el timeout manual de 8 segundos.
- Había dos usos en chat/stream.
- También existía lógica de planificación de misiones que necesitaba respetar el mínimo.

Corrección:
- chat Gemini: 10 s
- stream Gemini: 10 s
- planner Gemini: guard para respetar mínimo 10 s

Commit:
`1eb04da4911a90803b405febaf2e6c6e124d121c`

Auditoría:
- timeouts de chat: 10 s
- timeout de stream: 10 s
- timeout antiguo de 8 s: eliminado
- timeout antiguo de 7 s: eliminado
- diagnóstico del error: preservado

Segundo error real encontrado después:
`429 RESOURCE_EXHAUSTED`
con mensaje:
**“You exceeded your current quota”**

Conclusión:
- No era un error de API key.
- No era el timeout.
- Era cuota agotada de Gemini.

El usuario no quiere pagar, por lo que la estrategia correcta es fallback gratuito.

Corrección adicional:
- 429 de Gemini ya no se reintenta innecesariamente.
- chat: 429 → fallback inmediato.
- stream: 429 → fallback inmediato.
- planner: 429 → fallback inmediato.
- retry solo para códigos transitorios permitidos: 408, 500, 502, 503, 504.

Commit:
`6d982b2b616b47811fe4b1002a11aceb4198d03e`

Resultado:
- Akira siguió respondiendo vía Groq.
- Se redujo la latencia cuando Gemini está agotado.

---

## 5. COOLDOWN DE KEYS / FALLBACK

Se detectó otro problema conceptual:
- `_pick_gemini_keys()` podía devolver keys fallidas todavía dentro del periodo de cooldown.
- Eso hacía que Akira pudiera reintentar una key mala en lugar de avanzar.

Corrección:
```python
def _pick_gemini_keys():
    now = time.time()
    keys = get_gemini_keys()
    return [k for k in keys if _failed_keys_until.get(k, 0) < now]

def _pick_groq_keys():
    now = time.time()
    keys = get_groq_keys()
    return [k for k in keys if _failed_keys_until.get("groq:" + k, 0) < now]
```

El marcado de fallo usa provider explícito:
```python
_mark_key_failed(key, seconds=3600, provider="gemini")
_mark_key_failed(key, seconds=3600, provider="groq")
```

Esto evita mezclar cooldowns entre proveedores.

---

## 6. MODELOS GROQ

Se actualizaron los modelos activos de fallback Groq.

Lista actual:
```
[
  "openai/gpt-oss-120b",
  "openai/gpt-oss-20b",
  "qwen/qwen3.8-27b"
]
```

Se actualizaron tanto:
- chat Groq
- planner de misiones Groq

Commit relevante:
`7989fdcc561fad5d95cda663cd73d44a57c9f96c`

Auditoría confirmó que las listas antiguas de modelos Groq ya no se usan activamente.

Existe todavía una entrada histórica/deprecated de reemplazo para:
`llama2-70b-4096 → llama-3.3-70b-versatile`

No es una lista activa de fallback; solo es un mapping de reemplazo. No se ha considerado necesario eliminarla.

---

## 7. CONTEXTO REAL DE CONVERSACIÓN — BUG IMPORTANTE

Se encontró un bug conceptual importante:

Akira persistía los mensajes de conversación en la base de datos, pero al llamar al proveedor LLM no enviaba automáticamente el historial completo de la conversación.

Eso significaba que:
- la persistencia existía,
- pero el proveedor recibía principalmente el mensaje actual + memoria,
- y por tanto cambiar de proveedor no garantizaba continuidad real del chat.

Esto fue corregido.

Helper agregado:
```python
def _format_conversation_context(service, conversation_id, current_msg, limit=20, max_chars=18000):
    """Reconstruye contexto real de la conversación sin convertir el chat crudo en memoria."""
```

Características:
- lee mensajes persistidos;
- si el último mensaje user coincide con el mensaje actual, lo elimina para no duplicarlo;
- toma los últimos 20 mensajes;
- acepta solo roles user/assistant;
- limita cada contenido a 4000 caracteres;
- limita el bloque total a 18000 caracteres;
- separa historial real de memoria.

Formato:
```
[HISTORIAL REAL DE ESTA CONVERSACION]
Usuario: ...
Akira: ...
[FIN HISTORIAL]
```

Ese contexto se entrega a:
- Gemini
- Groq
- OpenRouter

Esto permite que el contexto pertenezca a **Akira**, no al proveedor.

Commit inicial:
`e73d0fdbaab14f9badd5d1db44ddbbc86eb27698`

Luego se detectó un error introducido durante la primera modificación:
- quedó un bloque duplicado/orphan.
- Se auditó estructuralmente.
- Se eliminó el bloque duplicado.

Commit de corrección:
`94dcf6dfe350e02f50544c975b10a052a0b59141`

Esto es aprendizaje importante:
**después de modificar código grande, no basta con revisar la zona editada; hay que auditar estructura y duplicados.**

---

## 8. PRUEBA REAL DE CONTEXTO

Se hizo una prueba real:

Mensaje:
**“Mi proyecto de prueba se llama Akira Contexto 2026. Recuérdalo durante esta conversación.”**

Después:
**“¿Cómo se llama el proyecto que te acabo de mencionar?”**

Akira respondió correctamente:
**“Akira Contexto 2026.”**

La respuesta apareció vía:
`openai/gpt-oss-120b`

Esto demostró simultáneamente:
- contexto persistido;
- contexto reconstruido;
- funcionamiento del fallback;
- continuidad aunque Gemini no respondiera.

---

## 9. FRONTEND — CONTEXTO Y CHAT

`js/akira_brain.js`:
- usa headers de sesión;
- envía `conversation_id`;
- recibe `conversation_id`;
- aplica la persistencia server-side.

Fase 10.7.2:
- conversación persistida mediante `conversation_id`.

Fase 11.0:
- guardado bruto de chat como memoria fue desactivado.
- cinco llamadas `saveNeuronaHibrida` fueron comentadas porque estaban llenando DB con ruido y violando P1.
- Reactivar solo cuando exista extractor real.

No volver a llenar memoria con cada mensaje bruto sin un extractor/criterio adecuado.

---

## 10. MISIONES — ARQUITECTURA ACTUAL

Endpoints:
- GET `/api/v8/missions`
- GET `/api/v8/missions/{mission_id}`
- GET `/api/v8/missions/{mission_id}/progress`
- POST `/api/v8/missions/{mission_id}/approve`
- POST `/api/v8/missions/{mission_id}/reject`
- POST `/api/v8/missions/{mission_id}/execute`
- POST `/api/v8/missions/{mission_id}/cancel`
- GET `/api/v8/missions/recent`
- GET `/api/v8/missions/selftest`
- GET `/api/v8/missions/{mission_id}/diagnose`
- GET `/api/v8/tasks?mission_id=...`

Estados:
```
created
planning
waiting_approval
running
paused
completed
failed
cancelled
```

Transiciones:
```
created -> planning | cancelled
planning -> waiting_approval | failed | cancelled
waiting_approval -> running | cancelled
running -> completed | failed | paused
paused -> running | cancelled | failed
completed -> terminal
failed -> terminal
cancelled -> terminal
```

Flujo esperado:
**Crear → Aprobar → Ejecutar → Ver progreso → completed/failed**

---

## 11. MISIONES — PLANIFICACIÓN Y TIMEOUTS

Se implementó runtime de planificación efímero:
```
_mission_planning_runtime = {}
_mission_planning_runtime_lock = threading.Lock()
```

Stages:
- mission_created
- transitioning_to_planning
- llm_planning_started
- planning_failed
- saving_plan
- transitioning_to_waiting_approval
- planning_completed

Helpers:
- `_set_mission_planning_runtime`
- `_get_mission_planning_runtime`
- `_clear_mission_planning_runtime`

Planner Gemini dedicado:
- usa `google.genai`
- `HttpOptions(timeout=...)`
- modelo `gemini-3.8-flash`
- JSON response MIME
- temperatura 0.1
- máximo aproximado 1600 tokens

Planner tiene deadline global:
`MISSION_PLAN_TIMEOUT_S`

Groq planner:
- respeta deadline global.
- cada request calcula tiempo restante.
- máximo aproximado por request: 8 s, pero respetando límites mínimos del SDK cuando corresponde.

Diagnóstico de misión:
- devuelve `planning_runtime`
- calcula `planning_stale`
- stale cuando age >= `MISSION_PLAN_TIMEOUT_S`

Esto se hizo porque se detectó un riesgo real:
- Groq había sido endurecido,
- pero Gemini podía quedar colgado en `planning`,
- y el frontend no ofrecía diagnóstico mientras estaba en `planning`.

---

## 12. MISIONES — BUG AÚN PENDIENTE

Se detectó una vulnerabilidad lógica en validación del plan:

`_build_mission_plan_prompt` lista herramientas/agentes y el validador vuelve a consultarlos.

Pero:
**`receives_from` depende de pasos que ya hayan aparecido en el orden de la lista.**

Si el LLM genera los steps fuera del orden esperado, una referencia válida puede ser rechazada.

Esto todavía NO está corregido.

Es el siguiente candidato técnico importante en Misiones.

Antes de modificar:
1. inspeccionar implementación exacta de `_validate_mission_plan`;
2. diseñar validación independiente del orden;
3. auditar efectos sobre dependencias reales;
4. implementar;
5. volver a auditar;
6. probar con plan ordenado y plan desordenado.

No asumir que el LLM siempre devuelve steps en orden.

---

## 13. MISIONES — PRUEBA EXITOSA REAL

Se validó una misión real:

**“Verificar el funcionamiento completo del sistema de misiones de Akira, desde la creación hasta la ejecución y finalización.”**

Resultado:
- 6 tareas
- 100%
- completed

Esto valida el camino feliz completo.

Pero todavía falta probar robustez ante:
- planificación fallida;
- rechazo;
- ejecución fallida;
- timeout/stale;
- dependencias en orden no convencional;
- respuestas de proveedor degradadas.

---

## 14. MISIONES — TIMEOUTS ACTUALES

Constantes relevantes:
- `MISSION_TASK_TIMEOUT_S = 60`
- `MISSION_COGNITIVE_TIMEOUT_S = 180`
- `MISSION_MAX_DURATION_S = 480`

---

## 15. FRONTEND — PANEL DE MISIONES

Archivo:
`js/akira_missions_panel.js`

Versionado/cache:
- V4 actualmente.

Cambios importantes:
- acciones de misión mejoradas;
- errores visibles;
- handlers delegados inicialmente;
- luego handlers directos en botones renderizados;
- cache busting;
- overlay de progreso corregido;
- diagnóstico de planificación;
- polling durante `running` y `planning`.

Commit frontend relevantes:
- `4105faafad34a40f5c104fe552dee6692a6a6b87` — Fix mission actions and improve mission panel errors
- `04bf7c9ab091e6ecf5cb94f556ccb35c22ecc407` — Bump mission panel cache version
- `66fa4ac21ae73b7c9bcc3cc55a298ecbe8b984cf` — Use delegated mission action handlers
- `cff00d10e854f111b274d853b93f640b6fa124c7` — Bind mission actions directly to rendered buttons
- `c976491b56f4d09b426976bcd4b0e82cb7e29394` — Bump mission panel cache version to v3
- `ac2b50eaca16e276ee75b1b7cabc22f135f4d2f1` — Fix mission progress overlay blocking buttons
- `245e34b87bdf811b274d853b93f640b6fa124c7` — Improve mission planning diagnostics and polling
- `2973ba4d2295e7d5432606bc98ead6ac7ff9a0a7` — mission module cache v3 → v4

---

## 16. BUG FRONTEND REAL: BOTÓN APROBAR

Se encontró que el botón Aprobar parecía no responder.

La causa no era inicialmente el handler:
el overlay/caja de progreso estaba interfiriendo con la interacción.

CSS corregido:
```css
.mission-progress-box{
  border:3px solid var(--border);
  background:#09090c;
  margin:12px 0;
  padding:10px;
  position:relative;
  overflow:hidden
}
.mission-progress-box .mission-progress-label{
  position:static;
  inset:auto;
  min-height:22px;
  display:flex;
  align-items:center;
  justify-content:space-between
}
.mission-progress-track{
  height:18px;
  background:#0e0e12;
  border:3px solid var(--border);
  margin-top:8px;
  position:relative;
  overflow:hidden
}
.mission-progress-fill{
  height:100%;
  width:0;
  background:linear-gradient(90deg,var(--accent),var(--sky));
  transition:width .25s ease
}
```

Aprendizaje:
**un botón que “no responde” puede ser un problema de capas/CSS/overlay, no necesariamente JavaScript.**

---

## 17. AUTH

En `index.html`:

```js
if(!localStorage.getItem("akira_backend_url"))
  localStorage.setItem("akira_backend_url","https://akira-empresa.onrender.com");

function akiraAuthHeaders(){
  const h={'Content-Type':'application/json'};
  try{
    const t=localStorage.getItem('akira_session_token');
    const exp=parseInt(localStorage.getItem('akira_session_exp')||'0',10);
    if(t && exp>Math.floor(Date.now()/1000))
      h['Authorization']='Bearer '+t;
  }catch(e){}
  return h;
}
window.akiraAuthHeaders=akiraAuthHeaders;
```

No modificar auth sin auditar todas las rutas que dependan de ella.

---

## 18. PROVIDER KEY LOADERS

Gemini:
- `GEMINI_API_KEY`
- puede contener múltiples keys separadas por coma.
- también:
  - `GEMINI_API_KEY_2` ... `GEMINI_API_KEY_5`
  - compatibilidad con `GEMINI_API_KEY2` ... `GEMINI_API_KEY5`

Groq:
- `GROQ_API_KEY`
- `GROQ_API_KEY_2` ... `GROQ_API_KEY_5`

Las keys se deduplican.

No imprimir secrets en logs.

---

## 19. REQUIREMENTS

Actualmente incluye, entre otros:
- fastapi
- uvicorn[standard]
- python-dotenv
- google-genai>=0.3.0
- google-auth
- google-auth-oauthlib
- requests
- boto3>=1.34.0
- numpy
- sse-starlette
- PyMuPDF
- python-multipart
- Pillow
- imageio
- psycopg[binary,pool]>=3.2

---

## 20. HISTORIAL RECIENTE BACKEND

Orden de commits relevantes recientes:

`95c9f3e7f1d79d2ac3adcdb0422839a12bb41cc7`
Retira modo temporal de prueba de OpenRouter.

`4c30ef530e9fb96868cb248a760dbdbbc88edf92`
Añade modo temporal owner-only para probar OpenRouter Free.

`6d982b2b616b47811fe4b1002a11aceb4198d03e`
Optimiza fallback ante 429 de Gemini; evita retries innecesarios.

`1eb04da4911a90803b405febaf2e6c6e124d121c`
Corrige timeout mínimo del SDK Gemini de 8 s a 10 s.

`b3f6961fc76d060700e7b173f7c3d0b18012bf10`
Cambio previo relevante del historial reciente.

`7989fdcc561fad5d95cda663cd73d44a57c9f96c`
Actualiza modelos Groq de fallback y planner.

`06d1fc2baa67cd1a39f445cd0068032628d4aba6`
Endurece cooldowns de providers y timeouts de Gemini.

`94dcf6dfe350e02f50544c975b10a052a0b59141`
Elimina bloque duplicado y consolida cambio de contexto/OpenRouter.

`e73d0fdbaab14f9badd5d1db44ddbbc86eb27698`
Añade contexto real de conversación y fallback OpenRouter.

Otros commits de misiones importantes:
- `87fd90689bf0165c72527ed9580b421197243930`
- `854d9d426d8b4e0503662a083c2bbfaffdc4ce19`
- `dc813b4767fbd465f1136d00bf3ea712c664e1ef`
- `c525352ff6b6546e1c77235bf96cea7866887daf`
- `65afd2145d44cc079aa31fb221790fb943146f7e`

---

## 21. FRONTEND INDEX

Último SHA conocido previo a los últimos cambios:
`411dad28cfc0ae721e8f2f72ed7ae551190ed06`

No tocar `akira_admin.js` estable sin necesidad.

---

## 22. PRÓXIMO PASO RECOMENDADO

Antes de seguir agregando funciones:

### Fase siguiente: auditoría profunda de Misiones

Primero revisar:
1. `_validate_mission_plan`
2. tratamiento de `receives_from`
3. dependencia del orden de steps
4. comportamiento con DAG/dependencias no lineales
5. validación de agentes/tools
6. estados imposibles
7. idempotencia de approve/reject/execute/cancel
8. comportamiento ante doble ejecución
9. timeout y stale planning
10. errores de proveedor durante planning

Después:
- corregir solo lo necesario;
- auditar;
- probar casos felices y casos de fallo;
- dejar evidencia del resultado.

---

## 23. NO HACER TODAVÍA

No:
- añadir nuevas features grandes al chat;
- volver a activar guardado bruto de chat como memoria;
- agregar pagos/OpenRouter credits;
- pedir al usuario API keys;
- tocar auth sin necesidad;
- tocar `akira_admin.js` estable;
- eliminar el fallback OpenRouter porque sea gratuito;
- asumir que Gemini volverá a tener cuota;
- asumir que el orden de steps generado por un LLM siempre será correcto.

---

## 24. ERRORES Y APRENDIZAJES QUE NO DEBEN PERDERSE

1. **Gemini 8 s era inválido**: el SDK exige mínimo 10 s en este caso.
2. **429 de Gemini es cuota agotada**, no timeout.
3. **No conviene reintentar 429**: debe avanzar inmediatamente al fallback.
4. **Cooldown debe ser por provider + key**, no una marca ambigua.
5. **Persistir historial no equivale a enviarlo al LLM**. Hay que reconstruir y pasar contexto real.
6. **Una primera modificación puede dejar bloques duplicados**. Siempre auditar estructura después.
7. **Un botón que no funciona puede estar bloqueado por CSS/overlay**, no solo por JS.
8. **No basta con probar el happy path de Misiones**.
9. **Los LLM pueden devolver steps en orden diferente**. La validación no debe depender accidentalmente del orden si la semántica permite dependencias no lineales.
10. **OpenRouter Free sí funcionó en una prueba real**, sin tarjeta ni pago.
11. **Los modos de diagnóstico temporales deben retirarse después de validar**, para no dejar switches de producción innecesarios.
12. **No exponer secretos en logs, código, capturas ni handoffs.**

---

## 25. CRITERIO DE CIERRE

Una tarea de Akira solo se considera cerrada cuando:
- se entiende el problema;
- se identifica la causa;
- se modifica lo necesario;
- se vuelve a auditar el código;
- se verifica que no quedó una regresión;
- se prueba el comportamiento real cuando es posible;
- y queda documentado el resultado.

Fin del handoff maestro.
