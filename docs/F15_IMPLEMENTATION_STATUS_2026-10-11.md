# Akira — continuidad técnica y estado de auditoría

Actualizado: 2026-10-14. Este documento registra observaciones verificadas en GitHub, Render, Supabase y CI. No significa que las fases F1–F15 estén cerradas.

## Alcance acordado

- Hive v1 conecta instalaciones de Akira que pertenecen a una misma propietaria autenticada.
- Cada instalación debe emparejarse y poder revocarse de forma individual. No se comparte entre propietarios en v1.
- Akira puede aprender de forma autónoma dentro de permisos y reglas configurados; publicar o ejecutar cambios externos conserva controles de autorización.

## Refresco de auditoría — 2026-10-14 17:34 UTC

- GitHub responde nuevamente para `AkiraGr2/akira-empresa`. `main` y Render live están en `35c48b659fad01c10f673f0c1e58549714f4862a`; deploy `dep-db7ratvavr4c73fmnitg` terminó `live`. Render sigue en Free, `main`, `autoDeploy=yes`, no suspendido. Métricas recientes no incluyen requests/latencia; logs de error disponibles llegan hasta el 10 oct y muestran Gemini 429/504.
- Supabase continúa saludable en PostgreSQL 17.11; 54 migraciones, la última es `054_tool_invocation_owner_scope_and_idempotency` (7 oct). Recuento directo confirma Identity Root 1, Self-Model 1, Learning 107, capabilities 15, capability_verifications 1.929, Evolution 3, autonomy 41 y Knowledge 2. Las capacidades F14/Hive siguen `stale`/`partial-unverified-degraded`, respectivamente.
- Advisors de Supabase: WARN por `postgres_fdw` y `vector` dentro de `public`; INFO por una FK de `capabilities` sin índice de cobertura y 22 índices no usados. Registrado para triage; sin cambios de esquema.
- PR #150 y #151 siguen abiertos en Draft, basados en `457785457898e93d47a96d697d917a22f781fcec`, anterior al `main` actual; #150 no reportó checks para su head actual. No se fusionó nada.
## Estado en producción

- GitHub restauró la cuenta `AkiraGr2`. La propietaria presentó la solicitud de revisión a GitHub; el ticket recibido es `4845126`. La causa concreta de la suspensión no ha sido informada.
- Backend `main` integró el PR #152 en el commit `35c48b659fad01c10f673f0c1e58549714f4862a`. Render terminó el despliegue automático `dep-db7ratvavr4c73fmnitg` y reportó `live` sobre ese SHA.
- Render mantiene el servicio `akira-empresa` en el plan Free, con auto despliegue desde `main`. Esto limita la idoneidad operativa para una sincronización crítica y debe resolverse antes de producción F15.
- El PR backend #147 habilitó la compuerta de consentimiento de Hive `SHAREABLE`. No transporta ni sincroniza Knowledge. Los cambios o la revocación del consentimiento deben invalidar el permiso de compartir.
- El PR frontend #89 está integrado. GitHub Pages entrega la UI de Hive Office. Sin sesión de propietaria, muestra “Sesión no autenticada” y no habilita cambios. Sus pruebas no acreditan una transferencia real entre instalaciones.
- Supabase sigue saludable. La consulta de solo lectura no encontró tablas de Hive, pairing, outbox, inbox, revocaciones o conflictos. No se aplicó migración F15 ni se cambió dato o secreto productivo.
- `COLLECTIVE` continúa bloqueado. No hay evidencia de pairing, membresías persistentes, entrega, aceptación, revisión de conflictos ni sincronización real en producción.

## Cambios recientes y evidencia

### F12 — concurrencia del ciclo de reparación

- Una ejecución PostgreSQL anterior falló una vez con `503 ConflictError` al persistir la etapa sandbox del ciclo de reparación; el reintento del workflow pasó. La escritura periódica del observador autónomo comparte la versión del self-model, por lo que podía invalidar una transición concurrente.
- El PR #152 permite hasta tres intentos de escritura cuando cambió la versión por una actualización ajena a la reparación. Si la misma reparación cambió concurrentemente, devuelve conflicto y no sobrescribe el cambio.
- La regresión local reproduce la escritura del observador. Pasaron 54 pruebas locales de reparación, seguridad de rutas, autorización e integridad entre fases.
- CI de #152 pasó `python-syntax` y `f12-postgres-e2e` en el head `2af712dbf541e7ed9e7446f247c5b6c0bb70d40b`. El PR se integró por squash como `35c48b659fad01c10f673f0c1e58549714f4862a`.
- La primera suite local ejecutó 364 tests y tuvo 16 errores de dependencias. En la ejecución actual con dependencias disponibles corrieron 409: 405 pasaron; 1 falló por falta de PyMuPDF (`fitz`) y 3 no pudieron verificarse porque faltaba PostgreSQL local para E2E F12/F15 y faltaba `rfc8785` para el contrato criptográfico. No equivale a suite completa aprobada. Un intento heredó una configuración de conexión no aislada y se detuvo al agotarse el tiempo de conexión; la ejecución final usó `127.0.0.1:1` para impedir acceso a bases externas.

### F15 — propuesta de sincronización entre instalaciones

- PR #150 está abierto en Draft (`d729c0efd70a7180e7d8a2ac374298097e9bab55`). Añade primitivas aisladas RFC 8785/JCS, SHA-256 y Ed25519 con pruebas de contrato y CI. `python-syntax` y `f12-postgres-e2e` pasaron en ese head.
- #150 y #151 se crearon sobre el `main` anterior (`457785457898e93d47a96d697d917a22f781fcec`), antes de integrar #152; su CI verde corresponde a esos heads, no al `main` nuevo.
- #150 no conecta el runtime, no crea endpoints o migraciones, no configura claves ni inicia transferencias. El paquete `rfc8785==0.1.4` requiere validación independiente de interoperabilidad antes de aceptar su uso. Custodia, distribución y rotación de claves también están sin aprobar.
- PR #151 es una propuesta documental del protocolo. Está en Draft; no constituye aprobación del contrato ni implementa sincronización.
- Pairing, invitaciones de un solo uso, persistencia de memberships, outbox/inbox, entrega idempotente, aceptación humana, conflictos sin “último cambio gana”, tombstones de revocación y sandbox de Local Agent siguen pendientes.
- No habilitar `COLLECTIVE`, no aplicar DDL productivo y no cargar claves de servicio hasta completar revisión del protocolo, interoperabilidad, autorización, pruebas E2E y reversión.

## Auditoría de fases F1–F15

- Se localizaron los cinco documentos maestros que habían sido adjuntados a la conversación. Estaban dentro de `.codex-remote-attachments`, una carpeta oculta que no apareció en la búsqueda anterior; decir que no existían fue un error de búsqueda. Se preservaron los adjuntos y se copiaron sin cambios a `Continuidad-Maestra/` para que sean visibles en Obsidian.
- El [índice de continuidad](../../Continuidad-Maestra/00-LEEME.md) explica jerarquía y antigüedad de las fuentes. HANDOFFMAESTRO establece que la arquitectura canónica D020 prevalece sobre numeraciones históricas. MATRIXMAESTRAv1 es una fotografía con corte 2026-10-04 y no representa por sí sola el estado vivo.
- Se añadió la [auditoría con mapa canónico y evidencia F1–F15](AUDIT_PHASES_F1_F15_EVIDENCE_2026-10-14.md); distingue código, pruebas, datos productivos y gates pendientes.
- `test_phase_relation_integrity.py` comprueba un escenario sintético entre fases y limpieza de fixtures; no certifica la implementación completa de las quince fases.
- La revisión actual sí usa el mapa maestro, pero no permite declarar las quince fases cerradas: aún falta aceptar individualmente cada subcomponente según Definition of Done, resolver F14 stale y completar F15+.
- Se verificaron copias fieles en `Continuidad-Maestra/`; no se sobrescribieron los cinco originales adjuntos.

### Contraste de producción consultado el 2026-10-14

- Supabase estaba `ACTIVE_HEALTHY` (PostgreSQL 17.11; 54 filas de migración). Entre los conteos leídos sin acceder a contenido privado: Identity Root 1; Self-Model 1; capabilities 15; verificaciones 1.929; Knowledge 2; grafo 87 nodos/463 relaciones; memoria 35 registros/6 embeddings; ejecuciones F14 41.
- Las capacidades de identidad, memoria, grafo, aprendizaje, reparación y autoconocimiento consultadas aparecen verificadas y disponibles. `controlled_autonomy_v1` aparece implementada/disponible pero con verificación `stale`; Hive aparece `partial/unverified/degraded`.
- `memory_save` y `memory_search` están actualmente limitadas al propietario. Los dos Knowledge observados son privados. Los tres registros de Evolution corresponden a `selftest_component` en investigación/evaluación: no demuestran evolución productiva completada.
- No se encontraron tablas productivas de pairing, memberships, outbox/inbox, tombstones o sincronización de Hive. No se aplicó DDL ni se modificaron datos productivos.

### Aprendizaje sin aprobación por cada evento

- La absorción de chats se configura en `nexus.py` con `AKIRA_ABSORPTION_MODE`; el valor por defecto en el código es `off`. No se leyó la configuración de producción, así que no se afirma cuál modo está activo allí.
- El modo `candidate` guarda de forma automática solo un candidato de aprendizaje, sin evidencia y sin acceso directo a recuperación. El motor impide marcarlo verificado o consolidado sin evidencia; consolidar exige además una evaluación `supported` con confianza mínima 0,70. No encontramos un verificador autónomo que cierre ese ciclo de extremo a extremo.
- La petición de la propietaria es que el aprendizaje interno, privado, reversible y basado en evidencia continúe sin aprobación humana por cada evento, dejando a la persona como supervisora con opción de revisar/pausar/corregir. Esto no obliga a quitar las compuertas de acciones externas o irreversibles: compartir datos, cambiar permisos, aplicar código/infraestructura, borrar o gastar deben conservar autorización y límites explícitos.
- Este es un requisito de producto pendiente, no una razón para cambiar ahora la variable de producción. Primero hay que diseñar y probar clasificación, verificación, privacidad/propiedad, consolidación reversible, auditoría, límites de costo/frecuencia y pausa; luego verificar el modo de producción sin exponer secretos.

## Próximas acciones

1. Actualizar las ramas de PR #150 y #151 frente al `main` nuevo, volver a correr CI y mantenerlas como propuestas hasta revisar sus gates.
2. Validar JCS con vectores fijos compartidos entre implementaciones y revisar la dependencia Beta; definir custodia/rotación de claves antes de conectarlas al runtime.
3. Continuar la matriz de aceptación desde el mapa canónico, requisito por requisito; registrar cada punto como verificado, fallido o sin evidencia. La auditoría actual es amplia pero no reemplaza esa aceptación exhaustiva.
4. Diseñar e implementar pairing, persistencia, entrega y aceptación en etapas aisladas. Probar migraciones y rollback en PostgreSQL desechable; no tocar producción antes del gate.
5. Volver a ejecutar la suite local en un entorno con dependencias correctas. Mantener los errores actuales como limitación del entorno, no como aprobación.

## Decisiones de seguridad

- Las credenciales, claves privadas, tokens y secretos no se escriben en Obsidian ni se imprimen en logs.
- Los cambios automáticos de código pueden proponerse y probarse en ramas/PR; escribir en producción, desplegar infraestructura sensible o compartir datos requiere una autorización específica según la política operativa.
- La restauración de GitHub no demuestra cuál fue la causa de la suspensión. Las solicitudes F14 repetidas por rutas ya existentes son un antecedente, no una causa confirmada.
