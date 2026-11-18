import unittest
from unittest.mock import Mock

from app.main import RamaMobileApp


class AppearanceTests(unittest.TestCase):
    def test_dark_mode_toggles_theme_and_persists_preference(self):
        app = RamaMobileApp()
        app.config = Mock()
        app.current_user = None

        app.toggle_dark_mode()

        self.assertTrue(app.dark_mode)
        self.assertEqual(app.theme_cls.theme_style, "Dark")
        self.assertEqual(app._theme_color("#49564E"), "#B7C4BB")
        app.config.set.assert_called_once_with("appearance", "dark_mode", "1")
        app.config.write.assert_called_once_with()

        app.toggle_dark_mode()

        self.assertFalse(app.dark_mode)
        self.assertEqual(app.theme_cls.theme_style, "Light")
        self.assertEqual(app.config.set.call_count, 2)
        self.assertEqual(app.config.write.call_count, 2)


if __name__ == "__main__":
    unittest.main()
