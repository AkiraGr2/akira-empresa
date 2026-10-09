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

### 2.1 Principales y pares

- **Owner principal:** identidad autenticada por el mecanismo de sesión del backend. El servidor deriva el propietario a partir de la sesión; nunca acepta un `owner_scope`, `owner_id`, `is_owner` ni rol del cuerpo JSON como autoridad.
- **Peer:** instalación/dispositivo con `peer_id` asignado por el servidor, asociado a un owner autenticado y a una clave pública. Una sesión de navegador no es por sí sola prueba de identidad de otro peer.
- **Collective:** espacio de intercambio identificado por UUID. Tiene un creador owner y una política de membresía. La autorización se evalúa tanto para el principal autenticado como para el peer que firma el evento.
- **Miembro:** owner que aceptó una invitación. Las instalaciones de ese owner no obtienen automáticamente privilegios hasta registrar/emparejar su propia clave y estar activas.

La membresía es **por invitación, con aceptación explícita y caducidad**. Un token de invitación debe tener entropía criptográfica, almacenarse como hash, ser de un solo uso, estar ligado a la colectiva y al destinatario previsto cuando exista ese dato, y expirar. Invitar no equivale a activar. El backend debe denegar por defecto y no revelar si un principal ajeno existe.

Estados de membresía propuestos: `INVITED`, `ACTIVE`, `SUSPENDED`, `REVOKED`, con transiciones auditadas. `REVOKED` no vuelve a `ACTIVE` mediante reintento; se requiere nueva invitación/aceptación.

### 2.2 Claves y firmas

- Cada peer registrado tiene una clave de firma Ed25519; la clave privada permanece en el dispositivo que la controla. El servidor vincula la clave pública a `peer_id`, owner autenticado, fecha de alta y estado.
- Los envelopes usan JSON canónico conforme a RFC 8785, SHA-256 sobre los bytes canónicos y firma Ed25519 sobre el hash/contexto definido por la implementación.
- El `key_id` permite rotación explícita. Revocar una clave bloquea nuevos eventos firmados con ella. La rotación conserva el registro histórico y no revalida eventos previamente rechazados.
- El servidor verifica sesión, estado de peer, pertenencia activa, firma y elegibilidad en cada operación de escritura. Una firma válida no sustituye la autorización de aplicación.
- Las claves del servidor para firmar recibos se separan de las claves de peer. El almacenamiento y rotación de esas claves debe acordarse con las capacidades reales de deployment antes de implementarlas; no se permite hardcodear secretos en el repositorio o frontend.

**Puerta de implementación:** antes de habilitar transferencias, una prueba de desafío debe demostrar posesión de clave del peer y su vínculo con la sesión/owner. Hasta entonces, el estado de cualquier peer es no verificado.

## 3. Privacidad, consentimiento y semántica de «COLLECTIVE»

Para evitar romper el esquema existente y mezclar conceptos:

- `privacy_level` mantiene el significado de privacidad del registro (`PRIVATE`, `SHAREABLE`, `SENSITIVE`). No se usará una actualización genérica para hacer aparecer una publicación colectiva.
- La relación con la colectiva y su estado de distribución se modelan por separado. La UI puede mostrar **COLLECTIVE** cuando un snapshot fue aceptado y existe una relación activa, pero esto no crea permiso implícito para redistribuirlo.
- `PRIVATE` y `SENSITIVE` son inexportables. `SHAREABLE` permite considerar un snapshot para publicación, pero por sí solo no autoriza una transferencia.
- Cada consentimiento MUST incluir al menos owner actor, colectiva destino, ID de registro, versión de Knowledge, hash del snapshot exportable, versión del contrato, política de redacción, timestamp, y estado de revocación/generación. El consentimiento no se reutiliza para otro hash, colectiva o revisión.
- Cualquier cambio material invalida el consentimiento anterior. La re-publicación exige guardar una nueva versión verificable y una nueva confirmación explícita. La verificación nueva no vuelve a habilitar el envío automáticamente.
- El snapshot exportable es una proyección permitida por lista positiva; no incluye sesiones, tokens, owner scope privado, prompt/contexto interno, datos de otros propietarios ni metadatos que no hagan falta para la procedencia.

La aceptación de un elemento entrante crea una **relación local con el snapshot y su procedencia**, no permiso de reexportación. Si el receptor desea compartirlo con una segunda colectiva, debe revisarlo y otorgar su propio consentimiento sobre un snapshot nuevo bajo su propio owner. No hay propagación transitiva implícita.

## 4. Envelope del protocolo

Cada evento de transferencia candidato v1 incluye como mínimo:

- `protocol_version` (literal `hive-sync/1`) y `event_type`;
- `event_id` UUID, `collective_id`, `sender_peer_id`, `key_id`;
- `membership_generation` y `sender_sequence` monotónica por peer/colectiva;
- `knowledge_lineage_id`, `revision_id`, referencias de revisión padre y `content_hash`;
- snapshot mínimo sanitizado, nivel de privacidad y estado de verificación del snapshot;
- procedencia/evidencia asociada al mismo hash, en la proyección permitida;
- identificador y prueba del consentimiento que autoriza exactamente ese snapshot y destino;
- timestamp del emisor solo como dato de auditoría, nunca como autoridad para sobrescribir versiones;
- hash, firma y versión de formato/canonicalización.

Tipos iniciales permitidos: `KNOWLEDGE_SNAPSHOT` y `KNOWLEDGE_REVOCATION`. Los eventos de membresía se administran por el servicio de membresía y se verifican contra el estado durable; un sobre no puede autoproclamarse miembro. Versiones o tipos desconocidos se rechazan de forma cerrada y auditable.

Los campos exactos de evidencia/procedencia se deben cotejar contra el schema actual antes de codificarlos; el esquema no autoriza a filtrar evidencia privada por conveniencia de serialización.

## 5. Idempotencia, orden y entrega durable

- La outbox se guarda en la misma transacción que el consentimiento y la revisión exportable. No se confirma publicación si no quedó persistida la intención de entrega.
- La clave de deduplicación propuesta es `(collective_id, event_id)`; se guarda también el hash del envelope.
- Repetir el mismo ID con el mismo hash devuelve el recibo/idempotency result anterior sin nuevas revisiones ni auditorías duplicadas. Reutilizar el mismo ID con un hash diferente se trata como error de integridad, se pone en cuarentena y se registra.
- `sender_sequence` permite detectar huecos y reordenamiento; no se usa como reloj factual ni como criterio last-write-wins. Un evento recibido fuera de orden puede persistirse en inbox, pero no debe reemplazar un estado más reciente ni saltarse validaciones.
- Los eventos normales requieren el peer y la membresía vigentes al validarse. Los eventos de revocación llevan una generación de consentimiento monotónica y no pueden ser revertidos por un snapshot antiguo.
- La entrega es como máximo reintentable; la aplicación de evento debe ser idempotente. Los estados `PENDING`, `DELIVERED`, `ACKNOWLEDGED`, `FAILED` son hechos persistidos, no estimaciones del navegador. «Entregado» no es sinónimo de «aceptado».
- Si el proceso cae tras guardar outbox y antes de enviar, una recuperación puede reintentar el evento con el mismo ID. La persistencia del inbox/recibo debe confirmarse mediante una lectura nueva antes de mostrar éxito final en Office.

## 6. Recepción y aceptación local

El inbox conserva por separado evento recibido, validación y decisión del receptor:

1. **RECEIVED:** bytes/envelope guardados de manera durable.
2. **VALIDATED:** versión, firma, peer, membresía, consentimiento, hash, clasificación y límites del payload comprobados.
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
- La revocación no puede reactivar un peer ni restablecer una membresía suspendida/revocada.
- Office debe distinguir «revocación pendiente de confirmación remota», «confirmada por el peer» y «no se puede verificar el estado remoto». Nunca mostrar «borrado en todas partes».

## 9. Esquema conceptual y límites transaccionales

Entidades aditivas candidatas (nombres ilustrativos hasta revisar convenciones de migración):

- `hive_peers`: owner derivado en servidor, `peer_id`, clave pública/`key_id`, estado, timestamps de revocación.
- `hive_collectives` y `hive_collective_memberships`: owner creador, política, estado de invitación/membresía y generación.
- `hive_share_consents`: revisión/hash exactos, actor y colectiva destino, versión de política y revocación.
- `hive_sync_outbox`: envelope/hash, estado, intento, recibo y timestamps.
- `hive_sync_inbox`: peer emisor, evento/hash, estado de validación/decisión y recibo.
- `hive_collective_revisions`, `hive_collective_conflicts` y `hive_revocation_tombstones`: historial inmutable, conflictos y generaciones de revocación.

Restricciones mínimas propuestas: índices únicos de deduplicación para eventos; FK/ownership verificable; transiciones de estado condicionadas por versión esperada; timestamps UTC; payload size limit; límites de retención documentados; índices para outbox pendiente, inbox pendiente, conflictos y tombstones. La migración debe ser aditiva y reversible en el sentido operativo disponible; no se modifica una tabla/enum compartida sin buscar todos los lectores/escritores primero.

Transacciones mínimas:
- consentimiento + revisión/hash validado + outbox + auditoría;
- aceptación del inbox + relación colectiva + auditoría;
- decisión de conflicto + revisión nueva + resolución + auditoría;
- revocación + incremento de generación + tombstone + cancelación de outbox pendiente + auditoría.

Si cualquier escritura obligatoria falla, se revierte la transacción. La operación nunca devuelve éxito parcial.

## 10. Superficie API candidata

Los nombres siguientes son una propuesta compatible con el prefijo Hive actual, pendiente de comprobar routers, convenciones, versionado y controles auth reales. No son endpoints existentes:

- `POST /api/v8/hive/collectives` — crear colectiva.
- `POST /api/v8/hive/collectives/{id}/invitations` y `POST /api/v8/hive/invitations/{token}/accept` — invitar/aceptar.
- `GET /api/v8/hive/collectives` — colectivas/membresías visibles para el principal.
- `POST /api/v8/hive/collectives/{id}/knowledge/{id}/publish` — consentimiento explícito con `expected_version` y `expected_hash`.
- `GET /api/v8/hive/collectives/{id}/outbox` — estados derivados de persistencia.
- `POST /api/v8/hive/collectives/{id}/events` — ingresar envelope firmado e idempotente.
- `GET /api/v8/hive/collectives/{id}/inbox` y acciones explícitas `accept/reject`.
- `GET /api/v8/hive/collectives/{id}/conflicts` y `POST .../conflicts/{id}/resolve`.
- `POST /api/v8/hive/collectives/{id}/knowledge/{id}/revoke` — revocación de un consentimiento exacto.

Una llamada de escritura requiere auth de owner/peer, autorización por colectiva, estado vigente y versión/hash cuando cambia un dato. Las respuestas de objetos ajenos no deben distinguir «no existe» de «no autorizado». Códigos propuestos: `401` sin sesión válida, `403` sin autorización donde proceda, `404` opaco para recursos ajenos, `409` versión/conflicto/idempotency mismatch, `410` invitación caducada/usada, `422` firma/payload inválidos y `503` fallo de persistencia/capacidad. El uso final de códigos debe respetar el contrato real del backend.

## 11. Criterios de aceptación para la implementación

El siguiente PR de código no debe abrirse hasta revisar este contrato y leer de nuevo los routers, modelos, esquema de Knowledge y mecanismo de auth. Debe incluir como mínimo:

1. **Aislamiento de propietarios:** tests de dos owners y dos peers; no leer ni mutar filas ajenas y respuestas opacas para recursos ajenos.
2. **Identidad:** firma válida/inválida, clave revocada, peer suspendido, membresía revocada y principal incorrecto.
3. **Consentimiento:** ausencia, colectivo incorrecto, versión/hash obsoletos, cambio material tras consentir, contenido `PRIVATE`/`SENSITIVE`, evidencia/procedencia incompletas y nueva confirmación después de editar.
4. **Idempotencia:** evento duplicado idéntico no produce mutaciones duplicadas; ID repetido con hash diferente va a cuarentena.
5. **Concurrencia y orden:** mensajes duplicados/reordenados, huecos de secuencia, dos revisiones concurrentes y revocación más antigua que un snapshot reenviado.
6. **Atomicidad/durabilidad:** fallo al escribir outbox/inbox/auditoría revierte toda la operación; caída simulada entre persistir y entregar puede recuperarse; lectura desde conexión nueva confirma estado y recibo.
7. **Conflictos:** ambas revisiones sobreviven, no existe last-write-wins y resolver genera una revisión nueva auditable.
8. **Revocación:** cancela pendientes, bloquea nuevas entregas, genera tombstone, impide reactivación por un evento antiguo y refleja el límite de las copias externas.
9. **Límites operativos:** payload demasiado grande, versión desconocida, firmas/serialización inválidas, rate limit, errores controlados de DB, sin secretos de producción.
10. **UI posterior:** estados de outbox/inbox/conflictos/revocación proceden de API real; un intento no se presenta como entrega/aceptación y un fallo de API no muta la UI a éxito.

Todas las pruebas deben ejecutarse en PostgreSQL desechable o fixtures aisladas. Ningún test usa credenciales de producción, modelos de pago o servicios externos reales.

## 12. Secuencia de trabajo y gates

1. Revisar esta propuesta frente al Handoff Maestro/Pasaporte y resolver los puntos marcados en revisión.
2. Tras aprobación del contrato, volver a inspeccionar migraciones, auth, schema de Knowledge y convenciones de API.
3. Abrir un PR de implementación backend separado: modelo/migraciones aditivas, servicios y contratos de transacción; después endpoints, outbox/inbox y tests.
4. Probar en PostgreSQL desechable con pares sintéticos y lecturas desde conexiones nuevas.
5. Implementar y probar conflictos y revocaciones antes de conectar controles de Office.
6. Diseñar Local Agent en un artefacto/PR separado, con emparejamiento, scopes, sandbox, límites de red/FS, approvals y health challenge; no reutilizar el token web como llave maestra.
7. Ejecutar CI, revisión de seguridad y aprobación humana. El backend se despliega primero solo después de aprobar; luego se verifica runtime/persistencia antes de publicar frontend.
8. Ejecutar auditoría integral entre sistemas al completar F15. No declarar F15 completa por el merge de una sola unidad.

## 13. Decisiones propuestas que requieren revisión explícita

- Identidad y firma de peer con Ed25519, JSON canónico y hash SHA-256.
- Invitación con aceptación explícita; membresía revocable y denegación por defecto.
- V1 sin merge automático de conocimiento factual.
- Consentimiento vinculado a una única revisión/hash y a una única colectiva destino.
- Inbox requiere aceptación del owner receptor; recepción no activa conocimiento por sí sola.
- Estado `COLLECTIVE` como relación de distribución/aceptación separada de `privacy_level`, evitando ampliar enum sin auditoría global de lectores/escritores.
- Revocación como tombstone durable y bloqueo de distribución futura, sin prometer eliminación garantizada de copias externas.
- Local Agent fuera del alcance de sync v1, separado en contrato y ciclo de release.

**Estado final:** solo se propone un contrato revisable. Este documento no prueba ni implementa sincronización colectiva, no crea datos, no publica endpoints, no registra peers y no cambia producción. Cualquier desacuerdo de contrato debe resolverse antes de migraciones y ejecución.
