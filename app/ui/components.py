from __future__ import annotations

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex
from kivymd.uix.button import MDButton, MDButtonText
from kivymd.uix.dialog import (
    MDDialog,
    MDDialogButtonContainer,
    MDDialogHeadlineText,
    MDDialogSupportingText,
)
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField

from .constants import FOREST, INK, MUTED


class ComponentActions:
    def _theme_color(self, color_hex: str) -> str:
        if not getattr(self, "dark_mode", False):
            return color_hex
        return {
            INK: "#E6EEE8",
            MUTED: "#B7C4BB",
            FOREST: "#A8D9B6",
            "#70410F": "#E7C47A",
            "#8A5A18": "#E7BD72",
            "#B42323": "#FF7770",
        }.get(color_hex, color_hex)

    def _label(self, text: str, *, size: int = 15, color_hex: str = INK,
               height: int = 25, bold: bool = False) -> MDLabel:
        color_hex = self._theme_color(color_hex)
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
            button.md_bg_color = get_color_from_hex(
                self._theme_color(background_color),
            )
        elif style == "filled":
            button.md_bg_color = get_color_from_hex(
                "#2E6345" if getattr(self, "dark_mode", False) else FOREST,
            )
        elif style == "tonal":
            button.md_bg_color = get_color_from_hex(
                "#2B3B31" if getattr(self, "dark_mode", False)
                else "#E4ECE6",
            )
        else:
            button.md_bg_color = get_color_from_hex(
                "#18221B" if getattr(self, "dark_mode", False) else "#FDFEFD",
            )
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
            text_color = self._theme_color(FOREST)
            button_text.text_color = get_color_from_hex(text_color)
            button_text.disabled_color = get_color_from_hex(text_color)
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
        dark_mode = getattr(self, "dark_mode", False)
        if style == "filled":
            button.md_bg_color = get_color_from_hex(
                "#2E6345" if dark_mode else FOREST,
            )
            button_text.theme_text_color = "Custom"
            button_text.text_color = get_color_from_hex("#FFFFFF")
            button_text.disabled_color = get_color_from_hex("#FFFFFF")
        elif style == "tonal":
            button.md_bg_color = get_color_from_hex(
                "#2B3B31" if dark_mode else "#E4ECE6",
            )
            button_text.theme_text_color = "Custom"
            text_color = self._theme_color(FOREST)
            button_text.text_color = get_color_from_hex(text_color)
            button_text.disabled_color = get_color_from_hex(text_color)
        else:
            button.md_bg_color = get_color_from_hex(
                "#18221B" if dark_mode else "#FFFFFF",
            )
            button_text.theme_text_color = "Custom"
            text_color = self._theme_color(FOREST)
            button_text.text_color = get_color_from_hex(text_color)
            button_text.disabled_color = get_color_from_hex(text_color)
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
