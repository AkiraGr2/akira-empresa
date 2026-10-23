# Aprendizaje autónomo por solicitud explícita

**Estado:** implementado en la rama `codex/learning-autonomy`; aún no desplegado.

## Qué puede hacer Akira

Cuando la propietaria escribe en el chat una instrucción clara como «Akira, aprende sobre desarrollo web a nivel senior», el backend crea un registro privado, busca fuentes, pide una evaluación al modelo y guarda un resumen como conocimiento reutilizable solo si la evaluación lo considera respaldado por al menos dos dominios independientes y una confianza mínima de 0,85. Ese ciclo no necesita una aprobación humana por cada aprendizaje.

Los estudios débiles o con pocas fuentes permanecen como candidatos privados y no entran en la memoria activa. El aprendizaje queda en el historial con sus fuentes, la evaluación y el estado. No modifica código, GitHub, permisos, datos compartidos ni infraestructura. Las búsquedas y evaluaciones usan los proveedores configurados y pueden consumir sus cuotas o generar cargos según esas cuentas.

## Supervisión y retiro

La propietaria puede revisar los registros desde el control de aprendizaje existente. Para retirar un estudio consolidado del recuerdo activo, se puede escribir «Akira, olvida el aprendizaje learn_…» con el identificador devuelto al terminar el estudio. El sistema cambia el registro a obsoleto y archiva su memoria y nodos asociados; conserva el registro y la evidencia en el historial.

## Límites

- El inicio es por solicitud explícita; Akira no inventa temas para estudiar ni ejecuta una agenda autónoma en segundo plano.
- La investigación actual usa resultados y fragmentos devueltos por la búsqueda web configurada. No equivale a leer un curso completo ni certifica un nivel profesional.
- La evaluación automática puede equivocarse. La confianza es una señal del modelo, no una garantía matemática; la propietaria puede retirar el resultado.
- La ruta requiere sesión autenticada de la propietaria y persistencia disponible.
- Antes de habilitarla en producción deben pasar CI, revisión del cambio y despliegue. Esta rama local todavía no cambia Render ni Supabase.

## Criterios verificables

`persistence/test_autonomous_study.py` cubre la detección de instrucciones explícitas, la exigencia de dos dominios distintos, el umbral de evidencia, la privacidad, la promoción sin aprobación evento por evento y el retiro del recuerdo activo.
