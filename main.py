from __future__ import annotations

import shutil
import webbrowser
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.uix.camera import Camera
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.uix.spinner import Spinner
from kivy.uix.widget import Widget
from kivy.utils import platform
from kivy.utils import get_color_from_hex
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDButton, MDButtonText
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import (
    MDDialog,
    MDDialogButtonContainer,
    MDDialogContentContainer,
    MDDialogHeadlineText,
    MDDialogSupportingText,
)
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField, MDTextFieldHintText
from kivymd.uix.screen import MDScreen
from PIL import Image as PillowImage

from request_service import RequestService, STATUS_LABELS

FOREST = "#173E31"
MUTED = "#49564E"
INK = "#1C2E27"


class CitizenScreen(Screen):
    pass


class LoginScreen(Screen):
    pass


class AdminScreen(Screen):
    pass


class WorkerScreen(Screen):
    pass


class RamaRoot(MDScreen):
    pass


class RamaMobileApp(MDApp):
    def build(self):
        self.title = "Rama | Retiro de poda"
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "Green"
        if platform not in {"android", "ios"}:
            Window.size = (430, 850)
        self.service = RequestService()
        self.current_user = None
        self.selected_photo_path = ""
        self.editing_request_id = None
        self.editing_original_photo = ""
        Builder.load_file("rama.kv")
        return RamaRoot()

    def on_start(self):
        self.root.ids.screen_manager.current = "login"
        self.root.ids.nav_bar.height = 0
        self.root.ids.nav_bar.opacity = 0
        login = self.root.ids.screen_manager.get_screen("login")
        self._bind_enter_navigation(
            (login.ids.login_username, login.ids.login_password),
            self.sign_in,
        )
        citizen = self.root.ids.screen_manager.get_screen("citizen")
        self._bind_enter_navigation(
            (citizen.ids.address, citizen.ids.neighborhood, citizen.ids.details),
            self.submit_request,
        )

    @staticmethod
    def _bind_enter_navigation(
        fields: tuple[MDTextField, ...],
        on_last: Callable[[], None],
    ) -> None:
        for index, field in enumerate(fields):
            field.focus_next = fields[(index + 1) % len(fields)]
            if index + 1 < len(fields):
                next_field = fields[index + 1]
                field.bind(
                    on_text_validate=lambda _field, target=next_field:
                    setattr(target, "focus", True),
                )
            else:
                field.bind(
                    on_text_validate=lambda *_args: on_last(),
                )

    def navigate(self, screen_name: str) -> None:
        if not self.current_user:
            return
        role_screen = {"citizen": "citizen", "admin": "admin", "worker": "worker"}
        if role_screen.get(self.current_user["role"]) != screen_name:
            return
        self.root.ids.screen_manager.current = screen_name
        self.root.ids.session_user.text = self.current_user["name"]
        self.refresh_all()

    def sign_in(self) -> None:
        login = self.root.ids.screen_manager.get_screen("login")
        account = self.service.authenticate(
            login.ids.login_username.text,
            login.ids.login_password.text,
        )
        if not account:
            self._show_dialog("No se pudo iniciar sesión", "Revisa tu usuario y contraseña e inténtalo de nuevo.")
            return
        self.current_user = account
        role_screen = account["role"]
        self.root.ids.nav_bar.height = dp(64)
        self.root.ids.nav_bar.opacity = 1
        if role_screen == "citizen":
            citizen = self.root.ids.screen_manager.get_screen("citizen")
            citizen.ids.full_name.text = account["name"]
            citizen.ids.full_name.readonly = True
            citizen.ids.phone.text = account["phone"]
            citizen.ids.phone.readonly = True
            role_screen = "citizen"
        elif role_screen == "worker":
            worker = self.root.ids.screen_manager.get_screen("worker")
            worker.ids.worker_identity.text = account["name"]
        self.navigate(role_screen)

    def sign_out(self) -> None:
        self.current_user = None
        self.root.ids.screen_manager.current = "login"
        self.root.ids.screen_manager.get_screen("login").ids.login_password.text = ""
        self.root.ids.nav_bar.height = 0
        self.root.ids.nav_bar.opacity = 0

    def open_register(self) -> None:
        fields = MDBoxLayout(
            orientation="vertical", spacing=dp(11), padding=dp(12),
            size_hint_y=None, height=dp(390),
        )
        username = MDTextField(
            MDTextFieldHintText(text="Usuario"), mode="outlined",
            size_hint_y=None, height=dp(54),
        )
        name = MDTextField(
            MDTextFieldHintText(text="Nombre completo"), mode="outlined",
            size_hint_y=None, height=dp(54),
        )
        email = MDTextField(
            MDTextFieldHintText(text="Correo electrónico"), mode="outlined",
            size_hint_y=None, height=dp(54),
        )
        phone = MDTextField(
            MDTextFieldHintText(text="Número de teléfono"), mode="outlined",
            size_hint_y=None, height=dp(54),
        )
        password = MDTextField(
            MDTextFieldHintText(text="Contraseña"), mode="outlined",
            size_hint_y=None, height=dp(54), password=True,
        )
        confirm_password = MDTextField(
            MDTextFieldHintText(text="Confirmar contraseña"), mode="outlined",
            size_hint_y=None, height=dp(54), password=True,
        )
        fields.add_widget(username)
        fields.add_widget(name)
        fields.add_widget(email)
        fields.add_widget(phone)
        fields.add_widget(password)
        fields.add_widget(confirm_password)

        cancel_button = MDButton(MDButtonText(text="Cancelar"), style="text")
        save_button = MDButton(MDButtonText(text="Crear cuenta"), style="filled")
        button_container = MDDialogButtonContainer(
            Widget(), cancel_button, save_button, spacing=dp(8),
        )
        dialog = MDDialog(
            MDDialogHeadlineText(text="Registrar cuenta"),
            MDDialogSupportingText(text="Crea una cuenta ciudadana en este sistema local."),
            MDDialogContentContainer(
                fields, orientation="vertical", padding=(dp(16), dp(8)),
            ),
            button_container,
            size=(dp(410), dp(650)),
            size_hint=(None, None),
        )
        cancel_button.bind(on_release=lambda *_args: dialog.dismiss())
        save_button.bind(on_release=lambda *_args: self._save_registration(
            dialog, username, password, confirm_password, name, email, phone,
        ))
        self._bind_enter_navigation(
            (username, name, email, phone, password, confirm_password),
            lambda: self._save_registration(
                dialog, username, password, confirm_password, name, email, phone,
            ),
        )
        dialog.open()

    def _save_registration(self, dialog, username, password, confirm_password,
                            name, email, phone) -> None:
        if password.text != confirm_password.text:
            self._show_dialog(
                "Contraseña no coincidente",
                "Las dos contraseñas deben ser exactamente iguales.",
            )
            return
        try:
            account = self.service.register_account(
                username=username.text,
                password=password.text,
                name=name.text,
                email=email.text,
                phone=phone.text,
            )
        except ValueError as error:
            self._show_dialog("No se pudo registrar", str(error))
            return
        dialog.dismiss()
        self._show_dialog(
            "Cuenta creada",
            f"Hola {account['name']}. Ahora puedes iniciar sesión con {account['username']}.",
        )

    def open_recovery(self) -> None:
        username = MDTextField(
            MDTextFieldHintText(text="Usuario"), mode="outlined",
            size_hint_y=None, height=dp(64),
        )
        cancel_button = MDButton(MDButtonText(text="Cancelar"), style="text")
        recover_button = MDButton(MDButtonText(text="Recuperar"), style="filled")
        button_container = MDDialogButtonContainer(
            Widget(), cancel_button, recover_button, spacing=dp(8),
        )
        supporting_text = MDDialogSupportingText(
            text="Introduce el usuario de tu cuenta.",
        )
        supporting_text.size_hint_y = None
        supporting_text.height = dp(36)
        dialog = MDDialog(
            MDDialogHeadlineText(text="Recuperar contraseña"),
            supporting_text,
            MDDialogContentContainer(
                username, orientation="vertical",
                padding=(dp(16), dp(16)),
            ),
            button_container,
            size=(dp(410), dp(300)),
            size_hint=(None, None),
        )
        cancel_button.bind(on_release=lambda *_args: dialog.dismiss())
        recover_button.bind(on_release=lambda *_args: self._recover_password(
            dialog, username,
        ))
        self._bind_enter_navigation(
            (username,), lambda: self._recover_password(dialog, username),
        )
        dialog.open()

    def _recover_password(self, dialog, username) -> None:
        password = self.service.recover_password(username.text)
        dialog.dismiss()
        if password is None:
            self._show_dialog(
                "Usuario no encontrado",
                "No existe una cuenta con ese usuario en este sistema local.",
            )
            return
        self._show_dialog(
            "Contraseña recuperada",
            f"Tu contraseña es: {password}. Cambiála después de iniciar sesión.",
        )

    def _label(self, text: str, *, size: int = 15, color_hex: str = INK,
               height: int = 25, bold: bool = False) -> MDLabel:
        return MDLabel(
            text=text,
            size_hint_y=None,
            height=dp(height),
            font_size=dp(size),
            bold=bold,
            theme_text_color="Custom",
            text_color=get_color_from_hex(color_hex),
        )

    def _button(
        self,
        text: str,
        callback,
        *,
        style: str = "filled",
        background_color: str | None = None,
        text_color: str | None = None,
        theme_width: str = "Primary",
    ) -> MDButton:
        button = MDButton(
            style=style, theme_width=theme_width,
            size_hint=(1, None), height=dp(44),
        )
        if background_color:
            button.theme_bg_color = "Custom"
            button.md_bg_color = get_color_from_hex(background_color)
        button_text = MDButtonText(text=text, font_size=dp(14))
        if text_color:
            button_text.theme_text_color = "Custom"
            button_text.text_color = get_color_from_hex(text_color)
        button.add_widget(button_text)
        button.bind(on_release=lambda *_args: callback())
        return button

    def _show_dialog(self, title: str, message: str) -> None:
        for root_widget in Window.children:
            for widget in root_widget.walk():
                if isinstance(widget, MDTextField):
                    widget.focus = False
        close_button = MDButton(
            MDButtonText(text="Entendido"), style="text", size_hint=(None, None),
            width=dp(120), height=dp(44),
        )
        dialog = MDDialog(
            MDDialogHeadlineText(text=title),
            MDDialogSupportingText(text=message),
            MDDialogButtonContainer(Widget(), close_button, spacing=dp(8)),
        )
        close_button.bind(on_release=lambda *_args: dialog.dismiss())

        def dismiss_on_enter(_window, key, *_args):
            if key in {13, 271}:
                dialog.dismiss()
                return True
            return False

        dialog.bind(
            on_dismiss=lambda *_args: Window.unbind(
                on_keyboard=dismiss_on_enter,
            )
        )
        dialog.open()
        Clock.schedule_once(
            lambda _dt: Window.bind(on_keyboard=dismiss_on_enter)
            if dialog._is_open else None,
            0,
        )

    def refresh_all(self) -> None:
        if not hasattr(self, "service") or not self.root:
            return
        self.refresh_citizen()
        self.refresh_admin()
        self.refresh_worker()

    def refresh_citizen(self) -> None:
        if not self.root or "screen_manager" not in self.root.ids:
            return
        screen = self.root.ids.screen_manager.get_screen("citizen")
        container = screen.ids.citizen_requests
        container.clear_widgets()
        name = screen.ids.full_name.text.strip()
        requests = self.service.for_citizen(name)
        screen.ids.citizen_count.text = f"Mis solicitudes  ·  {len(requests)}"
        if not requests:
            container.add_widget(self._label(
                "Todavía no tienes solicitudes. Completa el formulario para empezar.",
                size=14, color_hex=MUTED, height=48,
            ))
        for request in requests:
            container.add_widget(self._request_card(request, citizen_actions=True))

    def refresh_admin(self) -> None:
        if not self.root or "screen_manager" not in self.root.ids:
            return
        screen = self.root.ids.screen_manager.get_screen("admin")
        container = screen.ids.admin_requests
        container.clear_widgets()
        pending = sum(item["status"] == "submitted" for item in self.service.requests)
        waiting = sum(item["status"] == "accepted" for item in self.service.requests)
        active = sum(
            item["status"] in {"assigned", "in_progress", "pending"}
            for item in self.service.requests
        )
        screen.ids.pending_count.text = str(pending)
        screen.ids.assign_count.text = str(waiting)
        screen.ids.active_count.text = str(active)
        worker_container = screen.ids.admin_workers
        worker_container.clear_widgets()
        workers = self.service.list_workers()
        if not workers:
            worker_container.add_widget(self._label(
                "No hay trabajadores registrados.", size=14,
                color_hex=MUTED, height=dp(32),
            ))
        for worker in workers:
            assigned_requests = self.service.for_worker(worker["name"])
            assignment_text = "Sin retiros activos"
            if assigned_requests:
                preview = [
                    f"{request['id']} · {request['address']}"
                    for request in assigned_requests[:2]
                ]
                assignment_text = (
                    "Asignado: " + " | ".join(preview)
                    + (" + más" if len(assigned_requests) > 2 else "")
                )
            worker_card = MDCard(
                style="outlined", orientation="vertical", padding=dp(10),
                spacing=dp(4), size_hint_y=None, height=dp(146),
            )
            worker_card.add_widget(self._label(
                worker["name"], size=15, height=dp(24), bold=True,
            ))
            worker_card.add_widget(self._label(
                f"Usuario: {worker['username']}", size=13,
                color_hex=MUTED, height=dp(20),
            ))
            worker_card.add_widget(self._label(
                assignment_text, size=12,
                color_hex=FOREST if assigned_requests else MUTED,
                height=dp(32),
            ))
            actions = MDBoxLayout(
                orientation="horizontal", spacing=dp(8),
                size_hint_y=None, height=dp(40),
            )
            actions.add_widget(self._button(
                "Editar",
                lambda account=worker: self._show_worker_dialog(account),
                style="tonal",
            ))
            if assigned_requests:
                actions.add_widget(self._button(
                    "Finalizar retiro",
                    lambda rid=assigned_requests[0]["id"]: self._finalize_worker_request(rid),
                    style="text",
                ))
            actions.add_widget(self._button(
                "Eliminar",
                lambda account=worker: self._confirm_delete_worker(account),
                style="text",
            ))
            worker_card.add_widget(actions)
            worker_container.add_widget(worker_card)
        for status, heading in (
            ("submitted", "Por revisar"),
            ("accepted", "Aceptadas · asignar trabajador"),
            ("assigned", "Asignadas"),
            ("in_progress", "En recolección"),
            ("pending", "Pendientes · requieren atención"),
            ("completed", "Completadas"),
        ):
            requests = [item for item in self.service.requests if item["status"] == status]
            container.add_widget(self._label(
                f"{heading}  ·  {len(requests)}", size=16, height=dp(36), bold=True,
            ))
            if not requests:
                container.add_widget(self._label(
                    "No hay solicitudes en esta etapa.", size=14,
                    color_hex=MUTED, height=dp(32),
                ))
            for request in requests:
                container.add_widget(self._request_card(request, admin_actions=True))

    def refresh_worker(self) -> None:
        if not self.root or "screen_manager" not in self.root.ids:
            return
        screen = self.root.ids.screen_manager.get_screen("worker")
        if not self.current_user or self.current_user["role"] != "worker":
            return
        worker = self.current_user["name"]
        screen.ids.worker_identity.text = worker
        container = screen.ids.worker_requests
        container.clear_widgets()
        requests = self.service.route_for_worker(worker)
        screen.ids.worker_count.text = f"Servicios pendientes  ·  {len(requests)}"
        screen.ids.route_count.text = f"Ruta sugerida  ·  {len(requests)} paradas"
        screen.ids.open_route.disabled = not requests
        if not requests:
            container.add_widget(self._label(
                "No tienes retiros pendientes asignados.", size=14,
                color_hex=MUTED, height=dp(42),
            ))
        for stop_number, request in enumerate(requests, start=1):
            container.add_widget(self._request_card(
                request, worker_actions=True, stop_number=stop_number,
            ))

    def _request_card(self, request: dict, *, citizen_actions: bool = False,
                      admin_actions: bool = False,
                      worker_actions: bool = False,
                      stop_number: int | None = None) -> MDCard:
        extra_height = 0
        if citizen_actions:
            extra_height += 50
        if admin_actions and request["status"] == "submitted":
            extra_height += 54
        elif admin_actions and request["status"] in {"accepted", "assigned"}:
            extra_height += 106
        elif worker_actions:
            extra_height += 54
        if request.get("worker"):
            extra_height += 27
        if request.get("description"):
            extra_height += 38
        if request.get("pending_reason"):
            extra_height += 44
        if request.get("photo_path"):
            extra_height += 48
        if stop_number is not None:
            extra_height += 26
        card = MDCard(
            style="outlined", orientation="vertical", padding=dp(13),
            spacing=dp(4), size_hint_y=None, height=dp(137 + extra_height),
        )
        if stop_number is not None:
            card.add_widget(self._label(
                f"PARADA {stop_number}", size=14, color_hex=FOREST,
                height=dp(22), bold=True,
            ))
        card.add_widget(self._label(
            f"{request['id']}  ·  {request['date']}", size=14,
            color_hex=MUTED, height=dp(24), bold=True,
        ))
        card.add_widget(self._label(
            f"{request['address']} · {request['neighborhood']}",
            size=16, height=dp(28), bold=True,
        ))
        card.add_widget(self._label(
            f"{request['name']}  ·  {request['quantity']}  ·  {STATUS_LABELS[request['status']]}",
            size=14, color_hex=FOREST, height=dp(26),
        ))
        if request.get("worker"):
            card.add_widget(self._label(
                f"Responsable: {request['worker']}", size=14,
                color_hex=MUTED, height=dp(23),
            ))
        if request.get("description"):
            card.add_widget(self._label(
                request["description"], size=14, color_hex=MUTED, height=dp(34),
            ))
        if request.get("pending_reason"):
            card.add_widget(self._label(
                f"Motivo pendiente: {request['pending_reason']}", size=14,
                color_hex="#70410F", height=dp(40),
            ))
        if request.get("photo_path"):
            card.add_widget(self._button(
                "Ver foto adjunta",
                lambda path=request["photo_path"], rid=request["id"]:
                self._show_request_photo(rid, path),
                style="text",
            ))

        if citizen_actions:
            actions = MDBoxLayout(
                orientation="horizontal", spacing=dp(6),
                size_hint_y=None, height=dp(46),
            )
            actions.add_widget(self._button(
                "Editar",
                lambda rid=request["id"]: self._begin_edit_request(rid),
                background_color=FOREST,
                text_color="#FFFFFF",
                theme_width="Custom",
            ))
            actions.add_widget(self._button(
                "Borrar",
                lambda rid=request["id"]: self._confirm_delete_request(rid),
                background_color="#A61B1B",
                text_color="#FFFFFF",
                theme_width="Custom",
            ))
            card.add_widget(actions)
        elif admin_actions and request["status"] == "submitted":
            card.add_widget(self._button(
                "Aceptar solicitud",
                lambda rid=request["id"]: self._change_status(rid, "accepted"),
            ))
        elif admin_actions and request["status"] in {"accepted", "assigned"}:
            picker = Spinner(
                text=request.get("worker") or "Selecciona trabajador",
                values=self.service.worker_names,
                size_hint_y=None, height=dp(48),
                background_normal="", background_color=(0.95, 0.96, 0.94, 1),
                color=(0.11, 0.24, 0.19, 1), font_size=dp(14),
            )
            card.add_widget(picker)
            assign_button = self._button(
                "Asignar trabajador",
                lambda rid=request["id"], select=picker: self._assign(rid, select.text),
            )
            assign_button.disabled = picker.text not in self.service.worker_names
            picker.bind(text=lambda _picker, selected: setattr(
                assign_button, "disabled", selected not in self.service.worker_names,
            ))
            card.add_widget(assign_button)
        elif worker_actions:
            actions = MDBoxLayout(
                orientation="horizontal", spacing=dp(5),
                size_hint_y=None, height=dp(50),
            )
            if request["status"] == "assigned":
                primary_text, primary_status = "Iniciar", "in_progress"
            elif request["status"] == "pending":
                primary_text, primary_status = "Reanudar", "in_progress"
            elif request["status"] == "in_progress":
                primary_text, primary_status = "Finalizar", "completed"
            else:
                primary_text, primary_status = "Realizada", "completed"
            primary = self._button(
                primary_text,
                lambda rid=request["id"], state=primary_status: self._change_status(rid, state),
            )
            primary.size_hint_x = 1.1
            pending_button = self._button(
                "Pendiente",
                lambda rid=request["id"]: self._ask_pending_reason(rid),
                style="tonal",
            )
            pending_button.size_hint_x = 0.9
            actions.add_widget(primary)
            actions.add_widget(pending_button)
            card.add_widget(actions)
        return card

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
            f"Foto adjunta: {Path(self.selected_photo_path).name}"
        )
        return True

    def choose_request_photo(self) -> None:
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

    def _select_request_photo(self, popup: Popup, selection: list[str]) -> None:
        if not selection:
            self._show_dialog("Falta seleccionar", "Selecciona una foto antes de continuar.")
            return
        if self._set_selected_photo(selection[0]):
            popup.dismiss()

    def take_request_photo(self) -> None:
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

    def _begin_edit_request(self, request_id: str) -> None:
        if not self.current_user or self.current_user["role"] != "citizen":
            return
        try:
            request = self.service.get(request_id)
            if request["name"].strip().casefold() != self.current_user["name"].strip().casefold():
                raise ValueError("No tienes permiso para editar esta solicitud.")
        except ValueError as error:
            self._show_dialog("No se pudo editar", str(error))
            return
        screen = self.root.ids.screen_manager.get_screen("citizen")
        fields = screen.ids
        fields.address.text = request["address"]
        fields.neighborhood.text = request["neighborhood"]
        fields.quantity.text = request["quantity"]
        fields.details.text = request.get("description", "")
        self.editing_request_id = request_id
        self.editing_original_photo = request.get("photo_path", "")
        self.selected_photo_path = self.editing_original_photo
        fields.photo_status.text = (
            f"Foto adjunta: {Path(self.selected_photo_path).name}"
            if self.selected_photo_path else "Foto obligatoria: elige o toma una foto."
        )
        fields.submit_request_button_text.text = "Guardar cambios"
        fields.cancel_edit_button.disabled = False
        fields.cancel_edit_button.opacity = 1
        screen.ids.citizen_scroll.scroll_to(fields.address)

    def cancel_edit_request(self) -> None:
        if (self.selected_photo_path
                and self.selected_photo_path != self.editing_original_photo):
            self._remove_stored_photo(self.selected_photo_path)
        self._clear_request_form()

    def _clear_request_form(self) -> None:
        screen = self.root.ids.screen_manager.get_screen("citizen")
        screen.ids.address.text = ""
        screen.ids.neighborhood.text = ""
        screen.ids.quantity.text = "Selecciona cantidad"
        screen.ids.details.text = ""
        screen.ids.photo_status.text = "Foto obligatoria: elige o toma una foto."
        screen.ids.submit_request_button_text.text = "Enviar solicitud"
        screen.ids.cancel_edit_button.disabled = True
        screen.ids.cancel_edit_button.opacity = 0
        self.selected_photo_path = ""
        self.editing_request_id = None
        self.editing_original_photo = ""

    def _confirm_delete_request(self, request_id: str) -> None:
        if not self.current_user or self.current_user["role"] != "citizen":
            return
        try:
            request = self.service.get(request_id)
            if request["name"].strip().casefold() != self.current_user["name"].strip().casefold():
                raise ValueError("No tienes permiso para eliminar esta solicitud.")
        except ValueError as error:
            self._show_dialog("No se pudo eliminar", str(error))
            return
        cancel_button = MDButton(MDButtonText(text="Cancelar"), style="text")
        delete_button = MDButton(MDButtonText(text="Borrar solicitud"), style="tonal")
        dialog = MDDialog(
            MDDialogHeadlineText(text="Borrar solicitud"),
            MDDialogSupportingText(
                text=f"¿Quieres borrar {request_id}? Esta acción no se puede deshacer."
            ),
            MDDialogButtonContainer(
                Widget(), cancel_button, delete_button, spacing=dp(8),
            ),
        )
        cancel_button.bind(on_release=lambda *_args: dialog.dismiss())
        delete_button.bind(on_release=lambda *_args: self._delete_request(
            dialog, request_id,
        ))
        dialog.open()

    def _delete_request(self, dialog: MDDialog, request_id: str) -> None:
        if not self.current_user or self.current_user["role"] != "citizen":
            dialog.dismiss()
            return
        try:
            request = self.service.delete_request(
                request_id, citizen_name=self.current_user["name"],
            )
        except ValueError as error:
            dialog.dismiss()
            self._show_dialog("No se pudo eliminar", str(error))
            return
        self._remove_stored_photo(request.get("photo_path", ""))
        if self.editing_request_id == request_id:
            self._clear_request_form()
        dialog.dismiss()
        self.refresh_all()

    def _remove_stored_photo(self, photo_path: str) -> None:
        if not photo_path:
            return
        photo_dir = (Path(self.user_data_dir) / "request_photos").resolve()
        photo_file = Path(photo_path).resolve()
        if photo_file.parent != photo_dir:
            return
        try:
            photo_file.unlink(missing_ok=True)
        except OSError as error:
            self._show_dialog(
                "No se pudo limpiar una foto",
                f"La solicitud se actualizó, pero no se pudo borrar {photo_file.name}: {error}",
            )

    def _ask_pending_reason(self, request_id: str) -> None:
        reason_field = MDTextField(
            MDTextFieldHintText(text="Motivo (obligatorio)"),
            mode="outlined", size_hint_y=None, height=dp(62),
        )
        cancel_button = MDButton(MDButtonText(text="Cancelar"), style="text")
        save_button = MDButton(MDButtonText(text="Guardar"), style="filled")
        button_container = MDDialogButtonContainer(
            Widget(), cancel_button, save_button, spacing=dp(8),
        )
        dialog = MDDialog(
            MDDialogHeadlineText(text="Dejar retiro pendiente"),
            MDDialogSupportingText(text="Indica por qué no se pudo completar esta parada."),
            MDDialogContentContainer(
                reason_field, orientation="vertical", padding=(dp(16), dp(8)),
            ),
            button_container,
        )
        self.pending_dialog = dialog
        cancel_button.bind(on_release=lambda *_args: dialog.dismiss())
        save_button.bind(on_release=lambda *_args: self._save_pending_reason(
            dialog, request_id, reason_field.text,
        ))
        self._bind_enter_navigation(
            (reason_field,),
            lambda: self._save_pending_reason(
                dialog, request_id, reason_field.text,
            ),
        )
        dialog.open()

    def _show_worker_dialog(self, worker: dict[str, str] | None = None) -> None:
        if not self.current_user or self.current_user["role"] != "admin":
            return
        username_field = MDTextField(
            MDTextFieldHintText(text="Usuario"),
            mode="outlined", size_hint_y=None, height=dp(62),
            text=worker["username"] if worker else "",
        )
        name_field = MDTextField(
            MDTextFieldHintText(text="Nombre completo"),
            mode="outlined", size_hint_y=None, height=dp(62),
            text=worker["name"] if worker else "",
        )
        phone_field = MDTextField(
            MDTextFieldHintText(text="Teléfono"),
            mode="outlined", size_hint_y=None, height=dp(62),
            text=worker["phone"] if worker else "",
        )
        password_field = MDTextField(
            MDTextFieldHintText(
                text="Nueva contraseña (opcional)" if worker
                else "Contraseña (mínimo 6 caracteres)"
            ),
            mode="outlined", size_hint_y=None, height=dp(62), password=True,
        )
        cancel_button = MDButton(MDButtonText(text="Cancelar"), style="text")
        save_button = MDButton(MDButtonText(text="Guardar"), style="filled")
        content = MDDialogContentContainer(
            username_field, name_field, phone_field, password_field,
            orientation="vertical", padding=(dp(16), dp(8)),
        )
        dialog = MDDialog(
            MDDialogHeadlineText(
                text="Editar trabajador" if worker else "Agregar trabajador"
            ),
            MDDialogSupportingText(
                text="Deja la contraseña vacía para conservar la actual."
                if worker else "Crea el acceso para el trabajador."
            ),
            content,
            MDDialogButtonContainer(
                Widget(), cancel_button, save_button, spacing=dp(8),
            ),
        )
        cancel_button.bind(on_release=lambda *_args: dialog.dismiss())
        save_button.bind(on_release=lambda *_args: self._save_worker(
            dialog, worker, username_field.text, name_field.text,
            phone_field.text, password_field.text,
        ))
        self._bind_enter_navigation(
            (username_field, name_field, phone_field, password_field),
            lambda: self._save_worker(
                dialog, worker, username_field.text, name_field.text,
                phone_field.text, password_field.text,
            ),
        )
        dialog.open()

    def _save_worker(self, dialog, worker: dict[str, str] | None,
                     username: str, name: str, phone: str, password: str) -> None:
        try:
            if worker:
                self.service.update_worker(
                    worker["username"], username=username,
                    name=name, phone=phone, password=password,
                )
            else:
                self.service.create_worker(
                    username=username, name=name, password=password,
                    phone=phone,
                )
        except ValueError as error:
            self._show_dialog("No se pudo guardar", str(error))
            return
        dialog.dismiss()
        self.refresh_all()

    def _confirm_delete_worker(self, worker: dict[str, str]) -> None:
        if not self.current_user or self.current_user["role"] != "admin":
            return
        cancel_button = MDButton(MDButtonText(text="Cancelar"), style="text")
        delete_button = MDButton(MDButtonText(text="Eliminar"), style="tonal")
        dialog = MDDialog(
            MDDialogHeadlineText(text="Eliminar trabajador"),
            MDDialogSupportingText(
                text=f"¿Quieres eliminar a {worker['name']} y su acceso?"
            ),
            MDDialogButtonContainer(
                Widget(), cancel_button, delete_button, spacing=dp(8),
            ),
        )
        cancel_button.bind(on_release=lambda *_args: dialog.dismiss())
        delete_button.bind(on_release=lambda *_args: self._delete_worker(
            dialog, worker,
        ))
        dialog.open()

    def _delete_worker(self, dialog, worker: dict[str, str]) -> None:
        try:
            self.service.delete_worker(worker["username"])
        except ValueError as error:
            dialog.dismiss()
            self._show_dialog("No se pudo eliminar", str(error))
            return
        dialog.dismiss()
        self.refresh_all()

    def _finalize_worker_request(self, request_id: str) -> None:
        if not self.current_user or self.current_user["role"] not in {"admin", "worker"}:
            return
        try:
            request = self.service.get(request_id)
            if request["status"] == "assigned":
                self.service.transition(request_id, "in_progress")
            self.service.transition(request_id, "completed")
        except ValueError as error:
            self._show_dialog("No se pudo finalizar", str(error))
            return
        self.refresh_all()

    def _save_pending_reason(self, dialog, request_id: str, reason: str) -> None:
        if len(reason.strip()) < 4:
            self._show_dialog("Falta el motivo", "Escribe al menos cuatro caracteres para explicar el pendiente.")
            return
        dialog.dismiss()
        self.pending_dialog = None
        self._change_status(request_id, "pending", reason=reason)

    def open_worker_route(self) -> None:
        if not self.current_user or self.current_user["role"] != "worker":
            return
        stops = self.service.route_for_worker(self.current_user["name"])
        if not stops:
            self._show_dialog("Sin paradas", "No tienes solicitudes asignadas para abrir una ruta.")
            return
        locations = [
            f"{stop['address']}, {stop['neighborhood']}, Temuco, Chile"
            for stop in stops
        ]
        params = {
            "api": "1",
            "origin": "Current Location",
            "destination": locations[-1],
            "travelmode": "driving",
        }
        if len(locations) > 1:
            params["waypoints"] = "|".join(locations[:-1])
        webbrowser.open(f"https://www.google.com/maps/dir/?{urlencode(params)}")

    def submit_request(self) -> None:
        if not self.current_user or self.current_user["role"] != "citizen":
            return
        screen = self.root.ids.screen_manager.get_screen("citizen")
        fields = screen.ids
        name = self.current_user["name"]
        phone = self.current_user["phone"]
        address = fields.address.text.strip()
        neighborhood = fields.neighborhood.text.strip()
        quantity = fields.quantity.text
        description = fields.details.text.strip()
        was_editing = bool(self.editing_request_id)
        if not all((name, phone, address, neighborhood)):
            self._show_dialog("Faltan datos", "Completa nombre, teléfono, dirección y colonia para enviar la solicitud.")
            return
        if sum(character.isdigit() for character in phone) < 8:
            self._show_dialog("Revisa el teléfono", "Escribe un número de contacto con al menos 8 dígitos.")
            return
        if quantity not in {"1 montón", "2 montones", "3 montones", "Más de 3 montones"}:
            self._show_dialog("Selecciona la cantidad", "Indica cuántos montones de ramas deben retirarse.")
            return
        try:
            if not self.selected_photo_path:
                self._show_dialog(
                    "Falta la foto",
                    "Adjunta una foto de las ramas, tomada con la cámara o elegida del dispositivo.",
                )
                return
            if self.editing_request_id:
                request_id = self.editing_request_id
                old_photo = self.editing_original_photo
                request = self.service.update_request(
                    request_id,
                    citizen_name=name,
                    address=address,
                    neighborhood=neighborhood,
                    quantity=quantity,
                    photo_path=self.selected_photo_path,
                    description=description,
                )
                if old_photo and old_photo != self.selected_photo_path:
                    self._remove_stored_photo(old_photo)
                success_message = f"Actualizamos {request['id']}."
            else:
                request = self.service.create(
                    name=name, phone=phone, address=address,
                    neighborhood=neighborhood, quantity=quantity,
                    photo_path=self.selected_photo_path,
                    description=description,
                )
                success_message = f"Registramos {request['id']}. Administración la revisará."
        except ValueError as error:
            self._show_dialog("No se pudo enviar", str(error))
            return
        self._clear_request_form()
        self.refresh_all()
        self._show_dialog(
            "Solicitud actualizada" if was_editing else "Solicitud enviada",
            success_message,
        )

    def _assign(self, request_id: str, worker: str) -> None:
        if not self.current_user or self.current_user["role"] != "admin":
            return
        if worker not in self.service.worker_names:
            self._show_dialog(
                "Selecciona trabajador",
                "Elige una persona del menú antes de asignar el retiro.",
            )
            return
        self._change_status(request_id, "assigned", worker=worker)

    def _change_status(self, request_id: str, status: str, *, worker: str = "",
                       reason: str = "") -> None:
        required_role = "admin" if status in {"accepted", "assigned"} else "worker"
        if not self.current_user or self.current_user["role"] != required_role:
            return
        try:
            self.service.transition(request_id, status, worker=worker, reason=reason)
        except ValueError as error:
            self._show_dialog("No se pudo actualizar", str(error))
            return
        self.refresh_all()


if __name__ == "__main__":
    RamaMobileApp().run()
