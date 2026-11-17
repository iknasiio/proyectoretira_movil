[app]

title = Rama
package.name = rama
package.domain = io.github.iknasiio
source.dir = .
source.include_exts = py,kv,png,json
source.exclude_dirs = .venv, __pycache__, .git, capturas, docs, p4a-recipes, scripts, tests
source.exclude_patterns = test_*.py,capturar_pantallas.py,app/config/email_settings.json
version = 0.1.0
requirements = python3,kivy==2.3.1,kivymd==2.0.0,materialyoucolor==3.0.4,materialshapes==0.3,asynckivy==0.6.4,asyncgui==0.6.3,requests==2.34.2,pillow
orientation = portrait
fullscreen = 0
icon.filename = assets/rama_icon.png

android.api = 36
android.minapi = 24
android.ndk = 28c
android.archs = arm64-v8a
android.permissions = CAMERA, INTERNET
android.allow_backup = False
android.debug_artifact = apk
android.release_artifact = aab
p4a.local_recipes = p4a-recipes
