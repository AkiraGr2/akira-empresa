# F15 — Contrato propuesto para Hive Collective Sync y Local Agent

**Fecha:** 2026-10-09 (COT)  
**Estado:** borrador de diseño; NO es contrato canónico aprobado ni implementación.  
**Rama:** `akira/f15-hive-share-gate-20261009`  
**Relacionado:** [PR backend #137](https://github.com/AkiraGr2/akira-empresa/pull/137), [PR frontend #89](https://github.com/AkiraGr2/akira-v3-frontend/pull/89).

## 1. Por qué existe este documento

El Handoff Maestro y el Pasaporte recuperados fijan el objetivo de Hive:

`PRIVATE → SHAREABLE autorizado → COLLECTIVE`

con sincronización, resolución de conflictos, procedencia y privacidad. También establecen que Office muestra estados reales y que Local Agent es un componente local previsto para filesystem, terminal, browser, código y aplicaciones cuando exista una máquina disponible.

Las fuentes encontradas NO definen de forma versionada el protocolo de pares, la identidad de una colectiva, las semánticas de revocación remota, el algoritmo de conflictos ni el contrato de emparejamiento del agente local. Por eso este documento separa los principios canónicos recuperados de decisiones técnicas propuestas. No se crearán migraciones, endpoints de federación ni ejecución local a partir de este borrador por sí solo.

## 2. Estado vivo antes de diseñar la unidad siguiente

- La primera unidad Hive Share Gate tiene guardias de propietario, transiciones explícitas de privacidad, versión optimista, procedencia/evidencia, auditoría transaccional y vista exportable limitada al owner scope autenticado.
- El cambio material de una ficha compartida ahora revoca su consentimiento en la misma actualización, la devuelve a `PRIVATE` y a `partially_verified`; re-verificarla no la vuelve a publicar. Archivar/reactivar tampoco recupera la autorización anterior.
- Las pruebas del backend y PostgreSQL aprobaron en el SHA `1dd9d2dfd1b720e62910cde8c0d8c7ff25751505`; el frontend aprobó sintaxis, Browser E2E y Pixel Office E2E en `bb40bbceb331101a3baa2a73b4c641a32d054acb`.
- Los cambios continúan en PR Draft; no se han desplegado. La producción no dispone aún de una capacidad Hive registrada, lo esperado antes de integrar.
- La primera unidad NO implementa sincronización entre propietarios, promoción colectiva, resolución distribuida de conflictos ni un Local Agent ejecutable.

## 3. Principios de seguridad que deben conservarse

1. `PRIVATE` y `SENSITIVE` nunca se envían a un par. El consentimiento debe estar ligado a una revisión/version exacta del contenido, no solamente al ID del registro.
2. `SHAREABLE` solo permite entrar en un flujo de exportación futura aprobado. No implica que ya se haya transmitido o que todo miembro de la colectiva pueda leerlo.
3. Un par y su pertenencia a una colectiva deben probarse mediante identidad verificable y claves; no se confía en `owner_scope`, `peer_id` ni `is_owner` proporcionados por el cliente.
4. Cada entrega debe ser versionada e idempotente, conservar procedencia, hash del contenido y recibo de consentimiento. Los reintentos no deben crear versiones duplicadas.
5. Los conflictos factuales no se resuelven silenciosamente con last-write-wins. Se conservan las ramas competidoras, se registra el conflicto y se requiere una regla explícita para resolverlo.
6. Revocar detiene nuevas entregas y genera un evento/tombstone verificable. No se promete borrar copias ya exportadas fuera del control de Akira; esa limitación debe quedar visible.
7. Un Local Agent debe ser un proceso instalado y emparejado en una máquina controlada por el usuario, separado de la web estática. El agente no hereda privilegios por aparecer conectado.
8. El agente solo expone capacidades granulares autorizadas. Escrituras de filesystem, ejecución de comandos, cambios de código o acciones externas requieren scopes, límites, auditoría y aprobación humana cuando el efecto sea irreversible.
9. Si faltan claves, membresía, persistencia, confirmación o prueba de estado, la operación falla cerrada. Office informa `no disponible` / `sin verificar`; no infiere éxito de animaciones ni de declaraciones.
10. El contenido recibido de pares es dato externo sin autoridad automática sobre la identidad, permisos, políticas o instrucciones del sistema local.

## 4. Propuesta de flujo de datos — pendiente de aprobación técnica

### Publicación / transferencia

`Knowledge origen` → evaluación de elegibilidad → revisión sanitizada → consentimiento explícito por versión/hash → envelope firmado → outbox durable → entrega a par aprobado → recibo idempotente → inbox local → validación de firma, consentimiento y procedencia → revisión de conflicto → aceptación local explícita → conocimiento colectivo elegible.

No se propone que el backend copie una fila de `knowledge_records` directamente entre owner scopes. El payload sincronizable debe ser un snapshot aprobado y limitado al contrato; no incluye sesiones, tokens, owner scope privado ni metadatos internos no autorizados.

### Envelope mínimo propuesto

- Versión de contrato y tipo de evento.
- Identificadores idempotentes de evento, colectiva y par.
- Identidad/clave pública verificable del emisor.
- Identificador de revisión, hash del contenido y revisión base.
- Snapshot permitido del conocimiento, clasificación de privacidad y estado de verificación.
- Evidencia y referencia de procedencia, manteniendo su relación con el snapshot.
- Prueba/recibo de consentimiento para el hash exportado.
- Fecha, firma y metadatos de entrega necesarios para auditoría.

La lista definitiva de campos debe reconciliarse con el schema real antes de implementarse.

### Conflictos

- Si el par recibió una revisión basada en una base distinta de la revisión local, no se sobreescribe automáticamente.
- Se registra un conflicto con ambos hashes/revisiones y su procedencia.
- La resolución produce una revisión nueva con vínculo a las revisiones que la originaron; no se altera el historial anterior.
- Las estrategias automáticas solo se habilitan más adelante para tipos de dato cuyo merge tenga semántica formal y pruebas. Knowledge factual queda en revisión explícita hasta entonces.

### Revocación

- Revocar una revisión compartible cancela nuevas entregas pendientes y genera un evento duradero de revocación.
- Un par debe poder deduplicar y aplicar dicho evento aunque reciba reintentos o mensajes fuera de orden.
- La revocación no afirma que se recuperaron o borraron copias externas anteriores; cualquier remoción remota será un protocolo separado con recibos comprobables.

## 5. Persistencia propuesta — no migrar todavía

El diseño probablemente necesitará modelos durables equivalentes a:

- registro de pares y estado de confianza/clave;
- colectivas y membresías aprobadas;
- outbox de entrega y recibos;
- inbox idempotente;
- revisiones/conflictos y decisiones de resolución;
- eventos de revocación/tombstones.

Son entidades conceptuales, no nombres ni schemas aprobados. Antes de crear tablas hay que revisar migraciones actuales, idempotencia, política de retención, índices, límites de tamaño y ownership. No se debe ampliar la exposición de `knowledge_records` para simular una red colectiva.

## 6. Contrato propuesto para Local Agent

- El proceso local demuestra identidad del dispositivo y se empareja mediante un flujo de un solo uso que no expone credenciales de larga duración en el navegador.
- Los tokens del agente tienen duración corta y scopes limitados por dispositivo, capacidad y contexto.
- Filesystem restringido a rutas autorizadas; denegación por defecto de rutas sensibles y traversal.
- Terminal y código ejecutados en sandbox, con límites de tiempo, recursos, directorio de trabajo, red y comandos.
- Browser y aplicaciones locales se presentan como capacidades separadas con permisos explícitos, no como un canal genérico de ejecución.
- Cada acción registra actor, dispositivo, scope, argumentos redactados, aprobación, resultado, error y verificación posterior.
- La desconexión o pérdida de salud desactiva las ejecuciones nuevas; no se ejecutan colas pendientes con permisos obsoletos.
- Las acciones irreversibles requieren aprobación humana. El agente no decide por sí solo elevar privilegios.

La disponibilidad solo se declara tras emparejamiento, prueba de desafío firmado, heartbeat reciente, capacidades conocidas y una prueba funcional reproducible. Hasta entonces: Local Agent `no disponible / no verificado`.

## 7. Office: estados que debe representar

- Consentimiento de publicación y revisión/hash aprobados.
- Estado de outbox: pendiente, entregado, confirmado o fallido, a partir de persistencia real.
- Última sincronización confirmada diferenciada de un simple intento.
- Conflictos pendientes, revisiones competidoras y decisión adoptada.
- Estado de revocación y límite de control sobre copias externas.
- Par/Local Agent presente solo a partir de identidad comprobada y heartbeat válido.
- Cada control de escritura se desactiva si la capacidad correspondiente no está disponible, no tiene autorización o no posee evidencia actual.

No reutilizar indicadores genéricos de “Hive activa” para representar estados diferentes.

## 8. Pruebas de aceptación que necesitará la siguiente unidad

1. Dos pares sintéticos aislados en PostgreSQL desechable: transferencia autorizada e importación con relectura desde una conexión nueva.
2. Reintento del mismo evento: no duplica filas, versiones, recibos ni auditoría.
3. Contenido `PRIVATE`/`SENSITIVE`, consentimiento ausente o hash diferente: rechazo verificable y sin mutación.
4. Pares no miembros, claves inválidas, firma inválida, token caducado y scope ajeno: denegación sin filtrar si existe la fila ajena.
5. Dos revisiones concurrentes sobre una misma base: conflicto persistido; ninguna sobrescritura silenciosa.
6. Revocación antes/después de entrega, eventos duplicados y mensajes fuera de orden: estado determinista y sin nuevas exportaciones tras aplicar la revocación.
7. Reinicio entre crear outbox y entregar: recuperación durable e idempotente.
8. Local Agent: desafío firmado, scopes, caducidad, permiso de ruta, traversal, comandos no permitidos, aprobación humana, timeout y desconexión.
9. Office: los estados y contadores coinciden con las respuestas/persistencia reales; fallo del backend no finge éxito.
10. CI gratuito, sin credenciales de producción, sin llamadas a modelos de pago y sin side effects fuera de fixtures.

## 9. Decisiones aún no definidas por las fuentes canónicas encontradas

Antes de declarar terminada Hive colectiva, la arquitectura debe fijar explícitamente:

- qué es una “colectiva” y quién puede ser miembro;
- si los pares son instancias del mismo propietario, instalaciones distintas o propietarios diferentes;
- quién firma y administra las claves de identidad;
- quién puede aceptar contenido entrante y cuándo un conocimiento pasa a `COLLECTIVE`;
- qué garantía de revocación se exige a pares externos;
- qué clases de Knowledge permiten merge automático y cuáles requieren revisión;
- plataformas/entorno soportados por Local Agent y límite de sus permisos.

Las decisiones iniciales seguras propuestas son: membresía por invitación y aceptación explícita, rechazo por defecto, contenido recibido sin autoridad, sin merge automático de hechos, revocación como bloqueo durable de futuras entregas y Local Agent apagado hasta emparejamiento verificable.

## 10. Orden de ejecución después de la primera unidad

1. Revisar/aprobar el contrato de colectiva, pares, revisión y revocación.
2. Modelar schemas/migraciones aditivas y contratos de servicio antes de endpoints.
3. Implementar outbox/inbox y recibos idempotentes con dos pares sintéticos.
4. Implementar flujo explícito de conflicto/revisión y revocación.
5. Definir y probar el emparejamiento/scopes del Local Agent separado del backend web.
6. Integrar estados reales en Office.
7. Ejecutar CI, revisión de seguridad, aprobación y despliegue backend primero; comprobar runtime, lecturas desde conexión nueva y logs/auditoría.
8. Desplegar frontend solo después de verificar el contrato backend productivo.
9. Conservar evidencia, ejecutar auditoría integral cross-system tras F15 y cerrar únicamente los criterios demostrados.

**Estado de este borrador:** diseño propuesto y lista de pruebas preparada. No se han añadido entidades de colectiva, endpoints de sincronización, credenciales de pares ni ejecución de agente local. No implica que Hive colectiva o Local Agent estén implementados.
