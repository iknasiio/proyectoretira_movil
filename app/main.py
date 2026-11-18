from __future__ import annotations

import os
import shutil
import webbrowser
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from threading import Thread
from urllib.parse import urlencode
from uuid import uuid4

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.lang import Builder
from kivy.logger import Logger
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
from kivymd.uix.screen import MDScreen
from kivymd.uix.textfield import MDTextField, MDTextFieldHintText
from PIL import Image as PillowImage
from requests.exceptions import RequestException

from .email_service import (
    EmailConfigError,
    EmailSendError,
    send_password_reset_email,
    send_welcome_email,
)
from .demo_data import SIMULATED_REQUEST_COUNT, simulated_dashboard_requests
from .remote_config import (
    DEFAULT_REMOTE_CONFIG,
    DEFAULT_REMOTE_CONFIG_URL,
    RemoteConfigError,
    fetch_remote_config,
)
from .request_service import (
    RESET_CODE_TTL_SECONDS,
    RequestService,
    STATUS_LABELS,
)

FOREST = "#173E31"
MUTED = "#49564E"
INK = "#1C2E27"
APP_DIR = Path(__file__).resolve().parent


class CitizenScreen(Screen):
    pass


class LoginScreen(Screen):
    pass


class RecoveryScreen(Screen):
    pass


class AdminScreen(Screen):
    pass


class DashboardScreen(Screen):
    pass


class DashboardBarChart(Widget):
    def __init__(self, created: list[int], completed: list[int], **kwargs):
        self.created = created
        self.completed = completed
        super().__init__(**kwargs)
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_args) -> None:
        self.canvas.clear()
        if not self.created:
            return
        maximum = max(self.created + self.completed, default=0)
        column_width = self.width / len(self.created)
        baseline = self.y + dp(5)
        chart_height = max(0, self.height - dp(10))
        with self.canvas:
            Color(*get_color_from_hex("#E4ECE6"))
            Line(
                points=(self.x, baseline, self.right, baseline),
                width=dp(0.7),
            )
            Color(*get_color_from_hex("#EDF1EE"))
            Line(
                points=(
                    self.x, baseline + chart_height * 0.5,
                    self.right, baseline + chart_height * 0.5,
                ),
                width=dp(0.6),
            )
            for index, (created, completed) in enumerate(
                zip(self.created, self.completed),
            ):
                bar_width = column_width * 0.28
                for offset, value, color in (
                    (-bar_width / 2, created, "#173E31"),
                    (bar_width / 2, completed, "#9CB7A5"),
                ):
                    if not value or not maximum:
                        continue
                    bar_height = chart_height * value / maximum
                    Color(*get_color_from_hex(color))
                    RoundedRectangle(
                        pos=(
                            self.x + (index + 0.5) * column_width
                            + offset,
                            baseline,
                        ),
                        size=(bar_width, bar_height),
                        radius=[dp(2)],
                    )


class DashboardSegmentBar(Widget):
    def __init__(self, values: list[int], colors: list[str], **kwargs):
        self.values = values
        self.colors = colors
        super().__init__(**kwargs)
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_args) -> None:
        self.canvas.clear()
        total = sum(self.values)
        with self.canvas:
            Color(*get_color_from_hex("#E4ECE6"))
            RoundedRectangle(
                pos=self.pos, size=self.size, radius=[dp(4)],
            )
            if not total:
                return
            x = self.x
            for value, color in zip(self.values, self.colors):
                if not value:
                    continue
                width = self.width * value / total
                Color(*get_color_from_hex(color))
                RoundedRectangle(
                    pos=(x, self.y),
                    size=(width, self.height),
                    radius=[dp(3)],
                )
                x += width


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
        self.service = RequestService(
            Path(self.user_data_dir) / "rama_data.json",
        )
        self.remote_config = DEFAULT_REMOTE_CONFIG.copy()
        self.remote_config_url = os.environ.get(
            "RAMA_REMOTE_CONFIG_URL", DEFAULT_REMOTE_CONFIG_URL,
        )
        self.current_user = None
        self.pending_reset_username = ""
        self.selected_photo_path = ""
        self.editing_request_id = None
        self.editing_original_photo = ""
        self.dashboard_period = 7
        self._android_photo_request_code = None
        Builder.load_file(str(APP_DIR / "rama.kv"))
        return RamaRoot()

    @staticmethod
    def asset_path(relative_path: str) -> str:
        return str(APP_DIR.parent / relative_path)

    def on_start(self):
        self.root.ids.screen_manager.current = "login"
        self.root.ids.nav_bar.height = 0
        self.root.ids.nav_bar.opacity = 0
        login = self.root.ids.screen_manager.get_screen("login")
        login.ids.remote_announcement.text = self.remote_config["announcement"]
        login.ids.remote_config_status.text = ""
        Thread(target=self._fetch_remote_config, daemon=True).start()
        self._bind_enter_navigation(
            (login.ids.login_username, login.ids.login_password),
            self.sign_in,
        )
        recovery = self.root.ids.screen_manager.get_screen("recovery")
        recovery.ids.recovery_code.bind(text=self._limit_recovery_code)
        self._bind_enter_navigation(
            (
                recovery.ids.recovery_code,
                recovery.ids.recovery_password,
                recovery.ids.recovery_confirm_password,
            ),
            self.confirm_password_reset,
        )
        citizen = self.root.ids.screen_manager.get_screen("citizen")
        self._bind_enter_navigation(
            (citizen.ids.address, citizen.ids.neighborhood, citizen.ids.details),
            self.submit_request,
        )

    def _fetch_remote_config(self) -> None:
        try:
            config = fetch_remote_config(self.remote_config_url)
        except (RemoteConfigError, RequestException) as error:
            Logger.warning(
                f"Rama: configuración remota no disponible: {error}"
            )
            Clock.schedule_once(
                lambda _dt, message=str(error):
                self._use_default_remote_config(message),
                0,
            )
            return
        Clock.schedule_once(
            lambda _dt: self._apply_remote_config(config),
            0,
        )

    def _apply_remote_config(self, config: dict[str, str]) -> None:
        self.remote_config = config
        login = self.root.ids.screen_manager.get_screen("login")
        login.ids.remote_announcement.text = config["announcement"]
        login.ids.remote_config_status.text = (
            f"Configuración remota · {config['municipality']}"
        )

    def _use_default_remote_config(self, reason: str) -> None:
        Logger.warning(f"Rama: se conserva la configuración local: {reason}")
        login = self.root.ids.screen_manager.get_screen("login")
        login.ids.remote_announcement.text = (
            self.remote_config["announcement"]
        )
        login.ids.remote_config_status.text = ""

    def _notify(self, message: str) -> None:
        notification = MDLabel(
            text=message,
            size_hint=(0.9, None),
            height=dp(52),
            pos_hint={"center_x": 0.5, "y": 0.025},
            font_size=dp(14),
            halign="center",
            valign="middle",
            text_size=(Window.width * 0.85, None),
            theme_text_color="Custom",
            text_color=(1, 1, 1, 1),
        )
        with notification.canvas.before:
            Color(*get_color_from_hex(FOREST))
            background = RoundedRectangle(
                pos=notification.pos,
                size=notification.size,
                radius=[dp(8)],
            )
        notification.bind(
            pos=lambda widget, _value: setattr(background, "pos", widget.pos),
            size=lambda widget, _value: setattr(background, "size", widget.size),
        )
        root = self.root
        root.add_widget(notification)
        Clock.schedule_once(
            lambda _dt: root.remove_widget(notification)
            if notification.parent is root else None,
            3.5,
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
        self.root.ids.top_app_bar.height = (
            self.root.ids.top_app_bar.width * 325 / 1024
        )
        self.root.ids.nav_bar.height = 0
        self.root.ids.nav_bar.opacity = 0

    def open_dashboard(self) -> None:
        if not self.current_user or self.current_user["role"] != "admin":
            return
        self.root.ids.top_app_bar.height = dp(98)
        self.root.ids.screen_manager.current = "dashboard"
        self.root.ids.session_user.text = self.current_user["name"]
        self.refresh_dashboard()

    def close_dashboard(self) -> None:
        if not self.current_user or self.current_user["role"] != "admin":
            return
        self.root.ids.top_app_bar.height = (
            self.root.ids.top_app_bar.width * 325 / 1024
        )
        self.root.ids.screen_manager.current = "admin"
        self.refresh_all()

    def set_dashboard_period(self, days: int) -> None:
        if days not in {1, 7, 30}:
            return
        self.dashboard_period = days
        self.refresh_dashboard()

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

        cancel_button = self._dialog_button("Cancelar", style="text", width=110)
        save_button = self._dialog_button("Crear cuenta", style="filled", width=150)
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
        except (ValueError, OSError) as error:
            self._show_dialog("No se pudo registrar", str(error))
            return
        dialog.dismiss()
        self._show_dialog(
            "Cuenta creada",
            f"Hola {account['name']}. Ahora puedes iniciar sesión con {account['username']}.",
        )
        Thread(
            target=self._send_welcome_email,
            args=(account["email"], account["name"]),
            daemon=True,
        ).start()

    def _send_welcome_email(self, email: str, name: str) -> None:
        """Se ejecuta en un hilo: la cuenta ya existe aunque el correo falle."""
        try:
            send_welcome_email(email, name)
        except (EmailConfigError, EmailSendError) as error:
            Logger.warning(f"Correo de bienvenida no enviado: {error}")
            Clock.schedule_once(
                lambda _dt: self._notify(
                    "Cuenta creada, pero no se pudo enviar el correo de bienvenida."
                ),
                0,
            )
            return
        Clock.schedule_once(
            lambda _dt: self._notify("Te enviamos un correo de bienvenida."), 0,
        )

    def open_recovery(self) -> None:
        username = MDTextField(
            MDTextFieldHintText(text="Usuario"), mode="outlined",
            size_hint_y=None, height=dp(64),
        )
        cancel_button = self._dialog_button("Cancelar", style="text", width=110)
        recover_button = self._dialog_button("Recuperar", style="filled", width=130)
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
        dialog.dismiss()
        normalized_username = username.text.strip()
        if not normalized_username:
            self._show_dialog(
                "Usuario requerido",
                "Escribe el usuario de tu cuenta. No se envió ningún código.",
            )
            return
        account = self.service.recovery_account(normalized_username)
        if account is None:
            self._show_dialog(
                "Usuario no encontrado",
                "Ese usuario no existe. No se envió ningún código.",
            )
            return
        reset = self.service.create_password_reset(normalized_username)
        if reset is None:
            self._show_dialog(
                "Correo no registrado",
                "El usuario existe, pero esta cuenta no tiene un correo "
                "registrado. No se pudo enviar el código.",
            )
            return
        self._notify("Enviando código a tu correo…")
        Thread(
            target=self._send_reset_code,
            args=(reset,),
            daemon=True,
        ).start()

    def _send_reset_code(self, reset: dict[str, str]) -> None:
        """Se ejecuta en un hilo para no congelar la interfaz."""
        try:
            send_password_reset_email(
                reset["email"], reset["name"], reset["code"],
                RESET_CODE_TTL_SECONDS // 60,
            )
        except (EmailConfigError, EmailSendError) as error:
            Logger.error(f"Código de recuperación no enviado: {error}")
            self.service.cancel_password_reset(reset["username"])
            reason = str(error)
            Clock.schedule_once(
                lambda _dt: self._show_dialog(
                    "No se pudo enviar el correo", reason,
                ),
                0,
            )
            return
        Clock.schedule_once(
            lambda _dt: self._show_recovery_screen(
                reset["username"], reset["email"],
            ),
            0,
        )

    @staticmethod
    def _mask_email(email: str) -> str:
        local_part, separator, domain = email.partition("@")
        if separator and local_part and domain:
            return f"{local_part[:1]}***{separator}{domain}"
        return email

    @staticmethod
    def _limit_recovery_code(field: MDTextField, value: str) -> None:
        if len(value) > 6:
            field.text = value[:6]

    def _show_recovery_screen(self, username: str, email: str) -> None:
        screen = self.root.ids.screen_manager.get_screen("recovery")
        screen.ids.recovery_code.text = ""
        screen.ids.recovery_password.text = ""
        screen.ids.recovery_confirm_password.text = ""
        screen.ids.recovery_email.text = (
            f"Enviamos un código a {self._mask_email(email)}. "
            "Vence en 10 minutos."
        )
        self.pending_reset_username = username
        self.root.ids.screen_manager.current = "recovery"
        Clock.schedule_once(
            lambda _dt: setattr(screen.ids.recovery_code, "focus", True), 0,
        )

    def cancel_password_reset(self) -> None:
        if self.pending_reset_username:
            self.service.cancel_password_reset(self.pending_reset_username)
        self.pending_reset_username = ""
        self.root.ids.screen_manager.current = "login"

    def confirm_password_reset(self) -> None:
        if not self.pending_reset_username:
            self.root.ids.screen_manager.current = "login"
            self._show_dialog(
                "Solicita un código nuevo",
                "Vuelve a pedir un código para cambiar la contraseña.",
            )
            return
        screen = self.root.ids.screen_manager.get_screen("recovery")
        code = screen.ids.recovery_code.text.strip()
        new_password = screen.ids.recovery_password.text
        confirm_password = screen.ids.recovery_confirm_password.text
        if len(code) != 6 or not code.isdigit():
            self._show_dialog(
                "Código incompleto",
                "Ingresa los 6 dígitos que recibiste por correo.",
            )
            return
        if new_password != confirm_password:
            self._show_dialog(
                "Contraseña no coincidente",
                "Las dos contraseñas deben ser exactamente iguales.",
            )
            return
        try:
            self.service.reset_password(
                self.pending_reset_username, code, new_password,
            )
        except (ValueError, OSError) as error:
            self._show_dialog("No se pudo cambiar la contraseña", str(error))
            return
        self.pending_reset_username = ""
        screen.ids.recovery_code.text = ""
        screen.ids.recovery_password.text = ""
        screen.ids.recovery_confirm_password.text = ""
        self.root.ids.screen_manager.current = "login"
        self._show_dialog(
            "Contraseña actualizada",
            "Ya puedes iniciar sesión con tu nueva contraseña.",
        )

    def _open_reset_dialog(self, username: str, email: str) -> None:
        code = MDTextField(
            MDTextFieldHintText(text="Código de 6 dígitos"), mode="outlined",
            size_hint_y=None, height=dp(54),
            input_filter="int",
        )
        code.bind(
            text=lambda field, value: setattr(field, "text", value[:6])
            if len(value) > 6 else None,
        )
        new_password = MDTextField(
            MDTextFieldHintText(text="Nueva contraseña"), mode="outlined",
            size_hint_y=None, height=dp(54), password=True,
        )
        confirm_password = MDTextField(
            MDTextFieldHintText(text="Confirmar nueva contraseña"),
            mode="outlined", size_hint_y=None, height=dp(54), password=True,
        )
        fields = MDBoxLayout(
            orientation="vertical", spacing=dp(11), padding=dp(12),
            size_hint_y=None, height=dp(220),
        )
        fields.add_widget(code)
        fields.add_widget(new_password)
        fields.add_widget(confirm_password)
        cancel_button = self._dialog_button("Cancelar", style="text", width=110)
        save_button = self._dialog_button("Cambiar", style="filled", width=130)
        dialog = MDDialog(
            MDDialogHeadlineText(text="Ingresa tu código"),
            MDDialogSupportingText(
                text=f"Enviamos un código a {self._mask_email(email)}. "
                     "Vence en 10 minutos.",
            ),
            MDDialogContentContainer(
                fields, orientation="vertical", padding=(dp(16), dp(8)),
            ),
            MDDialogButtonContainer(
                Widget(), cancel_button, save_button, spacing=dp(8),
            ),
            size=(dp(410), dp(520)),
            size_hint=(None, None),
        )

        def cancel(*_args):
            self.service.cancel_password_reset(username)
            dialog.dismiss()

        cancel_button.bind(on_release=cancel)
        save_button.bind(on_release=lambda *_args: self._confirm_password_reset(
            dialog, username, code, new_password, confirm_password,
        ))
        self._bind_enter_navigation(
            (code, new_password, confirm_password),
            lambda: self._confirm_password_reset(
                dialog, username, code, new_password, confirm_password,
            ),
        )
        dialog.open()

    def _confirm_password_reset(self, dialog, username, code, new_password,
                                confirm_password) -> None:
        if new_password.text != confirm_password.text:
            self._show_dialog(
                "Contraseña no coincidente",
                "Las dos contraseñas deben ser exactamente iguales.",
            )
            return
        try:
            self.service.reset_password(
                username, code.text, new_password.text,
            )
        except (ValueError, OSError) as error:
            self._show_dialog("No se pudo cambiar la contraseña", str(error))
            return
        dialog.dismiss()
        self._show_dialog(
            "Contraseña actualizada",
            "Ya puedes iniciar sesión con tu nueva contraseña.",
        )

    def _label(self, text: str, *, size: int = 15, color_hex: str = INK,
               height: int = 25, bold: bool = False) -> MDLabel:
        label = MDLabel(
            text=text,
            size_hint_y=None,
            height=dp(height),
            font_size=dp(size),
            bold=bold,
            halign="left",
            valign="middle",
            theme_text_color="Custom",
            text_color=get_color_from_hex(color_hex),
        )
        label.bind(
            size=lambda widget, _size: setattr(
                widget, "text_size", (widget.width, widget.height),
            ),
        )
        label.text_size = (label.width if label.width else 1, dp(height))
        return label

    def _button(
        self,
        text: str,
        callback,
        *,
        style: str = "filled",
        background_color: str | None = None,
        text_color: str | None = None,
        theme_width: str = "Custom",
    ) -> MDButton:
        button = MDButton(
            style=style, theme_width=theme_width,
            size_hint=(1, None), height=dp(44),
        )
        button.theme_bg_color = "Custom"
        if background_color:
            button.md_bg_color = get_color_from_hex(background_color)
        elif style == "filled":
            button.md_bg_color = get_color_from_hex(FOREST)
        elif style == "tonal":
            button.md_bg_color = get_color_from_hex("#E4ECE6")
        else:
            button.md_bg_color = get_color_from_hex("#FDFEFD")
        button_text = MDButtonText(text=text, font_size=dp(14))
        if text_color:
            button_text.theme_text_color = "Custom"
            button_text.text_color = get_color_from_hex(text_color)
            button_text.disabled_color = get_color_from_hex(text_color)
        elif style == "filled":
            button_text.theme_text_color = "Custom"
            button_text.text_color = get_color_from_hex("#FFFFFF")
            button_text.disabled_color = get_color_from_hex("#FFFFFF")
        else:
            button_text.theme_text_color = "Custom"
            button_text.text_color = get_color_from_hex(FOREST)
            button_text.disabled_color = get_color_from_hex(FOREST)
        button.add_widget(button_text)
        button.bind(on_release=lambda *_args: callback())
        return button

    def _dialog_button(
        self,
        text: str,
        *,
        style: str = "filled",
        width: int = 120,
    ) -> MDButton:
        button_text = MDButtonText(text=text, font_size=dp(14))
        button = MDButton(
            button_text,
            style=style,
            theme_width="Custom",
            size_hint=(None, None),
            width=dp(width),
            height=dp(44),
        )
        button.theme_bg_color = "Custom"
        if style == "filled":
            button.md_bg_color = get_color_from_hex(FOREST)
            button_text.theme_text_color = "Custom"
            button_text.text_color = get_color_from_hex("#FFFFFF")
            button_text.disabled_color = get_color_from_hex("#FFFFFF")
        elif style == "tonal":
            button.md_bg_color = get_color_from_hex("#E4ECE6")
            button_text.theme_text_color = "Custom"
            button_text.text_color = get_color_from_hex(FOREST)
            button_text.disabled_color = get_color_from_hex(FOREST)
        else:
            button.md_bg_color = get_color_from_hex("#FFFFFF")
            button_text.theme_text_color = "Custom"
            button_text.text_color = get_color_from_hex(FOREST)
            button_text.disabled_color = get_color_from_hex(FOREST)
        return button

    def _show_dialog(self, title: str, message: str) -> None:
        for root_widget in Window.children:
            for widget in root_widget.walk():
                if isinstance(widget, MDTextField):
                    widget.focus = False
        close_button = self._dialog_button("Entendido", style="text", width=120)
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
        self.refresh_dashboard()

    def _dashboard_card(self, title: str, children: list[Widget]) -> MDCard:
        card = MDCard(
            style="outlined", orientation="vertical", padding=dp(10),
            spacing=dp(6), size_hint_y=None,
        )
        card.add_widget(self._label(title, size=14, height=23, bold=True))
        for child in children:
            card.add_widget(child)
        card.bind(minimum_height=card.setter("height"))
        card.height = card.minimum_height
        return card

    def _dashboard_metric(
        self, value: str, label: str, detail: str = "", *, color: str = FOREST,
    ) -> MDCard:
        card = MDCard(
            style="outlined", orientation="vertical", padding=(dp(7), dp(5)),
            spacing=0, size_hint=(1, None), height=dp(62),
        )
        card.add_widget(self._label(
            value, size=17, height=21, bold=True, color_hex=color,
        ))
        card.add_widget(self._label(
            label, size=9, height=18, color_hex=INK,
        ))
        if detail:
            card.add_widget(self._label(
                detail, size=8, height=11, color_hex=MUTED,
            ))
        return card

    @staticmethod
    def _average_duration(
        requests: list[dict], start_key: str, end_key: str,
    ) -> str:
        elapsed = []
        for request in requests:
            try:
                start = datetime.fromisoformat(request[start_key])
                end = datetime.fromisoformat(request[end_key])
            except (KeyError, TypeError, ValueError):
                continue
            seconds = (end - start).total_seconds()
            if seconds >= 0:
                elapsed.append(seconds)
        if not elapsed:
            return "—"
        average = sum(elapsed) / len(elapsed)
        if average >= 86400:
            return f"{average / 86400:.1f} días".replace(".", ",")
        return f"{average / 3600:.1f} h".replace(".", ",")

    @staticmethod
    def _dashboard_date(value: object) -> date | None:
        if not isinstance(value, str):
            return None
        try:
            if len(value) == 10:
                return date.fromisoformat(value)
            return datetime.fromisoformat(value).date()
        except ValueError:
            return None

    def _dashboard_bar_row(
        self, label: str, value: int, maximum: int, *,
        color: str = FOREST, detail: str = "",
    ) -> MDBoxLayout:
        row = MDBoxLayout(
            orientation="horizontal", spacing=dp(7),
            size_hint_y=None, height=dp(24),
        )
        label_widget = self._label(label, size=10, height=22)
        label_widget.size_hint_x = None
        label_widget.width = dp(95)
        row.add_widget(label_widget)
        track = MDBoxLayout(
            orientation="horizontal", size_hint_x=1,
            size_hint_y=None, height=dp(9),
            pos_hint={"center_y": 0.5},
            md_bg_color=get_color_from_hex("#E4ECE6"),
        )
        ratio = value / maximum if maximum else 0
        if ratio > 0:
            bar = MDBoxLayout(
                size_hint_x=max(0.04, ratio),
                md_bg_color=get_color_from_hex(color),
            )
            track.add_widget(bar)
        row.add_widget(track)
        value_widget = self._label(
            detail or str(value), size=10, height=22,
        )
        value_widget.size_hint_x = None
        value_widget.width = dp(27)
        value_widget.halign = "right"
        row.add_widget(value_widget)
        return row

    def refresh_dashboard(self) -> None:
        if not self.root or "screen_manager" not in self.root.ids:
            return
        screen = self.root.ids.screen_manager.get_screen("dashboard")
        if "dashboard_content" not in screen.ids:
            return
        content = screen.ids.dashboard_content
        content.clear_widgets()

        today = date.today()
        all_requests = simulated_dashboard_requests(today)
        counts = {
            status: sum(item["status"] == status for item in all_requests)
            for status in STATUS_LABELS
        }
        total = len(all_requests)
        completed = counts["completed"]
        completed_percent = round(completed * 100 / total) if total else 0

        screen.ids.dashboard_data_status.text = (
            f"SIMULACIÓN · {SIMULATED_REQUEST_COUNT} registros ficticios; "
            "no son datos reales."
        )
        for days, button_id in (
            (1, "period_today"),
            (7, "period_week"),
            (30, "period_month"),
        ):
            button = screen.ids[button_id]
            button.style = "filled" if days == self.dashboard_period else "tonal"

        metrics = MDBoxLayout(
            orientation="vertical", spacing=dp(7), size_hint_y=None,
        )
        metrics.bind(minimum_height=metrics.setter("height"))
        metric_rows = (
            (
                self._dashboard_metric(str(total), "Solicitudes totales"),
                self._dashboard_metric(
                    str(total - completed), "Abiertas",
                ),
            ),
            (
                self._dashboard_metric(
                    f"{completed_percent}%", "Completadas",
                    f"{completed} de {total}",
                ),
                self._dashboard_metric(
                    str(counts["pending"]), "Pendientes",
                    "requieren atención" if counts["pending"] else "",
                    color="#B42323" if counts["pending"] else FOREST,
                ),
            ),
            (
                self._dashboard_metric(
                    self._average_duration(
                        all_requests, "created_at", "accepted_at",
                    ),
                    "Hasta aceptar",
                    "Promedio",
                ),
                self._dashboard_metric(
                    self._average_duration(
                        all_requests, "accepted_at", "completed_at",
                    ),
                    "Hasta completar",
                    "Promedio",
                ),
            ),
        )
        for left_metric, right_metric in metric_rows:
            row = MDBoxLayout(
                orientation="horizontal", spacing=dp(7),
                size_hint_y=None, height=dp(62),
            )
            row.add_widget(left_metric)
            row.add_widget(right_metric)
            metrics.add_widget(row)
        content.add_widget(self._dashboard_card("Resumen", [metrics]))

        alerts = []
        for request in sorted(
            all_requests,
            key=lambda item: item.get("date", ""),
            reverse=True,
        ):
            request_id = request.get("id", "Solicitud")
            status = request.get("status")
            if status == "pending":
                reason = request.get("pending_reason", "").strip()
                alerts.append((
                    f"● {request_id} pendiente: "
                    f"{reason or 'requiere atención'}",
                    "#B42323",
                ))
                continue
            try:
                age = (today - date.fromisoformat(request["date"])).days
            except (KeyError, TypeError, ValueError):
                continue
            if age >= 3 and status == "submitted":
                alerts.append((
                    f"! {request_id} lleva {age} días sin revisar",
                    "#8A5A18",
                ))
            elif age >= 3 and status == "accepted":
                alerts.append((
                    f"! {request_id} está aceptada y falta asignar trabajador",
                    "#8A5A18",
                ))
        alert_rows = [
            self._label(text, size=11, height=31, color_hex=color)
            for text, color in alerts[:4]
        ] or [self._label(
            "No hay alertas que requieran atención.",
            size=11, height=25, color_hex=MUTED,
        )]
        content.add_widget(self._dashboard_card("Alertas", alert_rows))

        dashboard_status_labels = {
            "submitted": "Por revisar",
            "accepted": "Aceptadas",
            "assigned": "Asignadas",
            "in_progress": "En curso",
            "pending": "Pendientes",
            "completed": "Completadas",
        }
        status_rows = [
            self._dashboard_bar_row(
                dashboard_status_labels[status], counts[status],
                max(counts.values(), default=0),
                color=(
                    "#B42323" if status == "pending"
                    else "#9CB7A5" if status == "submitted"
                    else "#638E73" if status == "accepted"
                    else FOREST
                ),
            )
            for status in STATUS_LABELS
        ]
        content.add_widget(self._dashboard_card(
            "Solicitudes por estado", status_rows,
        ))

        period_days = self.dashboard_period
        period_start = today - timedelta(days=period_days - 1)
        bucket_count = min(7, period_days)
        date_buckets = []
        for index in range(bucket_count):
            start_offset = index * period_days // bucket_count
            end_offset = (index + 1) * period_days // bucket_count - 1
            date_buckets.append((
                period_start + timedelta(days=start_offset),
                period_start + timedelta(days=max(start_offset, end_offset)),
            ))
        created_counts = []
        completed_counts = []
        date_labels_text = []
        for start_day, end_day in date_buckets:
            date_labels_text.append(
                "Hoy" if period_days == 1 else end_day.strftime("%d/%m")
            )
            created_counts.append(sum(
                request_day is not None and start_day <= request_day <= end_day
                for item in all_requests
                for request_day in [self._dashboard_date(item.get("date"))]
            ))
            completed_counts.append(sum(
                item.get("status") == "completed"
                and completion_day is not None
                and start_day <= completion_day <= end_day
                for item in all_requests
                for completion_day in [
                    self._dashboard_date(item.get("completed_at")),
                ]
            ))
        chart = MDBoxLayout(
            orientation="vertical", size_hint_y=None, height=dp(100),
        )
        chart.add_widget(DashboardBarChart(
            created_counts, completed_counts,
            size_hint_y=None, height=dp(77),
        ))
        date_labels = MDBoxLayout(
            orientation="horizontal", size_hint_y=None, height=dp(18),
        )
        for day_label_text in date_labels_text:
            day_label = self._label(
                day_label_text, size=9, height=18,
                color_hex=MUTED,
            )
            day_label.halign = "center"
            date_labels.add_widget(day_label)
        chart.add_widget(date_labels)
        legend = MDBoxLayout(
            orientation="horizontal", spacing=dp(10),
            size_hint_y=None, height=dp(20),
        )
        for color, text in (
            ("#173E31", "Creadas"),
            ("#9CB7A5", "Completadas"),
        ):
            entry = MDBoxLayout(
                orientation="horizontal", spacing=dp(4),
                size_hint=(None, None), size=(dp(120), dp(18)),
            )
            dot = Widget(size_hint=(None, None), size=(dp(7), dp(7)))
            with dot.canvas.before:
                Color(*get_color_from_hex(color))
                dot.background = RoundedRectangle(
                    pos=dot.pos, size=dot.size, radius=[dp(2)],
                )
            dot.bind(
                pos=lambda widget, _value, shape=dot.background:
                setattr(shape, "pos", widget.pos),
                size=lambda widget, _value, shape=dot.background:
                setattr(shape, "size", widget.size),
            )
            entry.add_widget(dot)
            entry.add_widget(self._label(
                text, size=9, height=18, color_hex=MUTED,
            ))
            legend.add_widget(entry)
        chart_rows = [
            legend,
            chart,
        ]
        content.add_widget(self._dashboard_card(
            f"Últimos {period_days} días" if period_days > 1 else "Hoy",
            chart_rows,
        ))

        zones: dict[str, dict[str, int | str]] = {}
        for request in all_requests:
            name = request.get("neighborhood", "").strip() or "Sin colonia"
            key = name.casefold()
            zone = zones.setdefault(key, {"name": name, "total": 0, "open": 0})
            zone["total"] = int(zone["total"]) + 1
            if request["status"] != "completed":
                zone["open"] = int(zone["open"]) + 1
        ranked_zones = sorted(
            zones.values(), key=lambda zone: int(zone["total"]), reverse=True,
        )[:5]
        zone_rows = []
        max_zone_count = max(
            (int(zone["total"]) for zone in ranked_zones), default=0,
        )
        for zone in ranked_zones:
            zone_rows.append(self._dashboard_bar_row(
                str(zone["name"]), int(zone["total"]), max_zone_count,
                detail=str(zone["total"]),
            ))
            open_count = int(zone["open"])
            open_label = "abierta" if open_count == 1 else "abiertas"
            zone_rows.append(self._label(
                f"{open_count} {open_label}",
                size=9, height=15, color_hex=MUTED,
            ))
        if not zone_rows:
            zone_rows.append(self._label(
                "Sin solicitudes en este periodo.",
                size=12, height=25, color_hex=MUTED,
            ))
        content.add_widget(self._dashboard_card(
            "Zonas con más solicitudes", zone_rows,
        ))

        worker_rows = []
        workers = self.service.list_workers()
        for worker in workers:
            worker_requests = [
                item for item in self.service.requests
                if item.get("worker") == worker["name"]
            ]
            in_course = sum(
                item["status"] in {"assigned", "in_progress"}
                for item in worker_requests
            )
            pending = sum(item["status"] == "pending" for item in worker_requests)
            finished = sum(
                item["status"] == "completed" for item in worker_requests
            )
            active = in_course + pending
            active_label = "activo" if active == 1 else "activos"
            worker_rows.append(self._label(
                f"{worker['name']}  ·  {active} {active_label}",
                size=11, height=21, bold=True,
            ))
            worker_rows.append(DashboardSegmentBar(
                [in_course, pending, finished],
                [FOREST, "#B42323", "#9CB7A5"],
                size_hint_y=None, height=dp(8),
            ))
            worker_rows.append(self._label(
                f"{in_course} en curso · {pending} pendientes · "
                f"{finished} completados",
                size=9, height=16, color_hex=MUTED,
            ))
        if not worker_rows:
            worker_rows.append(self._label(
                "No hay trabajadores registrados.",
                size=12, height=25, color_hex=MUTED,
            ))
        content.add_widget(self._dashboard_card("Carga del equipo", worker_rows))

        quantity_order = (
            "1 montón", "2 montones", "3 montones", "Más de 3 montones",
        )
        quantity_counts = {quantity: 0 for quantity in quantity_order}
        for request in all_requests:
            quantity = request.get("quantity", "Sin cantidad")
            quantity_counts[quantity] = quantity_counts.get(quantity, 0) + 1
        quantity_rows = [
            self._dashboard_bar_row(
                quantity.replace(" montones", "").replace(" montón", ""),
                count, max(quantity_counts.values(), default=0),
                color="#8A6B43",
            )
            for quantity, count in quantity_counts.items()
        ]
        content.add_widget(self._dashboard_card(
            "Cantidad de ramas por solicitud", quantity_rows,
        ))

        recent = sorted(
            all_requests,
            key=lambda item: item.get("date", ""),
            reverse=True,
        )[:6]
        activity_rows = [
            self._label(
                f"{item.get('date', '')}  ·  {item.get('id', '')}: creada por "
                f"{item.get('name', '')} · "
                f"{STATUS_LABELS.get(item.get('status', ''), 'Sin estado')}",
                size=10, height=35, color_hex=INK,
            )
            for item in recent
        ] or [self._label(
            "Aún no hay solicitudes registradas.",
            size=12, height=25, color_hex=MUTED,
        )]
        content.add_widget(self._dashboard_card(
            "Actividad reciente", activity_rows,
        ))

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
                color_hex=MUTED, height=32,
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
            assignment_height = 32
            if len(assignment_text) > 52:
                assignment_height = 52
            worker_card = MDCard(
                style="outlined", orientation="vertical", padding=dp(10),
                spacing=dp(4), size_hint_y=None,
                height=dp(24 + 20 + assignment_height + 40 + 32),
            )
            worker_card.add_widget(self._label(
                worker["name"], size=15, height=24, bold=True,
            ))
            worker_card.add_widget(self._label(
                f"Usuario: {worker['username']}", size=13,
                color_hex=MUTED, height=20,
            ))
            worker_card.add_widget(self._label(
                assignment_text, size=12,
                color_hex=FOREST if assigned_requests else MUTED,
                height=assignment_height,
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
                f"{heading}  ·  {len(requests)}", size=16, height=36, bold=True,
            ))
            if not requests:
                container.add_widget(self._label(
                    "No hay solicitudes en esta etapa.", size=14,
                    color_hex=MUTED, height=32,
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
                color_hex=MUTED, height=42,
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
                height=22, bold=True,
            ))
        card.add_widget(self._label(
            f"{request['id']}  ·  {request['date']}", size=14,
            color_hex=MUTED, height=24, bold=True,
        ))
        card.add_widget(self._label(
            f"{request['address']} · {request['neighborhood']}",
            size=16, height=38, bold=True,
        ))
        card.add_widget(self._label(
            f"{request['name']}  ·  {request['quantity']}  ·  {STATUS_LABELS[request['status']]}",
            size=14, color_hex=FOREST, height=26,
        ))
        if request.get("worker"):
            card.add_widget(self._label(
                f"Responsable: {request['worker']}", size=14,
                color_hex=MUTED, height=23,
            ))
        if request.get("description"):
            card.add_widget(self._label(
                request["description"], size=14, color_hex=MUTED, height=34,
            ))
        if request.get("pending_reason"):
            card.add_widget(self._label(
                f"Motivo pendiente: {request['pending_reason']}", size=14,
                color_hex="#70410F", height=40,
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
        card.height = max(card.height, card.minimum_height + dp(26))
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
        if self.selected_photo_path:
            fields.photo_status.text = "Foto seleccionada correctamente"
            fields.photo_preview.source = self.selected_photo_path
            fields.photo_preview_card.height = dp(150)
            fields.photo_preview_card.opacity = 1
            fields.photo_preview_card.disabled = False
        else:
            fields.photo_status.text = "Foto obligatoria: elige o toma una foto."
            fields.photo_preview.source = ""
            fields.photo_preview_card.height = 0
            fields.photo_preview_card.opacity = 0
            fields.photo_preview_card.disabled = True
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
        screen.ids.photo_preview.source = ""
        screen.ids.photo_preview_card.height = 0
        screen.ids.photo_preview_card.opacity = 0
        screen.ids.photo_preview_card.disabled = True
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
        cancel_button = self._dialog_button("Cancelar", style="text", width=110)
        delete_button = self._dialog_button("Borrar solicitud", style="tonal", width=150)
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
        except (ValueError, OSError) as error:
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
        cancel_button = self._dialog_button("Cancelar", style="text", width=110)
        save_button = self._dialog_button("Guardar", style="filled", width=130)
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
        cancel_button = self._dialog_button("Cancelar", style="text", width=110)
        save_button = self._dialog_button("Guardar", style="filled", width=130)
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
        except (ValueError, OSError) as error:
            self._show_dialog("No se pudo guardar", str(error))
            return
        dialog.dismiss()
        self.refresh_all()

    def _confirm_delete_worker(self, worker: dict[str, str]) -> None:
        if not self.current_user or self.current_user["role"] != "admin":
            return
        cancel_button = self._dialog_button("Cancelar", style="text", width=110)
        delete_button = self._dialog_button("Eliminar", style="tonal", width=130)
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
        except (ValueError, OSError) as error:
            self._show_dialog("No se pudo finalizar", str(error))
            return
        self.refresh_all()
        self._notify(f"Retiro {request_id} finalizado.")

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
            f"{stop['address']}, {stop['neighborhood']}, "
            f"{self.remote_config['municipality']}"
            for stop in stops
        ]
        params = {
            "api": "1",
            "origin": "Current Location",
            "destination": locations[-1],
            "travelmode": "driving",
        }
        if len(locations) > 1:
            params["waypoints"] = "optimize:true|" + "|".join(locations[:-1])
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
        except (ValueError, OSError) as error:
            self._show_dialog("No se pudo enviar", str(error))
            return
        self._clear_request_form()
        self.refresh_all()
        self._notify(success_message)

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
        except (ValueError, OSError) as error:
            self._show_dialog("No se pudo actualizar", str(error))
            return
        self.refresh_all()
        request = self.service.get(request_id)
        if status == "assigned":
            message = f"Solicitud {request_id} asignada a {request['worker']}."
        else:
            message = f"{request_id}: {STATUS_LABELS[status].lower()}."
        self._notify(message)


if __name__ == "__main__":
    RamaMobileApp().run()
