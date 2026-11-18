from __future__ import annotations

from kivy.metrics import dp
from kivy.uix.spinner import Spinner
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard

from ..request_service import STATUS_LABELS
from .constants import FOREST, MUTED


class RequestViews:
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
                background_normal="", background_color=(
                    (0.17, 0.23, 0.19, 1) if self.dark_mode
                    else (0.95, 0.96, 0.94, 1)
                ),
                color=tuple(self.accent_text_color), font_size=dp(14),
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
