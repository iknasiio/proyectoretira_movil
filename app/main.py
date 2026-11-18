from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from threading import Thread

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.logger import Logger
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty
from kivy.utils import get_color_from_hex
from kivy.utils import platform
from kivymd.app import MDApp
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField
from requests.exceptions import RequestException

from .remote_config import (
    DEFAULT_REMOTE_CONFIG,
    DEFAULT_REMOTE_CONFIG_URL,
    RemoteConfigError,
    fetch_remote_config,
)
from .request_service import RequestService
from .ui.auth import AuthenticationActions
from .ui.components import ComponentActions
from .ui.constants import FOREST, INK, MUTED
from .ui.dashboard import DashboardActions
from .ui.kv_loader import load_kv_files
from .ui.request_actions import RequestActions
from .ui.request_photos import RequestPhotos
from .ui.request_views import RequestViews
from .ui.screens import (
    AdminScreen,
    CitizenScreen,
    DashboardBarChart,
    DashboardScreen,
    LoginScreen,
    RamaRoot,
    RecoveryScreen,
    WorkerScreen,
)

APP_DIR = Path(__file__).resolve().parent


class RamaMobileApp(
    ComponentActions,
    AuthenticationActions,
    DashboardActions,
    RequestViews,
    RequestPhotos,
    RequestActions,
    MDApp,
):
    dark_mode = BooleanProperty(False)
    page_color = ListProperty([0.96, 0.97, 0.95, 1])
    surface_color = ListProperty([1, 1, 1, 1])
    soft_surface_color = ListProperty([0.94, 0.96, 0.93, 1])
    primary_text_color = ListProperty([0.11, 0.18, 0.15, 1])
    secondary_text_color = ListProperty([0.29, 0.34, 0.30, 1])
    accent_text_color = ListProperty([0.11, 0.24, 0.19, 1])

    def build(self):
        self.title = "Rama | Retiro de poda"
        self.config.setdefaults("appearance", {"dark_mode": "0"})
        self.dark_mode = self.config.getboolean("appearance", "dark_mode")
        self._apply_appearance()
        self.theme_cls.primary_palette = "Green"
        if platform not in {"android", "ios"}:
            Window.size = (430, 850)
        private_data_dir = Path(self.user_data_dir)
        data_dir = (
            private_data_dir
            if platform in {"android", "ios"}
            else APP_DIR.parent / "json"
        )
        self.service = RequestService(
            data_dir=data_dir,
            legacy_data_path=private_data_dir / "rama_data.json",
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
        load_kv_files()
        return RamaRoot()

    def toggle_dark_mode(self) -> None:
        self.dark_mode = not self.dark_mode
        self._apply_appearance()
        self.config.set(
            "appearance", "dark_mode", "1" if self.dark_mode else "0",
        )
        self.config.write()
        if self.current_user:
            self.refresh_all()

    def _apply_appearance(self) -> None:
        Window.clearcolor = self.page_color
        if self.dark_mode:
            self.theme_cls.theme_style = "Dark"
            self.page_color = [0.07, 0.09, 0.08, 1]
            self.surface_color = [0.11, 0.15, 0.12, 1]
            self.soft_surface_color = [0.17, 0.23, 0.19, 1]
            self.primary_text_color = [0.90, 0.94, 0.91, 1]
            self.secondary_text_color = [0.69, 0.76, 0.71, 1]
            self.accent_text_color = [0.66, 0.85, 0.72, 1]
        else:
            self.theme_cls.theme_style = "Light"
            self.page_color = [0.96, 0.97, 0.95, 1]
            self.surface_color = [1, 1, 1, 1]
            self.soft_surface_color = [0.94, 0.96, 0.93, 1]
            self.primary_text_color = [0.11, 0.18, 0.15, 1]
            self.secondary_text_color = [0.29, 0.34, 0.30, 1]
            self.accent_text_color = [0.11, 0.24, 0.19, 1]

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
        self._configure_numeric_field(citizen.ids.phone, 9)
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

    @staticmethod
    def _configure_numeric_field(field: MDTextField, max_length: int) -> None:
        field.input_filter = "int"
        field.bind(
            text=lambda widget, value:
            setattr(widget, "text", value[:max_length])
            if len(value) > max_length else None,
        )

    def refresh_all(self) -> None:
        if not hasattr(self, "service") or not self.root:
            return
        self.refresh_citizen()
        self.refresh_admin()
        self.refresh_worker()
        self.refresh_dashboard()


if __name__ == "__main__":
    RamaMobileApp().run()
