from __future__ import annotations

import webbrowser
from urllib.parse import urlencode

from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
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
        Builder.load_file("rama.kv")
        return RamaRoot()

    def on_start(self):
        self.root.ids.screen_manager.current = "login"
        self.root.ids.nav_bar.height = 0
        self.root.ids.nav_bar.opacity = 0

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

    def _button(self, text: str, callback, *, style: str = "filled") -> MDButton:
        button = MDButton(style=style, size_hint=(1, None), height=dp(44))
        button.add_widget(MDButtonText(text=text, font_size=dp(14)))
        button.bind(on_release=lambda *_args: callback())
        return button

    def _show_dialog(self, title: str, message: str) -> None:
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
        dialog.open()

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
            container.add_widget(self._request_card(request))

    def refresh_admin(self) -> None:
        if not self.root or "screen_manager" not in self.root.ids:
            return
        screen = self.root.ids.screen_manager.get_screen("admin")
        container = screen.ids.admin_requests
        container.clear_widgets()
        pending = sum(item["status"] == "submitted" for item in self.service.requests)
        waiting = sum(item["status"] == "accepted" for item in self.service.requests)
        active = sum(item["status"] in {"assigned", "in_progress"} for item in self.service.requests)
        active += sum(item["status"] == "pending" for item in self.service.requests)
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
            worker_card = MDCard(
                style="outlined", orientation="vertical", padding=dp(10),
                spacing=dp(4), size_hint_y=None, height=dp(112),
            )
            worker_card.add_widget(self._label(
                worker["name"], size=15, height=dp(24), bold=True,
            ))
            worker_card.add_widget(self._label(
                f"Usuario: {worker['username']}", size=13,
                color_hex=MUTED, height=dp(20),
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

    def _request_card(self, request: dict, *, admin_actions: bool = False,
                      worker_actions: bool = False,
                      stop_number: int | None = None) -> MDCard:
        extra_height = 0
        if admin_actions and request["status"] == "submitted":
            extra_height = 54
        elif admin_actions and request["status"] == "accepted":
            extra_height = 106
        elif worker_actions:
            extra_height = 54
        if request.get("worker"):
            extra_height += 27
        if request.get("description"):
            extra_height += 38
        if request.get("pending_reason"):
            extra_height += 44
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

        if admin_actions and request["status"] == "submitted":
            card.add_widget(self._button(
                "Aceptar solicitud",
                lambda rid=request["id"]: self._change_status(rid, "accepted"),
            ))
        elif admin_actions and request["status"] == "accepted":
            picker = Spinner(
                text="Selecciona trabajador", values=self.service.worker_names,
                size_hint_y=None, height=dp(48),
                background_normal="", background_color=(0.95, 0.96, 0.94, 1),
                color=(0.11, 0.24, 0.19, 1), font_size=dp(14),
            )
            card.add_widget(picker)
            card.add_widget(self._button(
                "Asignar trabajador",
                lambda rid=request["id"], select=picker: self._assign(rid, select.text),
            ))
        elif worker_actions:
            actions = MDBoxLayout(
                orientation="horizontal", spacing=dp(5),
                size_hint_y=None, height=dp(50),
            )
            if request["status"] == "assigned":
                primary_text, primary_status = "Iniciar", "in_progress"
            elif request["status"] == "pending":
                primary_text, primary_status = "Reanudar", "in_progress"
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
            username_field, name_field, password_field,
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
            password_field.text,
        ))
        dialog.open()

    def _save_worker(self, dialog, worker: dict[str, str] | None,
                     username: str, name: str, password: str) -> None:
        try:
            if worker:
                self.service.update_worker(
                    worker["username"], username=username,
                    name=name, password=password,
                )
            else:
                self.service.create_worker(
                    username=username, name=name, password=password,
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
            request = self.service.create(
                name=name, phone=phone, address=address,
                neighborhood=neighborhood, quantity=quantity,
                description=description,
            )
        except ValueError as error:
            self._show_dialog("No se pudo enviar", str(error))
            return
        fields.address.text = ""
        fields.neighborhood.text = ""
        fields.details.text = ""
        self.refresh_all()
        self._show_dialog("Solicitud enviada", f"Registramos {request['id']}. Administración la revisará.")

    def _assign(self, request_id: str, worker: str) -> None:
        if not self.current_user or self.current_user["role"] != "admin":
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
