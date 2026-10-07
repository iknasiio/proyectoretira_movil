from pathlib import Path

from kivy.clock import Clock
from kivy.core.window import Window

from main import RamaMobileApp


CAPTURE_DIR = Path(__file__).parent / "capturas"
SCREENS = (
    ("elena", "elena123", "citizen", "ciudadano.png"),
    ("admin", "admin123", "admin", "administracion.png"),
    ("lucia", "lucia123", "worker", "trabajador.png"),
)


class CaptureScreensApp(RamaMobileApp):
    def on_start(self):
        super().on_start()
        CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        for old_capture in CAPTURE_DIR.glob("*.png"):
            old_capture.unlink()
        self.login_as("admin", "admin123")
        Clock.schedule_once(self.warm_up, 1.0)

    def warm_up(self, _dt):
        Window.screenshot(name=str(CAPTURE_DIR / "warmup.png"))
        Clock.schedule_once(self.begin_captures, 0.8)

    def begin_captures(self, _dt):
        for old_capture in CAPTURE_DIR.glob("*.png"):
            old_capture.unlink()
        self.capture_index = 0
        self.capture_next(0)

    def capture_next(self, _dt):
        if self.capture_index >= len(SCREENS):
            self.stop()
            return
        if self.current_user:
            self.sign_out()
        username, password, screen_name, filename = SCREENS[self.capture_index]
        self.login_as(username, password)
        Clock.schedule_once(lambda _step: self.save_capture(filename), 0.7)

    def login_as(self, username, password):
        login = self.root.ids.screen_manager.get_screen("login")
        login.ids.login_username.text = username
        login.ids.login_password.text = password
        self.sign_in()

    def save_capture(self, filename):
        destination = CAPTURE_DIR / filename
        Window.screenshot(name=str(destination))
        generated = CAPTURE_DIR / f"{Path(filename).stem}0001.png"
        if generated.exists() and generated != destination:
            generated.replace(destination)
        print(f"Captura guardada: {destination}")
        self.capture_index += 1
        Clock.schedule_once(self.capture_next, 0.5)


if __name__ == "__main__":
    CaptureScreensApp().run()
