# F15 — Hive Collective Sync Protocol v1 (propuesta de contrato)

**Fecha:** 2026-10-09 (COT)  
**Estado:** propuesta técnica para revisión; NO aprobada como contrato canónico y NO implementada.  
**Rama:** `akira/f15-hive-sync-contract-v1-20261009`  
**Dependencias:** backend PR [#137](https://github.com/AkiraGr2/akira-empresa/pull/137), frontend PR [#89](https://github.com/AkiraGr2/akira-v3-frontend/pull/89), borrador de diseño [Hive Collective Sync + Local Agent](https://github.com/AkiraGr2/akira-empresa/blob/akira/f15-hive-share-gate-20261009/docs/F15_HIVE_COLLECTIVE_SYNC_LOCAL_AGENT_DESIGN_DRAFT_2026-10-09.md).

> Este documento convierte huecos del diseño en decisiones propuestas que puedan revisarse y aprobarse. Los términos MUST/SHOULD describen el contrato candidato; no son una afirmación de que el runtime actual los cumpla. No se añaden tablas, endpoints, claves, sincronización ni ejecución local en este cambio documental.

## 1. Objetivo y límites

Definir el contrato mínimo seguro para que propietarios autorizados compartan snapshots de Knowledge con una colectiva, reciban contenido para revisión, conserven historial y procesen conflictos y revocaciones de forma reproducible.

La secuencia de producto se mantiene: conocimiento privado → autorización explícita para compartir → relación de conocimiento aceptada en una colectiva. El protocolo NO convierte todo dato elegible en dato transmitido, NO confunde «entregado» con «aceptado» y NO permite que el contenido recibido otorgue autoridad automáticamente.

**En alcance de este contrato:** identidades de propietarios y dispositivos, membresía de colectivas, consentimiento ligado a un snapshot, envelopes firmados, entrega durable e idempotente, inbox, aceptación humana, conflictos factuales y revocaciones.

**Fuera de alcance:** Local Agent ejecutable, ejecución de comandos, propagación automática a colectivas distintas, merge automático de hechos, borrado garantizado de copias externas, compatibilidad retroactiva con clientes que ignoren este contrato y activación de producción.

## 2. Modelo de identidad y autorización

### 2.0 Topología elegida para la propuesta v1

La propuesta v1 es **mediada por el backend**: el servicio autentica la acción de origen, valida membresías, crea envelopes, administra outbox/inbox y registra recibos. No hay conexión directa browser-a-browser ni peer-to-peer, y no se acepta un envelope arbitrario a través de una ruta pública. La entrega se procesa a través de servicios internos confiables y persistencia durable.

En este contrato, «par» significa otro owner autenticado miembro de la colectiva, no una instalación local. La identidad de dispositivo, pairing y claves de Local Agent son otro contrato. Si en el futuro se requiere transferencia directa entre instancias, será una versión/capacidad distinta, no un cambio implícito de transporte dentro de v1.

### 2.1 Principales, colectivas y membresía

- **Owner principal:** identidad autenticada por el mecanismo de sesión del backend. El servidor deriva al owner desde la sesión; nunca acepta `owner_scope`, `owner_id`, `is_owner` ni roles del JSON como autoridad.
- **Collective:** espacio de intercambio identificado por UUID, con owner creador y política de membresía.
- **Miembro:** owner principal que aceptó explícitamente una invitación y tiene membresía activa. Las sesiones o dispositivos de ese owner no son miembros adicionales.
- **Peer receptor:** destino autorizado por una membresía concreta. `collective_id` no es una credencial ni concede acceso por sí solo.

La membresía es **por invitación, con aceptación explícita y caducidad**. Un token de invitación debe tener entropía criptográfica, almacenarse como hash, ser de un solo uso, estar ligado a la colectiva y al destinatario previsto cuando aplique, y expirar. Invitar no equivale a activar. Estados propuestos: `INVITED`, `ACTIVE`, `SUSPENDED`, `REVOKED`, con transiciones auditadas. `REVOKED` no vuelve a `ACTIVE` por reintento; se requiere una invitación nueva.

Toda escritura comprueba sesión, ownership y membresía vigente en el servidor. Para recursos ajenos se usan respuestas opacas, sin confirmar si existen. Una baja o suspensión de membresía bloquea nuevas publicaciones y recepciones/aceptaciones según el contrato; no se puede eludir pasando otro `owner_scope` o un ID de cuenta en el cuerpo.

### 2.2 Firma del servicio y canonicalización

Como v1 es mediada por el backend, **el servicio firma los envelopes de distribución**; no se exige que el navegador o Local Agent firme los eventos de colectiva. El backend solo genera un envelope después de validar la sesión, el consentimiento registrado y las membresías. La firma del servicio protege la integridad y el emisor técnico del envelope; no sustituye el consentimiento humano ni, por sí sola, prueba que el owner lo aprobó.

Contrato criptográfico candidato:

- JSON canónico conforme a RFC 8785 (JCS); hash del snapshot: `SHA-256(JCS(snapshot))`.
- El campo `canonicalization` MUST usar exactamente el literal `RFC8785`; ausencia, alias o una versión desconocida hacen que el envelope se rechace (sin negociación implícita del serializador).
- Firma Ed25519 del envelope sin el campo `signature`: el mensaje firmado son los bytes UTF-8 de `AKIRA-HIVE-SYNC-V1\n` seguidos de `JCS(envelope_without_signature)`. El campo `signature` codifica los 64 bytes de firma en Base64url sin padding.
- Cada firma incluye `service_key_id`; el backend receptor valida firma, algoritmo y estado de la clave antes de aplicar el evento.
- La clave privada del servicio debe estar protegida en un mecanismo operativo aprobado (por ejemplo, gestor de claves/secretos con rotación y acceso restringido). No se hardcodean claves ni se almacenan en frontend o en Knowledge.
- La acción del owner se acredita mediante consentimiento persistido y auditoría transaccional. La firma del servicio no se usa como sustituto de esa fila.

Este algoritmo es una **propuesta**, no una implementación verificada ni conectada al runtime. `main` no declara explícitamente dependencias dedicadas para Ed25519/JCS; el PR separado [#139](https://github.com/AkiraGr2/akira-empresa/pull/139) las fija (`cryptography==50.0.2`, `rfc8785==0.1.4`) y añade primitivas/tests sin endpoints ni llamadas desde el runtime. En el SHA `d6f1c6e8aa204ab8be644f71d84eb4d6fb2ec626`, las 35 pruebas unitarias del contrato criptográfico y la suite de sintaxis pasaron en [Backend syntax verification](https://github.com/AkiraGr2/akira-empresa/actions/runs/37979419578); la verificación PostgreSQL E2E independiente también pasó en [F12 free PostgreSQL end-to-end verification](https://github.com/AkiraGr2/akira-empresa/actions/runs/37979419587). Esto verifica suites automatizadas, no una transferencia real. **Riesgo de dependencia pendiente:** PyPI clasifica `rfc8785==0.1.4` como *Beta* y su publicación figura el 2024-09-27 ([metadatos de PyPI](https://pypi.org/project/rfc8785/0.1.4/)); el pin es provisional y exige revisión independiente de interoperabilidad/vectores frente a otra implementación conforme antes de integrar o habilitar el protocolo. Sigue sin demostrarse que Render tenga una clave de firma gestionada/configurada. Los gates son: revisar/aprobar el contrato, validar interoperabilidad y vectores, resolver key management y solo después diseñar la integración. Si el despliegue no puede proteger/rotar la clave, la sincronización no se habilita.

El contrato no registra claves de dispositivos ni crea pairing. Local Agent deberá disponer de identidad, desafío firmado y permisos propios en su ciclo separado.

## 3. Privacidad, consentimiento y semántica de «COLLECTIVE»

La secuencia de producto continúa siendo: conocimiento privado → autorización explícita para compartir → relación de conocimiento aceptada en una colectiva. No se debe convertir una marca de privacidad en prueba de transporte, membresía o aceptación.

**Compatibilidad comprobada:** la migración existente `049_knowledge_first_class_and_graph_fk` permite el literal `COLLECTIVE` en el CHECK de `knowledge_records.privacy_level`; aun así, el servicio de Share Gate rechaza la transición a `COLLECTIVE` con `collective_sync_not_configured`. El valor existente no crea una colectiva, una membresía, consentimiento, un inbox ni una entrega. Esta propuesta no modifica ese CHECK ni propone establecer `privacy_level='COLLECTIVE'` como atajo: la relación de distribución debe tener su propio estado durable y explícito. La compatibilidad completa exige revisar los lectores/escritores de ese campo antes de cualquier implementación.

- `PRIVATE` y `SENSITIVE` son inexportables.
- `SHAREABLE` hace que un snapshot pueda considerarse para publicar, pero no autoriza por sí solo una transferencia.
- La relación con una colectiva y el estado de distribución se modelan por separado. Office puede presentar el estado de relación **COLLECTIVE** solo cuando el snapshot fue aceptado y la relación activa sigue vigente.
- El registro fuente conserva el significado de privacidad del conocimiento; una relación colectiva activa no es un permiso implícito para redistribuir. El receptor que acepta un snapshot crea una relación/proyección local con procedencia; una copia recibida no se reexporta sin revisión y consentimiento propios.
- Cada consentimiento incluye como mínimo owner actor derivado de sesión, colectiva destino, ID de Knowledge, versión, hash del snapshot exportable, versión del contrato, política de redacción, timestamp, generación de revocación y conjunto exacto de membresías destinatarias activas (o su hash determinista). El consentimiento se limita a esa revisión y audiencia; no se reutiliza para otro hash, colectiva o conjunto de destinatarios.
- Antes de confirmar, el servidor calcula la audiencia. Una nueva membresía no recibe retroactivamente publicaciones anteriores. Para sumar destinatarios, hace falta nuevo consentimiento explícito sobre la audiencia actual.
- Un cambio material invalida el consentimiento anterior. Re-publicar exige versión nueva, verificación fresca y confirmación nueva. Re-verificar no habilita envío automáticamente.
- El snapshot exportable es una proyección por lista positiva; no incluye sesiones, tokens, owner scope privado, prompts/contexto interno, datos de otros owners ni metadatos que no hagan falta para la procedencia.

## 4. Envelope del protocolo

Cada entrega destinada a un miembro es un envelope de servicio con mínimo:

- `protocol_version` literal `hive-sync/1` y `event_type`;
- `publication_id` para agrupar los envíos de una publicación y `event_id` UUID canónico (minúsculas, formato estándar) único para esa entrega a un destinatario;
- `collective_id` UUID canónico, referencia opaca estable del owner emisor, `recipient_membership_id` como UUID canónico de la membresía autorizada, generación de membresía y `sender_sequence` monotónica por colectiva/owner;
- `knowledge_lineage_id`, `revision_id`, revisión(es) padre y `content_hash`;
- snapshot mínimo sanitizado, clasificación de privacidad y estado de verificación de ese snapshot;
- procedencia/evidencia asociada al mismo hash, en la proyección permitida;
- ID del consentimiento y resumen determinista de la audiencia que se autorizó;
- timestamp del servicio para auditoría; no es una autoridad para ordenar hechos;
- `service_key_id`, firma Ed25519 y la versión de canonicalización.

El payload `signature` queda fuera de `envelope_without_signature`; la firma cubre el resto de los campos, incluido `content_hash`, destinatario y consentimiento. Los tipos iniciales permitidos son `KNOWLEDGE_SNAPSHOT` y `KNOWLEDGE_REVOCATION`. Los eventos se crean/aplican por servicios internos; no existe endpoint público para que un cliente se atribuya un emisor o inyecte eventos firmados.

La lista definitiva de campos de evidencia/procedencia debe cotejarse contra el schema real antes de codificarse. El esquema no autoriza a filtrar evidencia privada por conveniencia de serialización. Como propuesta inicial, el snapshot de primer nivel queda limitado a `concept`, `content`, `domain`, `source`, `source_reference`, `confidence`, `evidence` y `tags`; `source_id` y `related_nodes` quedan fuera por defecto porque pueden exponer IDs internos o estructura privada del grafo. Solo se podrían incluir referencias transformadas y opacas si el contrato de publicación las permite explícitamente. Tampoco se incluyen `id`, `owner_scope`, `created_by`, `status`, `version`, `last_verified_at`, `verified_by`, `idempotency_key` ni timestamps internos. Las claves privadas/de ejecución (por ejemplo `owner_scope`, `access_token`, `refresh_token`, `authorization`, `headers`, `session`, `private_key`, `api_key`, `password`, `secret`) se rechazan también en mapas anidados. El PR aislado [#139](https://github.com/AkiraGr2/akira-empresa/pull/139) implementa este rechazo dentro de la primitiva; la proyección por lista positiva y la validación de procedencia/evidencia siguen siendo responsabilidad del servicio futuro y la lista debe revisarse con el contrato antes de integrar.

## 5. Idempotencia, orden y entrega durable

- La outbox y las filas de entrega a destinatarios se guardan en la misma transacción que el consentimiento y la revisión exportable. No se confirma publicación si no quedó persistida la intención de entrega.
- Cada entrega por destinatario tiene un `event_id` propio y una clave de deduplicación durable, propuesta como `(recipient_membership_id, event_id)`; `publication_id` agrupa las entregas creadas por una confirmación. Se conserva el hash del envelope.
- Repetir el mismo ID con el mismo hash devuelve el resultado/recibo idempotente anterior sin nuevas revisiones o efectos. Reutilizar el ID con hash diferente es error de integridad, se pone en cuarentena y se audita.
- `sender_sequence` detecta huecos y reordenamiento; no es reloj factual ni criterio last-write-wins. Un evento fuera de orden puede persistirse en inbox, pero no sobrescribe un estado más reciente ni salta validaciones.
- Antes de entregar y de aceptar, el servidor revalida membresía, consentimiento, hash y generación. Si un receptor fue revocado antes de entregar, su fila pendiente no se envía. Una membresía nueva no entra en la audiencia histórica por defecto.
- Los eventos normales requieren membresía vigente. Los de revocación llevan `revocation_generation` como entero positivo monotónico y no pueden ser revertidos por un snapshot antiguo. Booleanos, valores no enteros, cero, valores negativos o generación ausente se rechazan.
- Los estados `PENDING`, `DELIVERED`, `ACKNOWLEDGED`, `FAILED` describen hechos persistidos: `DELIVERED` = el inbox del destinatario fue persistido; `ACKNOWLEDGED` = el destinatario registró la recepción/validación según el contrato; ninguno significa que el owner aceptó el conocimiento. La aceptación del contenido es un estado separado.
- Si el proceso cae tras guardar outbox y antes de materializar inbox, la recuperación puede reintentar con el mismo ID. Debe confirmarse el estado mediante lectura desde conexión nueva antes de mostrar éxito final en Office.

## 6. Recepción y aceptación local

El inbox conserva por separado evento recibido, validación y decisión del receptor:

1. **RECEIVED:** bytes/envelope guardados de manera durable.
2. **VALIDATED:** versión, firma del servicio, owner emisor, membresías destinataria y emisora, consentimiento, hash, clasificación y límites del payload comprobados.
3. **PENDING_REVIEW:** snapshot validado espera una decisión local; no es conocimiento activo de la colectiva.
4. **ACCEPTED:** el receptor acepta de forma explícita y queda una relación colectiva durable ligada al hash/revisión recibida.
5. **REJECTED / QUARANTINED:** contenido no deseado o inválido; se conserva el mínimo registro de auditoría necesario sin activar el dato.

La aceptación es una acción autenticada del owner receptor, con versión/hash esperados. Un cliente no puede cambiar directamente el estado del inbox mediante PATCH genérico. Los rechazos deben evitar revelar datos privados de terceros y no ejecutar instrucciones incluidas en el snapshot.

## 7. Conflictos y revisiones

Para Knowledge factual v1, **no existe resolución automática**.

- Cada revisión es inmutable y referencia la revisión padre o padres que la originaron.
- Si llegan dos snapshots incompatibles basados en la misma revisión base, o si la base recibida no coincide con la base activa del receptor, el servicio conserva ambas revisiones y crea un conflicto explícito.
- La presencia de una marca temporal más reciente no resuelve el conflicto. No se usa last-write-wins.
- La resolución requiere actor autorizado, selección/reconciliación visible, justificación opcional y creación de una revisión nueva con enlaces a todas las revisiones en conflicto. Las revisiones originales no se sobrescriben.
- Mientras un conflicto esté pendiente, los sistemas no deben presentar uno de los valores como «consenso de la colectiva». Office debe mostrar conflicto sin resolver y permitir inspección/revisión.
- Cualquier estrategia de merge automático futura requiere semántica específica por tipo de dato, una versión nueva del contrato y tests de propiedades/concurrencia; queda fuera de v1.

## 8. Revocación y límites de control

Revocar significa cancelar el consentimiento para nuevas entregas y hacer que la colectiva deje de presentar esa relación como activa; **no implica la capacidad de borrar todas las copias fuera del control del emisor**.

- La revocación incrementa una generación monotónica y crea un tombstone durable ligado a colectiva, registro/linaje, revisión/hash y consentimiento.
- Outbox no entregada se cancela en la misma transacción; una entrega en vuelo puede dejar de ser recuperable, por eso el protocolo necesita evento de revocación posterior y receipt.
- El receptor que valida un tombstone marca la relación retirada, bloquea su redistribución y la excluye de la vista activa de colectiva. Mantiene el mínimo historial/auditoría para explicar el cambio. El tratamiento de copias locales ya curadas o exportadas requiere una política del producto separada; no se afirma borrado remoto.
- Un snapshot con generación de consentimiento anterior no puede reactivar la relación. Reintentos y mensajes fuera de orden no eliminan el tombstone.
- La revocación no puede reactivar una membresía suspendida/revocada ni volver a autorizar un consentimiento revocado.
- Office debe distinguir revocación solicitada, tombstone persistido y estado de la proyección/inbox del destinatario. Un registro persistido en el backend no prueba que se hayan eliminado copias locales descargadas o exportadas. Nunca mostrar «borrado en todas partes».

## 9. Esquema conceptual y límites transaccionales

Entidades aditivas candidatas (nombres ilustrativos hasta revisar convenciones de migración):

- `hive_collectives` y `hive_collective_memberships`: owner creador, política, estado de invitación/membresía y generación.
- `hive_share_consents`: revisión/hash exactos, actor, colectiva destino, conjunto destinatario autorizado, versión de política y revocación.
- `hive_sync_outbox` y filas de entrega por destinatario: envelope/hash, estado, secuencia, intento, recibo y timestamps.
- `hive_sync_inbox`: owner/membresía receptora, evento/hash, estado de validación/decisión y recibo.
- `hive_collective_revisions`, `hive_collective_conflicts` y `hive_revocation_tombstones`: historial inmutable, conflictos y generaciones de revocación.
- Registro público de `service_key_id` y estado/validez para validar firmas; **la clave privada no va a Postgres ni al repositorio**. La ubicación de clave privada/rotación se decide con el mecanismo de secretos real.

No se proponen tablas de pares de dispositivos en Sync v1; eso pertenece al contrato Local Agent. Restricciones mínimas: índices únicos para deduplicación; FK/ownership verificable; transiciones por versión esperada; timestamps UTC; tamaño máximo del payload; límites de retención documentados; índices para outbox pendiente, inbox pendiente, conflictos y tombstones. La migración debe ser aditiva. No se edita una migración aplicada y no se cambia el CHECK de `privacy_level` hasta identificar todos sus lectores/escritores.

Transacciones mínimas:
- consentimiento + revisión/hash validado + snapshot/outbox por audiencia + auditoría;
- aceptación del inbox + relación colectiva + auditoría;
- decisión de conflicto + revisión nueva + resolución + auditoría;
- revocación + incremento de generación + tombstone + cancelación de outbox pendiente + auditoría.

Si cualquier escritura obligatoria falla, se revierte la operación completa. Nunca se devuelve éxito parcial. La implementación debe usar `PostgresRepository.transaction()` y las convenciones existentes; antes de migrar, se inspecciona `persistence/migrations.py`, el registro de entidades y todos los lectores/escritores de Knowledge.

## 10. Superficie API candidata

Los nombres siguientes son una propuesta compatible con el prefijo Hive actual, pendiente de comprobar routers, convenciones, versionado y controles auth reales. No son endpoints existentes:

- `POST /api/v8/hive/collectives` — crear colectiva.
- `POST /api/v8/hive/collectives/{collective_id}/invitations` y `POST /api/v8/hive/invitations/{token}/accept` — invitar/aceptar.
- `GET /api/v8/hive/collectives` — colectivas/membresías visibles para el principal.
- `POST /api/v8/hive/collectives/{collective_id}/knowledge/{knowledge_id}/publish` — consentimiento explícito con `expected_version`, `expected_hash` y audiencia que se mostrará antes de confirmar.
- `GET /api/v8/hive/collectives/{collective_id}/outbox` — estados derivados de persistencia.
- `GET /api/v8/hive/collectives/{collective_id}/inbox` y acciones explícitas `accept/reject` por `event_id`.
- `GET /api/v8/hive/collectives/{collective_id}/conflicts` y `POST /api/v8/hive/collectives/{collective_id}/conflicts/{conflict_id}/resolve`.
- `POST /api/v8/hive/collectives/{collective_id}/knowledge/{knowledge_id}/revoke` — revocación de un consentimiento/revisión exactos.
- La creación y validación del envelope y su entrega a inbox son funciones internas de servicio/worker, no un endpoint público de ingestión de eventos.

Cada escritura requiere auth de owner, autorización por colectiva, estado vigente y versión/hash cuando cambia un dato. Las respuestas para recursos ajenos no deben distinguir «no existe» de «no autorizado». Códigos propuestos: `401` sin sesión válida, `403` sin autorización donde proceda, `404` opaco para recursos ajenos, `409` versión/conflicto/idempotency mismatch, `410` invitación caducada/usada, `422` firma/payload inválidos y `503` fallo de persistencia/capacidad. El uso final debe respetar el contrato real del backend.

## 11. Criterios de aceptación para la implementación

El siguiente PR de código no debe abrirse hasta revisar este contrato, resolver el key management del servicio y leer de nuevo los routers, modelos, esquema de Knowledge y mecanismo de auth. Debe incluir como mínimo:

1. **Aislamiento de propietarios:** tests de dos owners y varias membresías destinatarias; no leer ni mutar filas ajenas y respuestas opacas para recursos ajenos.
2. **Identidad e integridad:** firma del servicio válida/inválida, clave desconocida/rotada/revocada, membresía suspendida/revocada, envelope con destinatario distinto y principal incorrecto.
3. **Consentimiento:** ausencia, colectivo incorrecto, versión/hash obsoletos, cambio material tras consentir, contenido `PRIVATE`/`SENSITIVE`, evidencia/procedencia incompletas y nueva confirmación después de editar.
4. **Idempotencia:** evento duplicado idéntico no produce mutaciones duplicadas; ID repetido con hash diferente va a cuarentena.
5. **Concurrencia y orden:** IDs UUID no canónicos, generación de revocación ausente/no positiva, mensajes duplicados/reordenados, huecos de secuencia, dos revisiones concurrentes y revocación más antigua que un snapshot reenviado.
6. **Atomicidad/durabilidad:** fallo al escribir outbox/inbox/auditoría revierte toda la operación; caída simulada entre persistir y entregar puede recuperarse; lectura desde conexión nueva confirma estado y recibo.
7. **Conflictos:** ambas revisiones sobreviven, no existe last-write-wins y resolver genera una revisión nueva auditable.
8. **Revocación:** cancela pendientes, bloquea nuevas entregas, genera tombstone, impide reactivación por un evento antiguo y refleja el límite de las copias externas.
9. **Límites operativos:** payload demasiado grande, versión desconocida, firmas/serialización inválidas, rate limit, errores controlados de DB, sin secretos de producción.
10. **UI posterior:** estados de outbox/inbox/conflictos/revocación proceden de API real; un intento no se presenta como entrega/aceptación y un fallo de API no muta la UI a éxito.

Todas las pruebas deben ejecutarse en PostgreSQL desechable o fixtures aisladas. Ningún test usa credenciales de producción, modelos de pago o servicios externos reales.

## 12. Secuencia de trabajo y gates

1. Revisar esta propuesta frente al Handoff Maestro/Pasaporte y aprobar/rechazar explícitamente la topología mediada, la semántica de audiencia y la firma de servicio.
2. Resolver key management para Render, selección/versionado de dependencias Ed25519/JCS y vectores de interoperabilidad. Sin eso no se habilita sincronización firmada.
3. Tras aprobación del contrato, volver a inspeccionar migraciones, auth, schema de Knowledge y convenciones de API.
4. Abrir un PR de implementación backend separado: modelos/migraciones aditivas, servicios y contratos transaccionales; después endpoints, outbox/inbox y tests.
5. Probar en PostgreSQL desechable con owners/membresías sintéticos y lecturas desde conexiones nuevas.
6. Implementar y probar conflictos y revocaciones antes de conectar controles de Office.
7. Diseñar Local Agent en un artefacto/PR separado, con emparejamiento, scopes, sandbox, límites de red/FS, approvals y health challenge; no reutilizar el token web como llave maestra.
8. Ejecutar CI, revisión de seguridad y aprobación humana. El backend se despliega primero solo después de aprobar; luego se verifica runtime/persistencia antes de publicar frontend.
9. Ejecutar auditoría integral entre sistemas al completar F15. No declarar F15 completa por el merge de una sola unidad.

## 13. Decisiones propuestas que requieren revisión explícita

- Transporte mediado por backend en v1, con envelopes Ed25519 firmados por el servicio, JSON canónico JCS y hash SHA-256; ninguna ruta pública acepta envelopes arbitrarios.
- Invitación con aceptación explícita; membresía revocable y denegación por defecto.
- V1 sin merge automático de conocimiento factual.
- Consentimiento vinculado a una única revisión/hash, una colectiva destino y el conjunto concreto de membresías destinatarias autorizado; miembros nuevos no heredan publicaciones históricas.
- Inbox requiere aceptación del owner receptor; recepción no activa conocimiento por sí sola.
- Estado `COLLECTIVE` como relación de distribución/aceptación separada del valor `privacy_level`: el esquema legado ya permite ese literal, pero Share Gate actualmente lo rechaza y el valor aislado no representa membresía/consentimiento. No cambiar su uso sin una auditoría global de lectores/escritores.
- Revocación como tombstone durable y bloqueo de distribución futura, sin prometer eliminación garantizada de copias externas.
- Local Agent fuera del alcance de sync v1, separado en contrato y ciclo de release.

**Estado final:** solo se propone un contrato revisable. Este documento no prueba ni implementa sincronización colectiva, no crea datos, no publica endpoints, no registra peers y no cambia producción. Cualquier desacuerdo de contrato debe resolverse antes de migraciones y ejecución.

## 14. Hallazgos operativos y gate de clave — 2026-10-09

Esta sección registra hechos observados y límites, sin afirmar que exista ya una clave de sincronización configurada.

### Hechos comprobados

- El servicio Render identificado como backend AKIRA ejecuta Python, construye con `pip install -r requirements.txt`, está en plan `free`, tiene `autoDeploy=yes` y sigue la rama `main`. Por tanto, una fusión posterior a `main` dispararía despliegue automático. No desplegar una implementación colectiva mientras no pase los gates de contrato, claves y CI.
- El `requirements.txt` actual no declara directamente `cryptography` ni `rfc8785`; ninguna de ellas se añadió en este PR. La dependencia transitiva de otra librería no sustituye declarar la dependencia criptográfica que el código usa directamente.
- PyCA `cryptography` ofrece Ed25519 para firmar y verificar; la release PyPI consultada `50.0.2` declara Python `>=3.9`. PyPI muestra `rfc8785` `0.1.4`, paquete Python sin dependencias para JCS, pero aparece con estado Beta. Las dependencias están añadidas y fijadas en el PR Draft separado [#139](https://github.com/AkiraGr2/akira-empresa/pull/139), no en `main`; sus 30 tests incluyen vectores JCS y firmas y pasaron en el SHA enlazado arriba. Eso no sustituye revisión interoperable independiente ni activa el runtime.
- Render documenta que se pueden almacenar *Secret Files* desde el panel y leerlos en runtime; para servicios no-Docker, están disponibles en el directorio del servicio y en `/etc/secrets/<filename>`. Render también documenta el uso de variables de entorno para configuración/secrets. Fuentes: [Render — Environment Variables and Secrets](https://render.com/docs/configure-environment-variables), [PyCA cryptography 50.0.2](https://pypi.org/project/cryptography/50.0.2/), [rfc8785 0.1.4](https://pypi.org/project/rfc8785/), [Ed25519 API](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/), [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785.html).
- La metadata leída del servicio no permite confirmar que exista un archivo secreto o una variable concreta con la clave de sincronización. El estado de la clave actual, por tanto, es **NO VERIFICADO**. No se inspeccionaron valores secretos ni se cambiaron variables, archivos secretos, servicios, planes o despliegues.
- La documentación de Render sobre su plan gratuito indica que Free está pensado para probar el servicio y no recomienda usarlo para aplicaciones de producción: [Render — Deploy for Free](https://render.com/docs/free). La configuración actual del backend es Free; esto no prueba un fallo criptográfico, pero sí es una limitación operativa que se debe resolver o aceptar formalmente antes de activar sincronización en producción.

### Aprovisionamiento propuesto, no ejecutado

1. En un contexto controlado por el operador, generar una clave privada Ed25519 fuera del repositorio y mantener la privada fuera de GitHub, logs, variables de salida de CI y Knowledge. Nunca generar una nueva clave automáticamente al arrancar el servicio: eso rompería la continuidad de `service_key_id` entre reinicios.
2. Preferir un *Secret File* del servicio Render, por ejemplo `/etc/secrets/hive-sync-ed25519.pem`, con acceso operativo restringido. La ruta sería configuración (`HIVE_SYNC_SIGNING_KEY_FILE`); el identificador público se configuraría por separado (`HIVE_SYNC_SIGNING_KEY_ID`). Estos nombres son candidatos y no son todavía configuración activa.
3. Registrar el material público y el `service_key_id` mediante un proceso auditado y versionado. Verificar la clave pública derivada de la clave privada fuera de línea antes de habilitar firma. No poner nunca la privada en tablas de Postgres.
4. Definir una rotación con periodo de solapamiento: los verificadores aceptan la clave pública activa y la(s) anterior(es) aprobadas durante la ventana acordada; después de la transición, revocar la anterior sin invalidar silenciosamente recibos históricos. La política de retención debe quedar explícita.
5. Fallar cerrado si falta la clave, el identificador, la clave no se puede cargar o la pareja de claves no coincide. No crear una clave de desarrollo implícita ni devolver un estado de sincronización disponible.
6. Antes de un despliegue productivo, resolver el plan Free, provisionar la clave mediante el mecanismo elegido y comprobar el estado sin imprimir su valor. Ninguna acción de aprovisionamiento se ha realizado en este paso.

### Pruebas obligatorias de preparación

- Carga válida de clave desde archivo temporal de test y rechazo de ruta ausente, formato inválido, clave pública no coincidente y permisos/errores de lectura.
- Generar y verificar envelope con claves efímeras solo de test; alteraciones de hash, destinatario, consentimiento, versión, `key_id` o payload deben fallar.
- Vectores JCS fijos compartidos que cubran orden de claves, Unicode, números, arrays, claves inválidas, valores no representables y campo `signature` excluido del mensaje firmado.
- Rotación de `service_key_id`, firma de nueva clave y verificación histórica bajo la política aprobada.
- Comprobar que logs y respuestas HTTP nunca imprimen PEM/bytes privados y que error de configuración mantiene sync deshabilitada.

**Gate de salida:** contrato revisado/aprobado; dependencias declaradas y fijadas; secreto configurado por el operador en el entorno correcto; clave pública registrada/verificada; pruebas de vector y rotación correctas; plan de despliegue compatible con la política operativa. Hasta cumplirlo, Hive Collective Sync permanece no disponible.

## 15. Auditoría de persistencia previa a una migración — observación de `main`

Esta sección es una lectura estática de `main` observada el 2026-10-09. Es una propuesta de implementación y una lista de restricciones; no es una migración ejecutada. Debe volver a revisarse contra el SHA y los PR aprobados justo antes de programar DDL.

### 15.1 Hechos del repositorio

- `persistence/migrations.py` mantiene migraciones como lista explícita y el encabezado prohíbe editar migraciones ya aplicadas. En el SHA consultado, la secuencia de la lista llega a `054_tool_invocation_owner_scope_and_idempotency`; `055_hive_collective_sync_v1` sería un nombre candidato, no una migración existente.
- El ejecutor `persistence/postgres.py` aplica migraciones bajo un advisory transaction lock. Su parser separa sentencias por punto y coma; una migración nueva debe evitar punto y coma dentro de comentarios/literales que confunda ese parser.
- El repositorio usa SQL con identificadores de tabla/columna tomados de la allowlist `ENTITIES` en `persistence/core.py`, y valores parametrizados. Una entidad a la que se acceda con los métodos genéricos necesita una entrada explícita en `ENTITIES` con columnas, columnas JSON, campos mutables, filtros y orden permitidos. No basta con crear una tabla.
- `PostgresRepository.transaction()` crea un repositorio atado a una sola conexión; las operaciones anidadas reutilizan esa transacción. Las escrituras obligatorias de publicación/aceptación/revocación deben usar esa única transacción y el API existente de auditoría, no hacer commits independientes.
- La migración `049_knowledge_first_class_and_graph_fk` crea `knowledge_records.id` como `TEXT`; su CHECK permite `COLLECTIVE` como valor de privacidad pero no define relaciones colectivas. Cualquier FK desde las tablas propuestas al Knowledge fuente debe conservar el tipo `TEXT`. No se cambia la tabla ni el CHECK existente en este diseño.
- Las migraciones de seguridad existentes habilitan RLS y revocan acceso directo a los roles Supabase `anon` y `authenticated`, con políticas restrictivas de denegación por defecto. Las tablas nuevas deben seguir el mismo patrón; la autorización de negocio sigue en el backend autenticado.

### 15.2 Tablas candidatas y propósito

Todos los nombres/columnas son candidatos por revisar; no se crean en este PR.

| Tabla candidata | Datos propios y restricciones críticas |
|---|---|
| `hive_collectives` | UUID de colectiva, owner creador derivado en el servidor, estado, versión de política, timestamps. El propietario de una colectiva no debe poder adjudicar membresías a sí mismo cambiando IDs en el cliente. |
| `hive_collective_memberships` | UUID de membresía, colectiva, owner autenticado, estado `INVITED/ACTIVE/SUSPENDED/REVOKED`, generación, emisor/fechas de invitación/aceptación/revocación, hash de invitación y caducidad. Token original de invitación no se persiste. Índice que impida membresías activas duplicadas según la política aprobada; preservar historial revocado. |
| `hive_share_consents` | Consentimiento inmutable ligado a owner origen, Knowledge ID/versión, hash del snapshot, colectiva, conjunto exacto de membership IDs y generaciones destinatarias, hash de audiencia, política de redacción, actor/fecha y generación de revocación. No reutilizar un consentimiento para otra revisión o audiencia. |
| `hive_sync_outbox` | Una fila durable por entrega a un destinatario: `event_id`, `publication_id`, consentimiento, membership destino/generación, hash de envelope y snapshot, envelope sanitizado/firma/clave, estado `PENDING/DELIVERED/ACKNOWLEDGED/FAILED/CANCELLED`, intentos y fechas. Restricción única de deduplicación por destino + evento; ID repetido con hash distinto es error de integridad. |
| `hive_sync_inbox` | Evento/envelope recibido, hash y firma validada, membership destino, estado `RECEIVED/VALIDATED/PENDING_REVIEW/ACCEPTED/REJECTED/QUARANTINED`, versión/hash aceptados y recibo. `UNIQUE(recipient_membership_id,event_id)` debe hacer durable la idempotencia. |
| `hive_collective_revisions` | Historial inmutable de snapshots aceptados, linaje/revisión/padres, origen opaco, evento, hash, procedencia permitida, actor receptor y fecha. Nunca actualizar un snapshot previo para simular una revisión nueva. |
| `hive_collective_conflicts` | Linaje y revisiones/base en conflicto, estado pendiente/resuelto/rechazado, resolución, actor/fecha y vínculo a una nueva revisión de resolución. No se admite last-write-wins. |
| `hive_revocation_tombstones` | Consentimiento/linaje/hash destinatario, generación positiva, evento y acuse. Una revisión antigua no puede reactivar la relación; mantener el tombstone según retención aprobada. |
| `hive_sync_service_public_keys` (opcional) | Solo `service_key_id`, clave pública, algoritmo, estado y periodo de validez. Nunca almacenar aquí el PEM privado. Usarlo solo si la arquitectura de verificación realmente lo necesita, no solo por simetría de tablas. |

### 15.3 Invariantes DDL y de aplicación

- UUID en columnas de identidad/evento donde el contrato lo especifica; Knowledge fuente conserva su ID de texto actual.
- CHECK para estados finitos, contador de versión/generación entero positivo, hash de contenido/audiencia en hex SHA-256 y límites razonables al tamaño de JSON/firmas.
- Foreign keys con `ON DELETE RESTRICT` para conservar historia y auditoría; la baja lógica/revocación no debe borrar revisiones, receipts o tombstones.
- Restricciones únicas para idempotencia y evitar más de una membresía vigente conforme a la política aprobada. No confiar en «buscar primero y luego insertar»: la unicidad debe hacerse cumplir por la base de datos.
- RLS habilitado, `REVOKE ALL` a `anon`/`authenticated` y denegación directa por defecto, igual al baseline existente. No añadir políticas públicas para hacer funcionar Hive.
- Índices para outbox pendiente por `next_attempt_at`, inbox por estado/membresía, conflictos pendientes y tombstones por colectivo/linaje/generación. Índices y retención deben comprobarse sobre los tests; no inventar selectividad/volumen.
- Cualquier tabla incorporada a la interfaz genérica se añade explícitamente a `persistence/core.py:ENTITIES`; si requiere semánticas diferentes a CRUD/versionado genérico, se usa un servicio dedicado en vez de relajar la allowlist.

### 15.4 Límites transaccionales

1. **Publicar:** releer Knowledge bajo owner scope exacto y `expected_version`; comprobar verificación/evidencia, hash y privacidad; calcular y presentar audiencia; registrar consentimiento; crear outbox por destinatario y auditoría. Todo dentro de una transacción. No enviar mensajes externos dentro de esta transacción.
2. **Entregar internamente:** bloquear/adquirir una fila pending de outbox de forma concurrente segura; revalidar consent/generación/membresía; crear inbox de manera idempotente y actualizar el recibo/estado. Si el transporte futuro no es el mismo Postgres, usar un worker con lease/retry y no mantener una transacción abierta durante la red.
3. **Aceptar:** volver a leer inbox por owner/membership derivada de sesión, verificar `expected_hash` y `expected_version`, crear relación/revisión local y auditoría en una transacción.
4. **Resolver conflicto:** preservar entradas competidoras, crear nueva revisión con enlaces a sus padres y marcar resolución/auditoría atómicamente.
5. **Revocar:** incrementar generación, crear tombstones, cancelar outbox aún no entregada y emitir auditoría. Los acuses externos (si existen) son otro hecho durable, no prueba de eliminación de copias.

### 15.5 Puerta de implementación

Antes del primer archivo de migración: aceptar/rechazar la sección 13 de este contrato; inspeccionar de nuevo `ENTITIES`, CRUD, funciones de auditoría, rutas/auth y estado del schema; especificar retención/tamaño máximo del snapshot; ejecutar una migración equivalente en PostgreSQL desechable desde base limpia y desde una base ya migrada hasta `054`; probar rollback por fallo inyectado; y verificar denegación de acceso con roles `anon`/`authenticated`. No modificar Supabase productivo ni el estado de Render en esta etapa.
