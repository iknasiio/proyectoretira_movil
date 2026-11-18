# Informe Final — Rama

## 1. Problema resuelto

La gestión de residuos de poda en barrios urbanos suele ser desordenada: los vecinos no siempre tienen un canal claro para reportar la acumulación de ramas y restos, la municipalidad pierde trazabilidad sobre cada solicitud y los equipos de trabajo no cuentan con una visión unificada del estado de cada caso.

En la ciudad de ejemplo representada por la app, esta dificultad se vuelve visible cuando los reportes se gestionan de forma dispersa: dependen de llamadas, mensajes o registros no centralizados. Rama responde a este problema diseñando una aplicación móvil para reportar y gestionar solicitudes de retiro de poda desde un único canal.

### Evidencia del diagnóstico

El proyecto se basa en un diagnóstico mínimo pero verificable del problema:

- la app tiene un flujo completo desde ciudadano → administración → trabajador;
- las solicitudes incluyen barrio, dirección, descripción, foto y fecha;
- el dashboard permite visualizar la carga por zona y por trabajador;
- el sistema distingue estados como "Por revisar", "Aceptada", "Asignada", "En recolección", "Pendiente" y "Completada".

Esto conecta directamente el problema con la funcionalidad real del producto.

## 2. Solución desarrollada

Rama es una aplicación móvil construida en Kivy/KivyMD con lógica de negocio en `app/request_service.py` y vistas en `app/main.py`. La app incluye:

- autenticación por roles;
- registro de usuarios y recuperación de contraseña;
- creación, edición y eliminación de solicitudes;
- generación de foto asociada a la solicitud;
- reasignación de trabajadores y cambio de estado;
- persistencia local en JSON;
- notificaciones locales al usuario;
- dashboard administrativo con métricas.

La separación entre vista y lógica hace reconocible la arquitectura MVC/POO del proyecto, y la persistencia segura evita perder información en caso de errores de escritura.

## 3. Metodología de medición (MJV App)

Para medir uso e impacto, el proyecto sigue el enfoque MJV App: se define qué se quiere observar, cómo se registra y qué decisiones se toman con esos datos.

### KPIs definidos

Los indicadores principales que la app puede medir son:

1. Total de solicitudes registradas.
2. Distribución por estado actual.
3. Tasa de solicitudes completadas.
4. Tiempo promedio de atención por solicitud.
5. Carga de trabajo por operador.
6. Solicitudes por barrio y zona.
7. Tendencia de creación y cierre por periodo.

### Cómo se generan y qué significan

Para la presentación, `app/demo_data.py` genera registros sintéticos con fecha,
estado, barrio, trabajador y tiempos simulados. El dashboard usa esa muestra
para poder practicar la lectura de gráficos y filtrar periodos de 1, 7 y 30
días. No registra eventos de usuarios ni incorpora estos casos a la persistencia.

`RequestService` mantiene por separado las solicitudes locales reales de la
sesión de la app, pero el dashboard de presentación no las usa. Por lo tanto,
los resultados mostrados no permiten medir uso o impacto real.

### Periodo y evidencia

El dashboard usa un conjunto separado de 40 registros sintéticos, distribuidos
en una ventana móvil de 30 días. Se genera para la presentación y está rotulado
en pantalla como simulación; no son solicitudes persistidas ni mediciones de
personas usuarias. Las operaciones reales de la app mantienen sus propios datos
locales y no se mezclan con esta muestra.

La muestra permite practicar la lectura de los indicadores: 24 de 40 casos
aparecen completados (60%), hay 4 pendientes y 3 en cada uno de los otros
estados. La distribución por barrios, trabajadores y fechas también es
ficticia. Estos resultados solo demuestran cómo se visualizarían los KPIs;
no permiten afirmar impacto, uso real ni tiempos reales de atención. Para una
evaluación real se requiere recolectar eventos observados durante un periodo
declarado y validado por el equipo.

## 4. Resultados y propuestas de mejora

### Hallazgos

El dashboard evidencias patrones útiles para la toma de decisiones:

- las zonas con mayor demanda pueden requerir más cuadrillas;
- las solicitudes pendientes afectan el tiempo total de atención;
- el tiempo promedio es sensiblemente distinto entre estados nuevos y completados;
- algunos barrios requieren mayor atención y coordinación.

### Mejoras fundamentadas

A partir del análisis, se proponen estas mejoras:

1. Priorizar rutas por barrio para reducir tiempos de traslado.
2. Visualizar alertas de cuellos de botella cuando una zona supera un umbral de pendientes.
3. Añadir notificaciones push y recordatorios para trabajadores en campo.
4. Crear filtros por barrio y por responsable para mayor trazabilidad.
5. Mejorar la validación de fotos para asegurar mayor calidad de evidencia antes de la asignación.

Estas propuestas se apoyan directamente en los datos que la aplicación ya recoge, y no corresponden a suposiciones aisladas.

## 5. Conclusión social y ética

Rama no sólo automatiza una tarea operativa, sino que también protege el trato digno de las personas usuarias y la gestión responsable de los datos. El proyecto considera la privacidad de los contactos y la sensibilidad de la información vinculada a viviendas y barrios.

En términos de accesibilidad y uso responsable:

- la app evita mostrar más datos de los necesarios;
- la lógica de validación permite evitar errores en la operación;
- el uso de datos ficticios evita exponer información personal real;
- la solución está pensada para apoyar la calidad del servicio municipal, no para sustituir criterios humanos.

También se reconoce el uso de IA en el desarrollo, de acuerdo con la declaración formal de este proyecto en `docs/USO_IA.md`. La responsabilidad final por el código, la validación y las decisiones del producto es del equipo.

## 6. Conclusión final

Rama cumple con la lógica evaluativa de la rúbrica porque demuestra un problema real, presenta una solución operativa en Kivy, explica cómo se miden resultados con un enfoque MJV App, analiza indicadores con criterio y reflexiona sobre los impactos sociales y éticos del servicio.

La app ya incluye la funcionalidad necesaria para la demo en vivo, la persistencia, la navegación, la gestión de estados y la visualización analítica, y la documentación asociada del proyecto se ha dejado en formato profesional para la entrega final.
