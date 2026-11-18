from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.camera import Camera
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.utils import platform
from kivymd.uix.boxlayout import MDBoxLayout
from PIL import Image as PillowImage


class RequestPhotos:
    def _show_request_photo(self, request_id: str, photo_path: str) -> None:
        try:
            self.service.get(request_id)
            if not Path(photo_path).is_file():
                raise ValueError("No encontramos el archivo de la foto.")
            image = Image(
                source=photo_path, allow_stretch=True, keep_ratio=True,
            )
        except (OSError, ValueError) as error:
            self._show_dialog("No se pudo abrir la foto", str(error))
            return
        popup = Popup(
            title=f"Foto de {request_id}", content=image,
            size_hint=(0.9, 0.8),
        )
        popup.open()

    def _store_photo(self, source_path: str) -> str:
        source = Path(source_path)
        if source.suffix.casefold() not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise ValueError("Elige una imagen JPG, PNG o WEBP.")
        if not source.is_file() or source.stat().st_size == 0:
            raise ValueError("No se pudo leer el archivo de imagen seleccionado.")
        destination_dir = Path(self.user_data_dir) / "request_photos"
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / f"{uuid4().hex}{source.suffix.lower()}"
        shutil.copy2(source, destination)
        try:
            with PillowImage.open(destination) as image:
                image.verify()
                image_format = image.format
        except (OSError, SyntaxError) as error:
            destination.unlink(missing_ok=True)
            raise ValueError("El archivo seleccionado no es una imagen válida.") from error
        if image_format not in {"JPEG", "PNG", "WEBP"}:
            destination.unlink(missing_ok=True)
            raise ValueError("Elige una imagen JPG, PNG o WEBP.")
        return str(destination)

    def _set_selected_photo(self, source_path: str) -> bool:
        previous_photo = self.selected_photo_path
        try:
            stored_photo = self._store_photo(source_path)
        except (OSError, ValueError) as error:
            self._show_dialog("No se pudo adjuntar la foto", str(error))
            return False
        self.selected_photo_path = stored_photo
        if (previous_photo and previous_photo != self.editing_original_photo
                and previous_photo != stored_photo):
            self._remove_stored_photo(previous_photo)
        citizen = self.root.ids.screen_manager.get_screen("citizen")
        citizen.ids.photo_status.text = (
            "Foto seleccionada correctamente"
        )
        citizen.ids.photo_preview.source = self.selected_photo_path
        citizen.ids.photo_preview_card.height = dp(150)
        citizen.ids.photo_preview_card.opacity = 1
        citizen.ids.photo_preview_card.disabled = False
        return True

    def choose_request_photo(self) -> None:
        if platform == "android":
            self._choose_android_request_photo()
            return

        if platform not in {"android", "ios"}:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            initial_dir = Path.home() / "Pictures"
            if not initial_dir.is_dir():
                initial_dir = Path.home() / "Downloads"
            if not initial_dir.is_dir():
                initial_dir = Path.home()
            try:
                selection = filedialog.askopenfilename(
                    parent=root,
                    title="Selecciona una foto",
                    initialdir=str(initial_dir),
                    filetypes=[
                        ("Imágenes", "*.jpg *.jpeg *.png *.webp"),
                        ("Todos los archivos", "*.*"),
                    ],
                )
            finally:
                root.destroy()
            if selection:
                self._set_selected_photo(selection)
            return

        chooser = FileChooserListView(
            path=str(Path.home()),
            filters=["*.jpg", "*.jpeg", "*.png", "*.webp"],
            multiselect=False,
        )
        select_button = self._button("Usar foto seleccionada", lambda: None)
        cancel_button = self._button("Cancelar", lambda: None, style="text")
        actions = MDBoxLayout(
            orientation="horizontal", spacing=dp(8),
            size_hint_y=None, height=dp(48),
        )
        actions.add_widget(cancel_button)
        actions.add_widget(select_button)
        content = MDBoxLayout(
            orientation="vertical", spacing=dp(8), padding=dp(8),
        )
        content.add_widget(chooser)
        content.add_widget(actions)
        popup = Popup(
            title="Elige una foto", content=content,
            size_hint=(0.95, 0.9),
        )
        cancel_button.bind(on_release=lambda *_args: popup.dismiss())
        select_button.bind(on_release=lambda *_args: self._select_request_photo(
            popup, chooser.selection,
        ))
        popup.open()

    def _choose_android_request_photo(self) -> None:
        if getattr(self, "_android_photo_request_code", None) is not None:
            return

        try:
            from android import activity, mActivity
            from jnius import JavaException, autoclass
        except ImportError as error:
            self._show_dialog(
                "Selector no disponible",
                f"No se pudo iniciar el selector de Android: {error}",
            )
            return

        intent_class = autoclass("android.content.Intent")
        intent = intent_class(intent_class.ACTION_OPEN_DOCUMENT)
        intent.addCategory(intent_class.CATEGORY_OPENABLE)
        intent.setType("image/*")
        intent.addFlags(intent_class.FLAG_GRANT_READ_URI_PERMISSION)
        request_code = 48127
        self._android_photo_request_code = request_code
        activity.bind(on_activity_result=self._on_android_photo_result)
        try:
            mActivity.startActivityForResult(intent, request_code)
        except JavaException as error:
            activity.unbind(on_activity_result=self._on_android_photo_result)
            self._android_photo_request_code = None
            self._show_dialog(
                "Selector no disponible",
                f"No se pudo abrir la selección de imágenes: {error}",
            )

    def _on_android_photo_result(
        self, request_code: int, result_code: int, data,
    ) -> None:
        if request_code != self._android_photo_request_code:
            return

        from android import activity
        from jnius import JavaException, autoclass

        activity.unbind(on_activity_result=self._on_android_photo_result)
        self._android_photo_request_code = None
        if data is None or result_code != autoclass(
            "android.app.Activity",
        ).RESULT_OK:
            return
        uri = data.getData()
        if uri is None:
            self._show_dialog(
                "No se seleccionó una imagen",
                "El selector no devolvió una foto. Inténtalo otra vez.",
            )
            return

        temporary_path = None
        try:
            temporary_path = self._copy_android_photo(uri)
            self._set_selected_photo(str(temporary_path))
        except (JavaException, OSError, ValueError) as error:
            self._show_dialog("No se pudo adjuntar la foto", str(error))
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def _copy_android_photo(self, uri) -> Path:
        from android import mActivity
        from jnius import autoclass

        resolver = mActivity.getContentResolver()
        mime_type = str(resolver.getType(uri) or "").split(";", 1)[0].strip().lower()
        suffix = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }.get(mime_type)
        if suffix is None:
            raise ValueError("Elige una imagen JPG, PNG o WEBP.")

        destination_dir = Path(self.user_data_dir)
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / f"{uuid4().hex}{suffix}"
        input_stream = resolver.openInputStream(uri)
        if input_stream is None:
            raise OSError("No se pudo leer la imagen seleccionada.")
        output_stream = None
        copied_successfully = False
        try:
            try:
                output_stream = autoclass("java.io.FileOutputStream")(
                    str(destination),
                )
                channels = autoclass("java.nio.channels.Channels")
                source_channel = channels.newChannel(input_stream)
                destination_channel = output_stream.getChannel()
                offset = 0
                while True:
                    copied = destination_channel.transferFrom(
                        source_channel, offset, 1024 * 1024,
                    )
                    if copied <= 0:
                        break
                    offset += copied
            finally:
                try:
                    if output_stream is not None:
                        output_stream.close()
                finally:
                    input_stream.close()
            if not destination.is_file() or destination.stat().st_size == 0:
                raise OSError("No se pudo copiar la imagen seleccionada.")
            copied_successfully = True
            return destination
        finally:
            if not copied_successfully:
                destination.unlink(missing_ok=True)

    def _select_request_photo(self, popup: Popup, selection: list[str]) -> None:
        if not selection:
            self._show_dialog("Falta seleccionar", "Selecciona una foto antes de continuar.")
            return
        if self._set_selected_photo(selection[0]):
            popup.dismiss()

    def take_request_photo(self) -> None:
        if platform == "android":
            try:
                from android.permissions import Permission, request_permissions
                from jnius import JavaException
            except ImportError as error:
                self._show_dialog(
                    "Permiso de cámara no disponible",
                    f"No se pudo solicitar el permiso de Android: {error}",
                )
                return
            try:
                request_permissions(
                    [Permission.CAMERA], self._on_camera_permission_result,
                )
            except JavaException as error:
                self._show_dialog(
                    "No se pudo solicitar el permiso",
                    f"Android no pudo solicitar acceso a la cámara: {error}",
                )
            return
        self._open_request_camera()

    def _on_camera_permission_result(self, _permissions, grants) -> None:
        if len(grants) != 1 or not grants[0]:
            self._show_dialog(
                "Permiso de cámara denegado",
                "Autoriza el uso de la cámara para tomar la foto de la solicitud.",
            )
            return
        Clock.schedule_once(lambda _dt: self._open_request_camera(), 0)

    def _open_request_camera(self) -> None:
        try:
            camera = Camera(
                play=True, resolution=(1280, 720),
                size_hint=(1, 1),
            )
        except (AttributeError, OSError, RuntimeError, ValueError) as error:
            self._show_dialog(
                "Cámara no disponible",
                f"No se pudo iniciar la cámara: {error}",
            )
            return
        capture_button = self._button("Tomar foto", lambda: None)
        cancel_button = self._button("Cancelar", lambda: None, style="text")
        actions = MDBoxLayout(
            orientation="horizontal", spacing=dp(8),
            size_hint_y=None, height=dp(48),
        )
        actions.add_widget(cancel_button)
        actions.add_widget(capture_button)
        content = MDBoxLayout(
            orientation="vertical", spacing=dp(8), padding=dp(8),
        )
        content.add_widget(camera)
        content.add_widget(actions)
        popup = Popup(
            title="Tomar foto de las ramas", content=content,
            size_hint=(0.95, 0.85),
        )
        cancel_button.bind(on_release=lambda *_args: popup.dismiss())
        capture_button.bind(on_release=lambda *_args: self._capture_request_photo(
            camera, popup,
        ))
        popup.bind(on_dismiss=lambda *_args: setattr(camera, "play", False))
        popup.open()

    def _capture_request_photo(self, camera: Camera, popup: Popup) -> None:
        if not camera.texture:
            self._show_dialog(
                "Cámara no lista",
                "Espera a que aparezca la imagen de la cámara e inténtalo de nuevo.",
            )
            return
        temporary = Path(self.user_data_dir) / f"{uuid4().hex}.png"
        try:
            temporary.parent.mkdir(parents=True, exist_ok=True)
            camera.texture.save(filename=str(temporary), flipped=False)
            if not temporary.is_file() or temporary.stat().st_size == 0:
                raise OSError("La cámara no generó un archivo de imagen.")
            if not self._set_selected_photo(str(temporary)):
                return
        except (OSError, RuntimeError, ValueError) as error:
            self._show_dialog("No se pudo tomar la foto", str(error))
            return
        finally:
            temporary.unlink(missing_ok=True)
        if self.selected_photo_path:
            popup.dismiss()
