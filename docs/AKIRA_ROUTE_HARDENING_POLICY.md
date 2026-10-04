# AKIRA — Route Hardening Policy

## Regla permanente

Una ruta de AKIRA no se considera completa cuando solamente responde correctamente.

Toda superficie que toque identidad, memoria, aprendizaje, conocimiento, autoconocimiento,
grafo, ciclos cognitivos, agentes, tareas, misiones, conversaciones o datos persistentes
debe cerrar el ciclo completo:

**ANALIZAR → VERIFICAR → AUDITAR → CORREGIR → PROBAR → VERIFICAR NUEVAMENTE**

## Qué significa 'ruta completa'

1. Autorización: identidad derivada del servidor; nunca del cliente.
2. Aislamiento: el propietario solo puede leer/modificar sus propios datos.
3. Validación: tipos, límites, valores permitidos e identificadores.
4. Persistencia: transacciones, control de versiones e idempotencia cuando aplique.
5. Auditoría: acciones sensibles deben dejar trazabilidad sin secretos.
6. Errores: respuestas seguras, sin credenciales, SQL, stacks ni detalles internos innecesarios.
7. Recuperación: timeouts, conflictos, reintentos seguros y estados de fallo explícitos.
8. Protección contra abuso: límites, concurrencia y coste cuando la operación lo requiera.
9. Pruebas: caso normal, no autenticado, no propietario, datos inválidos y fallo de dependencia.
10. Regresión: el CI debe impedir que una futura modificación quite una protección existente.

## Regla de aprendizaje y autoconocimiento

Ninguna entrada nueva pasa directamente a conocimiento reutilizable por el mero hecho de ser
recibida. El flujo debe conservar las barreras de candidato, evidencia, verificación,
consolidación, promoción y recall seguro.

## Regla de base de datos

Las tablas expuestas en `public` deben permanecer protegidas con RLS y una política que
refleje el modelo real de acceso. En AKIRA, las superficies persistentes son privadas para
clientes `anon` y `authenticated`; el backend es la frontera de acceso.

## Regla de despliegue

Después de una modificación de seguridad:

- verificar GitHub Actions;
- verificar el deploy de Render;
- verificar salud y persistencia;
- comprobar logs;
- volver a inspeccionar Supabase.

Un cambio de seguridad no se da por terminado por haber sido escrito: debe verificarse en producción.