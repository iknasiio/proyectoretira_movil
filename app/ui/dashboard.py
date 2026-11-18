from __future__ import annotations

from datetime import date, datetime, timedelta
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from ..demo_data import SIMULATED_REQUEST_COUNT, simulated_dashboard_requests
from ..request_service import STATUS_LABELS
from .constants import FOREST, INK, MUTED
from .screens import DashboardBarChart, DashboardSegmentBar


class DashboardActions:
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
            md_bg_color=get_color_from_hex(
                "#33443A" if self.dark_mode else "#E4ECE6",
            ),
        )
        ratio = value / maximum if maximum else 0
        if ratio > 0:
            bar = MDBoxLayout(
                size_hint_x=max(0.04, ratio),
                md_bg_color=get_color_from_hex(self._theme_color(color)),
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
            dark_mode=self.dark_mode,
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
            if self.dark_mode and color == "#173E31":
                color = "#70AA7D"
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
                dark_mode=self.dark_mode,
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
