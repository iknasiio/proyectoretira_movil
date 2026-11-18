from __future__ import annotations

from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex
from kivymd.uix.screen import MDScreen


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
    def __init__(
        self, created: list[int], completed: list[int],
        *, dark_mode: bool = False, **kwargs,
    ):
        self.created = created
        self.completed = completed
        self.dark_mode = dark_mode
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
        baseline_color = "#506156" if self.dark_mode else "#E4ECE6"
        grid_color = "#35453A" if self.dark_mode else "#EDF1EE"
        created_color = "#70AA7D" if self.dark_mode else "#173E31"
        with self.canvas:
            Color(*get_color_from_hex(baseline_color))
            Line(
                points=(self.x, baseline, self.right, baseline),
                width=dp(0.7),
            )
            Color(*get_color_from_hex(grid_color))
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
                    (-bar_width / 2, created, created_color),
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
    def __init__(
        self, values: list[int], colors: list[str],
        *, dark_mode: bool = False, **kwargs,
    ):
        self.values = values
        self.colors = colors
        self.dark_mode = dark_mode
        super().__init__(**kwargs)
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *_args) -> None:
        self.canvas.clear()
        total = sum(self.values)
        with self.canvas:
            background_color = "#33443A" if self.dark_mode else "#E4ECE6"
            Color(*get_color_from_hex(background_color))
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
                if self.dark_mode and color == "#173E31":
                    color = "#70AA7D"
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
