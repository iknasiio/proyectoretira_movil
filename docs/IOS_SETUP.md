# Preparar Rama para iPhone

La app usa Kivy y comparte parte del código entre plataformas, pero por ahora
solo se genera el paquete Android: el APK/AAB de Buildozer no funciona en
iPhone. Generar y firmar una app para iPhone requiere macOS y Xcode; este equipo
Windows no puede producir ni probar un IPA directamente.

## Requisitos

- macOS 11.6 o posterior y Xcode 13.2.1 o posterior.
- Homebrew y las herramientas de línea de comandos de Xcode.
- Un Apple ID configurado en Xcode para ejecutar en un iPhone. Publicar mediante
  TestFlight o App Store requiere una cuenta de desarrollador de Apple.

Instala las dependencias del sistema una vez:

```bash
brew install autoconf automake libtool pkg-config
brew link libtool
xcode-select --install
```

## Generar el proyecto Xcode

Desde la raíz del repositorio:

```bash
bash scripts/prepare_ios.sh
```

El script compila Python, Kivy y Pillow con Kivy-iOS, instala las dependencias
Python puras de `requirements-ios.txt` y crea
`~/Rama-ios-build/Rama-ios/Rama.xcodeproj`. El código fuente se copia a una
carpeta aislada de preparación para no incluir las pruebas, el entorno virtual
ni los artefactos de Android. También excluye `json/email_settings.json`,
que puede contener credenciales SMTP locales y nunca debe empaquetarse dentro
de una app móvil.

Abre el proyecto en Xcode:

```bash
open "$HOME/Rama-ios-build/Rama-ios/Rama.xcodeproj"
```

En el target de la app:

1. En **Signing & Capabilities**, selecciona el equipo de desarrollo para
   firmar y ejecutar en el iPhone, y configura un identificador de paquete
   único, por ejemplo `io.github.iknasiio.rama`.
2. En **Info**, agrega **Privacy - Camera Usage Description**
   (`NSCameraUsageDescription`) con el texto: “Rama necesita la cámara para
   adjuntar una foto de las ramas a la solicitud.”
3. Selecciona el iPhone conectado como destino y presiona **Run**.

La cámara debe probarse en un dispositivo real y aceptar el permiso del
sistema. La selección de archivos en iOS usa el selector Kivy y debe probarse
por separado para confirmar el acceso a las fotos que el usuario desea adjuntar.
Si la app se cierra al iniciar, revisa la consola de Xcode y comparte el primer
traceback; no basta con el mensaje de cierre.
