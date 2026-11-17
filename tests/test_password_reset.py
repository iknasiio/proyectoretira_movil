import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app import email_service
from app.request_service import RequestService


class PasswordResetTests(unittest.TestCase):
    def setUp(self):
        self.service = RequestService()

    def test_code_changes_password_once(self):
        reset = self.service.create_password_reset("ELENA")
        self.assertRegex(reset["code"], r"^\d{6}$")
        self.assertEqual(reset["email"], "elena@example.com")
        self.service.reset_password("elena", reset["code"], "nueva123")
        self.assertIsNone(self.service.authenticate("elena", "elena123"))
        self.assertIsNotNone(self.service.authenticate("elena", "nueva123"))
        with self.assertRaises(ValueError):
            self.service.reset_password("elena", reset["code"], "otra1234")

    def test_wrong_code_is_limited_to_five_attempts(self):
        reset = self.service.create_password_reset("elena")
        wrong = "000000" if reset["code"] != "000000" else "111111"
        for _ in range(4):
            with self.assertRaisesRegex(ValueError, "incorrecto"):
                self.service.reset_password("elena", wrong, "nueva123")
        with self.assertRaisesRegex(ValueError, "Demasiados"):
            self.service.reset_password("elena", wrong, "nueva123")
        with self.assertRaises(ValueError):
            self.service.reset_password("elena", reset["code"], "nueva123")
        self.assertIsNotNone(self.service.authenticate("elena", "elena123"))

    def test_expired_code_is_rejected(self):
        reset = self.service.create_password_reset("elena")
        with patch("app.request_service.time.monotonic", return_value=1e12):
            with self.assertRaisesRegex(ValueError, "venció"):
                self.service.reset_password("elena", reset["code"], "nueva123")

    def test_unknown_user_or_missing_email_gets_no_code(self):
        self.assertIsNone(self.service.create_password_reset("nadie"))
        self.service.accounts[0]["email"] = ""
        self.assertIsNone(
            self.service.create_password_reset(self.service.accounts[0]["username"])
        )

    def test_new_password_persists_on_disk(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "data.json"
            service = RequestService(path)
            reset = service.create_password_reset("lucia")  # trabajadora
            service.reset_password("lucia", reset["code"], "nuevaclave")
            restored = RequestService(path)
            self.assertIsNotNone(restored.authenticate("lucia", "nuevaclave"))
            self.assertNotIn("code", json.loads(path.read_text()))

    def test_short_password_is_rejected(self):
        reset = self.service.create_password_reset("elena")
        with self.assertRaises(ValueError):
            self.service.reset_password("elena", reset["code"], "123")


class EmailTests(unittest.TestCase):
    SETTINGS = email_service.EmailSettings(
        "smtp.test", 587, "app@test.cl", "secreto", "app@test.cl",
    )

    def test_missing_config_raises(self):
        with patch.object(email_service, "SETTINGS_FILE", Path("/no/existe.json")), \
                patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(email_service.EmailConfigError):
                email_service.load_email_settings()

    def test_env_config_is_loaded(self):
        env = {"RAMA_SMTP_HOST": "smtp.gmail.com", "RAMA_SMTP_USER": "a@b.cl",
               "RAMA_SMTP_PASSWORD": "x"}
        with patch.object(email_service, "SETTINGS_FILE", Path("/no/existe.json")), \
                patch.dict("os.environ", env, clear=True):
            settings = email_service.load_email_settings()
        self.assertEqual((settings.port, settings.sender), (587, "a@b.cl"))

    def test_emails_are_sent_with_expected_content(self):
        server = MagicMock()
        with patch.object(email_service, "load_email_settings", return_value=self.SETTINGS), \
                patch("app.email_service.smtplib.SMTP") as smtp:
            smtp.return_value.__enter__.return_value = server
            email_service.send_welcome_email("x@y.cl", "Ana <b>Pérez")
            email_service.send_password_reset_email("x@y.cl", "Ana", "123456", 10)
        welcome, reset = [c.args[0] for c in server.send_message.call_args_list]
        self.assertIn("Felicidades por ser nuevo usuario", welcome.get_body(("plain",)).get_content())
        self.assertNotIn("<b>", welcome.get_body(("html",)).get_content().split("Felicidades,")[1][:20])
        self.assertIn("123456", reset["Subject"])
        self.assertEqual(server.starttls.call_count, 2)
        self.assertEqual(server.login.call_count, 2)


if __name__ == "__main__":
    unittest.main()
