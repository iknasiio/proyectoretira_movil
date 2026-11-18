# Documentación técnica de Rama

## 1. Descripción del proyecto

Rama es una aplicación móvil desarrollada en Kivy/KivyMD para apoyar la gestión municipal de retiro de ramas y restos de poda acumulados frente a viviendas. La solución está pensada como demostración de una experiencia real de servicio público, con roles de ciudadano, administración y trabajador.

La aplicación permite:

- registro e inicio de sesión por usuario y rol;
- creación y edición de solicitudes con fotografía y ubicación;
- revisión, aceptación y asignación por parte de administración;
- trabajo de campo para trabajadores asignados;
- persistencia local de datos en formato JSON;
- dashboard con indicadores y análisis por periodo;
- configuración remota con valor por defecto para seguir operando sin conexión.

## 2. Arquitectura

El proyecto mantiene una separación clara entre capas de presentación, lógica y datos:

- `app/main.py`: inicialización y coordinación general de la aplicación.
- `app/ui/auth.py`: inicio de sesión, registro y recuperación de contraseña.
- `app/ui/dashboard.py`: métricas, gráficas y actualización del dashboard.
- `app/ui/request_views.py`, `request_actions.py` y `request_photos.py`: presentación y operaciones de solicitudes, separadas por responsabilidad.
- `app/ui/components.py`, `screens.py` y `kv_loader.py`: componentes comunes, clases de pantalla y carga ordenada de vistas.
- `app/kv/`: interfaz declarativa Kivy; contiene `components.kv`, `root.kv` y un archivo por pantalla.
- `app/request_service.py`: núcleo de negocio. Define los roles, validaciones, transiciones de estado, persistencia y reglas de acceso.
- `app/remote_config.py`: carga de configuración remota con validación y fallback local.
- `json/remote_config.json`: copia local de la configuración pública; se publica como `remote_config.json` en la raíz del repositorio remoto.
- `json/email_settings.example.json`: plantilla de configuración SMTP sin credenciales reales.
- `json/email_settings.json`: configuración SMTP local, excluida de Git; créala a partir de la plantilla y no compartas sus credenciales.
- `tests/`: pruebas automatizadas.

### Principios de diseño

- MVC/POO identificables: la lógica de negocio está encapsulada en `RequestService`; los controladores de `app/ui/` coordinan eventos y actualizaciones visuales, y las vistas están en `app/kv/`.
- Persistencia segura: los tres JSON se escriben primero en archivos temporales; si una sustitución falla, se restauran los archivos y el estado en memoria.
- Manejo de errores: si el archivo está corrupto o la configuración remota falla, la app mantiene funcionamiento local.
- UX orientada a móvil: los cards, notificaciones y filtros están diseñados para una gestión ágil desde un teléfono.

## 3. Flujo principal

1. El usuario entra a la app desde `LoginScreen`.
2. `RequestService.authenticate()` valida credenciales y devuelve el rol del usuario.
3. La pantalla correspondiente (`CitizenScreen`, `AdminScreen` o `WorkerScreen`) carga la información relevante.
4. Las solicitudes se crean o editan según validaciones de negocio.
5. Cuando cambia el estado, se actualiza el historial y la vista asociada.
6. La persistencia JSON guarda el estado para que la app siga operando tras reiniciar.

## 4. Datos y persistencia

En escritorio, los datos se pueden inspeccionar en `json/solicitudes.json`, `json/cuentas.json` y `json/trabajadores.json`. En Android/iOS esos tres archivos se guardan en el directorio privado de la aplicación (`App.user_data_dir`). El directorio `json/` local está excluido de Git y Buildozer no lo incluye en el paquete móvil. Al iniciar, la app migra un antiguo `rama_data.json` y lo elimina solo después de guardar correctamente los archivos nuevos.

- `solicitudes.json`: solicitudes de los ciudadanos;
- `cuentas.json`: cuentas de ciudadanos y administración;
- `trabajadores.json`: operadores y credenciales de acceso del equipo.

Cada archivo tiene una versión de esquema y `RequestService` valida su estructura. Si un archivo falta o está dañado, el inicio reporta el error en vez de reemplazar datos silenciosamente. Los guardados usan archivos temporales y restauran el estado anterior si falla una escritura.

## 5. Configuración remota

La app consulta una configuración remota en segundo plano para actualizar:

- el anuncio de bienvenida;
- la municipalidad asociada a la ruta de Google Maps.

Si no hay conexión o la respuesta no es válida, el sistema conserva `DEFAULT_REMOTE_CONFIG` y mantiene la demo operativa.

## 6. Dashboard y medición

El dashboard administrativo calcula indicadores clave a partir de las solicitudes y su cronología:

- total de solicitudes;
- solicitudes por estado;
- pendientes y completadas;
- tiempos promedio por etapa;
- distribución por barrio;
- carga de trabajo por colaborador;
- tendencia de creación y cierre en un periodo determinado.

Estos indicadores permiten aplicar el enfoque MJV App al problema de gestión municipal y justificar decisiones de mejora.

## 7. Validación y pruebas

El proyecto cuenta con pruebas automáticas para verificar:

- persistencia y rollbacks de errores;
- validación de JSON corrupto;
- flujo de autenticación por roles;
- transiciones de estado válidas e inválidas;
- validación de configuración remota.

Desde la raíz del proyecto:

```powershell
$env:KIVY_NO_ARGS = "1"
python -m unittest discover -v
```

## 8. Uso responsable y ética

La app es una demostración académica. Los datos son ficticios y sirven únicamente para evidenciar comportamiento funcional. Se recomienda tratarlos como información no real ni sensible. La declaración de uso de IA está en `USO_IA.md`.

## 9. Referencias rápidas

- [README](../README.md): guía de instalación y uso general.
- DOCUMENTATION.md: explicación técnica completa.
- [INFORME_FINAL.md](INFORME_FINAL.md): resumen de diagnóstico, métricas y propuesta final.
- [USO_IA.md](USO_IA.md): declaración honesta de uso de IA.
