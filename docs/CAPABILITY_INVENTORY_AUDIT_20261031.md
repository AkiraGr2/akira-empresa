# Inventario histórico y evidencia — 2026-10-31

Se recuperan los 60 elementos de `renderLevels` del frontend histórico 74e7641 y se añaden seis superficies identificadas en el código actual. Son elementos de interfaz/producto, no 66 contratos independientes ni 66 funciones certificadas. F5 y F11 comparten contrato. El registro principal conserva su estado persistente y permisos.

## Hallazgos

- Administración imponía mínimo 15 y sustituía cero verificadas por 15; además una búsqueda parcial aceptaba `unverified` como verificado. Corregido en el frontend compañero.
- El catálogo raíz contiene 17 definiciones; el total persistido en producción debe consultarse con sesión propietaria. No inferirlo del catálogo.
- E7 (WCAG) y E10 (tests) mostraban resultados exitosos fabricados. Se retiran esas afirmaciones; siguen pendientes motores reales.
- E9 es un simulador educativo, no una shell real.
- Localizar un módulo no acredita su ejecución completa. Ningún estado de contrato se hereda automáticamente a estas funciones.
- Las seis adiciones son acceso y superficies de Trading Lab; no acreditan rentabilidad, conexión MT5 ni ejecución en broker.

## Matriz de trazabilidad

| ID | Elemento | Código localizado | Evidencia de implementación |
|---|---|---|---|
| V1 | Chat Cognitivo | frontend/js/akira_conversations.js | source_located |
| V2 | Colmena Compartida | frontend/js/hybrid_sync.js | source_located |
| V3 | Búsqueda y Razonamiento | frontend/js/akira_live_web.js | source_located |
| V4 | Streaming AUTO | frontend/js/akira_conversations.js | source_located |
| V5 | Visión Multimodal | frontend/js/akira_extras.js | source_located |
| V6 | Auto-Repair | frontend/js/akira_self_healing.js | source_located |
| V7 | PDF Local & Documentos | frontend/js/akira_extras.js | source_located |
| V8 | Akira Live: voz | frontend/js/akira_voice_live.js | source_located |
| F5 | Autoconocimiento persistente | frontend/js/akira_admin.js | source_located |
| F6 | Cerebro y aprendizaje | frontend/js/akira_learning.js | source_located |
| F7 | Proceso cognitivo persistente | frontend/js/akira_cognitive_ui.js | source_located |
| F8 | Herramientas de Akira | frontend/js/akira_admin.js | source_located |
| F9 | Agentes y colmena táctica | frontend/js/akira_hive_catalog.js | source_located |
| F10 | Mission Engine + Conversaciones | frontend/js/akira_missions_panel.js | source_located |
| F11 | Self-knowledge / Autoconocimiento | frontend/js/akira_admin.js | source_located |
| F12 | Self-Repair / Reparación | frontend/js/akira_self_healing.js | source_located |
| F13 | Evolution / Evolución | frontend/js/akira_autonomous_evolution.js | source_located |
| F14 | Controlled Autonomy / Autonomía | frontend/js/akira_admin.js | source_located |
| F15 | Hive Collective Sync & Colmena Táctica | frontend/js/akira-hive-office-v1.js | source_located |
| F16 | Hive Agent Orchestration & Router | frontend/js/akira_hive_catalog.js | source_located |
| F17 | Voice VAD & Push-to-Talk Callejero | frontend/js/akira_voice_live.js | source_located |
| F18 | Upwork Bidding Autonomous Engine | frontend/js/akira_monetization.js | source_located |
| F19 | Cerebro y grafo 2D | frontend/js/obsidian_membrane.js | source_located |
| F20 | Autonomous Active Supervisor | frontend/js/akira_missions_modern.js | source_located |
| P1 | Sandbox & Live Artifacts Preview | frontend/js/akira_sandbox.js | source_located |
| P2 | Radar Tecnológico & Ingesta Continua | frontend/js/akira_knowledge_pipeline.js | source_located |
| P3 | Swarm Multi-Agent Collaboration | frontend/js/akira_hive_catalog.js | source_located |
| P4 | 1-Click Project ZIP & GitHub Export | frontend/js/akira_sandbox.js | source_located |
| M1 | Consola Python REPL WebAssembly | frontend/js/akira_python_repl.js | source_located |
| M2 | Búsqueda Semántica Vectorial Local | frontend/js/akira_search_vector.js | source_located |
| M3 | Cron & Automatizaciones Programadas | frontend/js/akira_cron_scheduler.js | source_located |
| M4 | Pipeline CRM Freelance & Facturación | frontend/js/akira_crm_pipeline.js | source_located |
| M5 | Dashboards & Gráficas Visuales en Vivo | frontend/js/akira_data_viz.js | source_located |
| M6 | Escudo de Auditoría & Seguridad de Código | frontend/js/akira_security_shield.js | source_located |
| M7 | Exportador de Memoria a Bóveda Obsidian | frontend/js/akira_obsidian_vault.js | source_located |
| M8 | Estudio de Voz Situacional & Manos Libres | frontend/js/akira_voice_studio.js | source_located |
| M9 | Motor de Hojas de Cálculo & Data Wrangler | frontend/js/akira_spreadsheet.js | source_located |
| M10 | Simulador de Pruebas Web & Auditoría UX | frontend/js/akira_ux_tester.js | source_located |
| M11 | Modo Offline Resiliente PWA & IndexedDB | frontend/js/akira_offline_pwa.js | source_located |
| L4 | Motor Proactivo J.A.R.V.I.S. (Nivel 4) | frontend/js/akira_admin.js | source_located |
| M12 | Vigilante de Auto-Curación Técnica | frontend/js/akira_self_healing.js | source_located |
| M13 | Probador de APIs REST & Servidor Mock | frontend/js/akira_api_tester.js | source_located |
| M14 | Estudio de Temas & Accesibilidad WCAG | frontend/js/akira_theme_studio.js | source_located |
| M15 | Constructor Visual de Agentes (Colmena Studio) | frontend/js/akira_agent_studio.js | source_located |
| M16 | Mapa de Calor de Productividad & ROI | frontend/js/akira_roi_tracker.js | source_located |
| M17 | Motor de Conexión Web en Tiempo Real | frontend/js/akira_live_web.js | source_located |
| T1 | Telegram: suite ejecutiva | backend/telegram_service.py | source_located |
| T2 | Doble Motor de Transcripción Multimodal | backend/telegram_service.py | source_located |
| T3 | Facturación Proforma & Minutas en PDF | backend/telegram_service.py | source_located |
| T4 | Sincronización Web ⟷ Telegram | backend/telegram_service.py | source_located |
| E1 | Arquitectura & Diagramas Mermaid en Vivo | frontend/js/akira_software_lab.js | source_located |
| E2 | Laboratorio SQL & Base de Datos In-Browser (SQLite WASM) | frontend/js/akira_software_lab.js | source_located |
| E3 | Generador de Blueprints Full-Stack & Boilerplates | frontend/js/akira_software_lab.js | source_located |
| E4 | Auditor Estático Clean Code & Principios SOLID | frontend/js/akira_software_lab.js | source_located |
| E5 | Diseñador OpenAPI 3.0 & Simulador Swagger | frontend/js/akira_software_lab.js | source_located |
| E6 | Laboratorio Regex & Tokenizador de Código (AST) | frontend/js/akira_software_lab.js | source_located |
| E7 | Auditor Sintético WCAG AAA & SEO de Alto Rendimiento | frontend/js/akira_software_lab.js | placeholder |
| E8 | Transformador Políglota de Estructuras de Datos | frontend/js/akira_software_lab.js | source_located |
| E9 | Terminal Virtual Shell & Simulador CLI (Bash/Git) | frontend/js/akira_software_lab.js | simulation |
| E10 | Laboratorio de Pruebas Unitarias Automatizadas | frontend/js/akira_software_lab.js | placeholder |
| N1 | Acceso con sesión y usuarios permitidos | backend/akira_auth.py | source_located |
| N2 | Trading Lab: precios Deriv y reconexión | frontend/js/akira_trading_lab.js | source_located |
| N3 | Trading Lab: simulador local | frontend/js/akira_trading_lab.js | source_located |
| N4 | Escáner estructural y armónico | frontend/js/akira_trading_scanner_core.js | source_located |
| N5 | Scalping por tipo de mercado | frontend/js/akira_scalp_research_core.js | source_located |
| N6 | Chulito de referencia Step/oro | frontend/js/akira_reference_scanner.js | source_located |

## Pendiente

Pruebas funcionales individuales autenticadas y dependencias externas para cada elemento. Este cambio corrige inventario y afirmaciones, no declara cerrada esa auditoría integral. Sin cambios de esquema ni alteración del registro persistido.
