from __future__ import annotations

from threading import Thread

from kivy.clock import Clock
from kivy.logger import Logger
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.dialog import (
    MDDialog,
    MDDialogButtonContainer,
    MDDialogContentContainer,
    MDDialogHeadlineText,
    MDDialogSupportingText,
)
from kivymd.uix.textfield import MDTextField, MDTextFieldHintText

from ..email_service import (
    EmailConfigError,
    EmailSendError,
    send_password_reset_email,
    send_welcome_email,
)
from ..request_service import RESET_CODE_TTL_SECONDS


class AuthenticationActions:
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
        self._configure_numeric_field(phone, 9)
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
