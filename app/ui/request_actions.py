from __future__ import annotations

import webbrowser
from pathlib import Path
from urllib.parse import urlencode

from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivymd.uix.dialog import (
    MDDialog,
    MDDialogButtonContainer,
    MDDialogContentContainer,
    MDDialogHeadlineText,
    MDDialogSupportingText,
)
from kivymd.uix.textfield import MDTextField, MDTextFieldHintText

from ..request_service import STATUS_LABELS


class RequestActions:
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
        self._configure_numeric_field(phone_field, 9)
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
        if len(phone) != 9 or not phone.isdigit():
            self._show_dialog("Revisa el teléfono", "Escribe un número de contacto de exactamente 9 dígitos.")
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
