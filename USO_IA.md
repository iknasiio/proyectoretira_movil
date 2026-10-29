# Declaración de uso de inteligencia artificial

## 1. IA usada

Se utilizó GitHub Copilot en Visual Studio Code como asistente de IA durante el desarrollo y la preparación de la documentación de Rama. La herramienta se usó para consultar, proponer y revisar; las decisiones y la responsabilidad por el proyecto corresponden al equipo.

## 2. Modelo

El nombre y la versión exactos del modelo utilizado durante todo el desarrollo no quedaron registrados por el equipo. Por honestidad, no se atribuye aquí un modelo específico. Si el historial de Copilot muestra esa información, el equipo debe agregar el nombre y la versión antes de entregar.

## 3. Prompts realizados

Entre las solicitudes relevantes, resumidas fielmente, estuvieron:

- Pedir ayuda para implementar o revisar el guardado y la recuperación de solicitudes y cuentas en JSON.
- Consultar cómo mostrar notificaciones cuando ocurren eventos de la aplicación y cómo leer una configuración remota con valores predeterminados.
- Solicitar pruebas y documentación para explicar la instalación, los módulos y el flujo de la aplicación.
- Comparar el proyecto y sus documentos con las instrucciones de evaluación para identificar faltantes.
- En esta revisión, preguntar si la aplicación cumplía la pauta y pedir ayuda para ejecutarla.

## 4. Outputs

La asistencia de IA contribuyó con propuestas y revisiones relacionadas con la persistencia JSON, las notificaciones locales, la consulta de configuración remota, las pruebas automatizadas y la documentación. El proyecto conserva estas funciones; por ejemplo, el guardado JSON valida los datos y maneja errores, y la configuración remota cuenta con valores predeterminados cuando la consulta falla. También se aclaró que las notificaciones son locales, no push, y que los datos incluidos son de demostración.

## 5. Ajustes

El equipo debe revisar y confirmar este apartado según el historial completo del trabajo. En el código actual, las decisiones visibles incluyen guardar los datos en el directorio privado de la aplicación, escribir el JSON mediante un archivo temporal antes de reemplazarlo, validar la configuración remota y conservar valores locales cuando no está disponible. La configuración remota se consulta en segundo plano para no bloquear el inicio de la interfaz. No se deben presentar las cuentas de prueba como cuentas seguras ni los datos ficticios como información obtenida de participantes reales.

## 6. Reflexión en el uso de IA

Completar con una reflexión propia del equipo antes de entregar: qué parte de la asistencia les resultó útil, qué tuvieron que comprobar o corregir y qué aprendieron al entender y probar el código. No presentar una reflexión generada por IA como experiencia personal del equipo.

## Revisión y responsabilidad del equipo

Antes de entregar, todas las personas integrantes deben confirmar que esta declaración refleja el uso real de IA en el proyecto, completar los datos que puedan verificar y ser capaces de explicar el código. Las pruebas automatizadas no equivalen a una validación con usuarios ni con el socio comunitario. La responsabilidad por el código, los datos, las pruebas, las decisiones y la presentación final corresponde al equipo.
