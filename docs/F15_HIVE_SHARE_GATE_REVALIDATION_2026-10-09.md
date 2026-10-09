# F15 — Revalidación inicial y contrato de Hive Share Gate

**Fecha:** 2026-10-09 (COT)  
**Estado del documento:** diseño y criterios de aceptación; no constituye cierre de F15.  
**Rama de trabajo:** `akira/f15-hive-share-gate-20261009`  
**Base backend observada:** `7060e02ac01868425adb5f4e0c4748c88f05387b`  
**Base frontend observada:** `0ff0cd8eea5406bfc0c3e5e9c71eb301589aca8c`

## 1. Protocolo operativo

Se conserva el orden:

`ANALIZAR → DISEÑAR → PREPARAR SOLUCIÓN → VERIFICAR LA IDEA → CORREGIR LA IDEA → AUDITAR LA IDEA → VERIFICAR SEGURIDAD → IMPLEMENTAR → TESTS → CI → MERGE → DEPLOY → RUNTIME → PERSISTENCIA → EVIDENCIA → AUDITORÍA FINAL → CIERRE`

No se reabren F1–F14 sin una discrepancia concreta que bloquee F15. La auditoría integral entre sistemas queda reservada para después de terminar F15.

## 2. Fuente y alcance canónico

Las fuentes de continuidad localizadas describen F15+ como Hive, Office avanzado y Local Agent, pero no se encontró un contrato detallado y versionado de F15 en los HCV disponibles. Por ello, esta primera entrega materializa solo una unidad vertical mínima deducida del código real: una compuerta de privacidad de conocimiento controlada por el propietario. No pretende sustituir el contrato canónico completo cuando se recupere.

Arquitectura recuperada para Hive: `PRIVATE → SHAREABLE autorizado → COLLECTIVE`, con procedencia, privacidad, sincronización, resolución de conflictos y límites de propagación.

## 3. Estado inicial observado

- Backend `main`: `7060e02ac01868425adb5f4e0c4748c88f05387b`.
- Frontend `main`: `0ff0cd8eea5406bfc0c3e5e9c71eb301589aca8c`.
- Backend Render: servicio `akira-empresa`; deploy `dep-db4fbioae00c73a22uk0` observado como LIVE en el SHA backend anterior.
- Frontend: workflows de sintaxis, Browser E2E, Pixel Office E2E y Pages deploy completados con éxito en el SHA frontend anterior.
- Supabase: proyecto `kqurkakznuxgkzklujrh` observado como ACTIVE_HEALTHY. `knowledge_records` tiene columnas de propietario, privacidad, procedencia, evidencia, versión y estado de verificación.
- Persistencia previa: los niveles `PRIVATE`, `SENSITIVE`, `SHAREABLE` y `COLLECTIVE` existen; `HIVE_VISIBLE` se aplica al conteo/consulta de memorias, no es sincronización de Knowledge.
- Falta previa: no había rutas `/api/v8/hive/*`, ni un registro `hive` dedicado en el catálogo productivo de capacidades, ni un contrato de propagación entre propietarios.
- Office v5 ya existe; no se rediseña en esta primera unidad. No se encontró una implementación de Local Agent que permita afirmar disponibilidad.

## 4. Contrato de la primera unidad F15

| ID | Criterio de aceptación | Evidencia requerida |
|---|---|---|
| HSG-01 | Las rutas de estado, vista exportable y transición Hive requieren la guardia central de propietario. | Prueba estática de rutas + CI. |
| HSG-02 | Las operaciones sobre conocimiento exigen coincidencia exacta de `owner_scope`; el fallback legacy `owner_scope='owner'` no autoriza publicación. | Regresión con dos scopes y registro legacy. |
| HSG-03 | Una transición de privacidad exige confirmación explícita y `expected_version` válido. | Pruebas negativas para confirmación y versión. |
| HSG-04 | Solo conocimiento activo, verificado, con evidencia y procedencia (`source_reference` o `source_id`) puede pasar a `SHAREABLE`. | Pruebas de estado, evidencia y procedencia. |
| HSG-05 | El cambio de privacidad es versionado y la auditoría se escribe en la misma transacción; relectura confirma el resultado. | Prueba de versión, evento auditado y relectura. |
| HSG-06 | La vista exportable devuelve únicamente Knowledge `SHAREABLE`, verificado y del scope exacto del solicitante. | Prueba de aislamiento y exclusión de registros privados. |
| HSG-07 | La ruta genérica de actualización de Knowledge no puede saltarse la compuerta Hive cambiando `privacy_level`. | Prueba de servicio y guardia de API. |
| HSG-08 | La transición a `COLLECTIVE` falla de forma cerrada: no modifica datos y no simula sincronización. | Prueba negativa y versión sin cambios. |
| HSG-09 | Una versión obsoleta es rechazada sin sobreescritura; un propietario puede revocar el estado compartible. | Pruebas de conflicto y revocación. |
| HSG-10 | Esta unidad no realiza propagación externa ni concede acceso público o entre propietarios. | Flags explícitos de respuesta y evento de auditoría. |

## 5. Límites explícitos de esta entrega

Esta primera unidad no implementa la sincronización entre propietarios, promoción colectiva, resolución distribuida de conflictos, elección de peers, ni ejecución de comandos o acceso a filesystem local. La respuesta del backend debe seguir declarando estas capacidades como no disponibles. `SHAREABLE` representa elegibilidad para una futura integración autorizada, no publicación externa ejecutada.

No se añade tabla ni migración: el primer contrato usa `knowledge_records` y `audit_log` existentes. No se reescriben registros históricos ni se ajustan estados persistidos manualmente.

## 6. Riesgos previstos y mitigaciones

1. **Lectura cruzada accidental:** consultas restringidas por scope exacto y pruebas de dos propietarios.
2. **Bypass vía API antigua:** `PATCH /api/v8/knowledge/{id}` rechaza cambios de privacidad; el servicio también aplica el guard.
3. **Registro legacy de alcance ambiguo:** coincidencia exacta para la nueva transición, aun cuando lecturas existentes conservan compatibilidad.
4. **Compartir hechos sin validar:** requerir verificación, evidencia y referencia de procedencia.
5. **Doble operación o concurrencia:** versión optimista, conflicto explícito y relectura posterior.
6. **Éxito de UI sin persistencia:** se exige relectura desde el servicio y evento auditado en la transacción.
7. **Sincronización simulada:** `propagation_performed=false` y rechazo de `COLLECTIVE`.
8. **Regresión de capacidades:** registro nuevo `partial / unverified / degraded` y prueba de contrato; no marcar Hive completa como verificada.
9. **Regresión de rutas:** añadir el prefijo Hive al contrato de rutas sensibles.
10. **Despliegue prematuro:** no se hará merge ni se declarará producción hasta revisar CI, aprobación del PR, Render, relectura persistida y evidencia del build desplegado.

## 7. Estado de verificación al escribir este documento

- Análisis de repositorios y persistencia: realizado para diseñar esta unidad.
- Código en rama: en implementación.
- Pruebas/CI de esta rama: pendientes de ejecución por GitHub Actions.
- PR: pendiente de abrir al completar el conjunto de cambios.
- Merge/despliegue: no ejecutados.
- Evidencia productiva F15: no disponible aún y no se declara.
