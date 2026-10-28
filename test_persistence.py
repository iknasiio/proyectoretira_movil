import json
import tempfile
import unittest
from pathlib import Path

from request_service import RequestService


class RequestServicePersistenceTests(unittest.TestCase):
    def test_requests_and_accounts_survive_app_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "rama_data.json"
            service = RequestService(data_path)
            service.transition("RM-1048", "accepted")
            service.create(
                name="Ana Pérez",
                phone="5551234567",
                address="Calle Arce 18",
                neighborhood="Centro",
                quantity="2 montones",
                photo_path="foto.jpg",
            )
            service.register_account(
                username="ana",
                password="anapass",
                name="Ana Pérez",
                email="ana@example.com",
                phone="5551234567",
            )
            service.create_worker(
                username="sofia",
                name="Sofía Pérez",
                password="sofiapass",
                phone="5551234568",
            )

            restored = RequestService(data_path)

            self.assertEqual(restored.get("RM-1048")["status"], "accepted")
            self.assertEqual(restored.get("RM-1049")["name"], "Ana Pérez")
            self.assertEqual(
                restored.authenticate("ana", "anapass")["name"],
                "Ana Pérez",
            )
            self.assertEqual(
                restored.authenticate("sofia", "sofiapass")["role"],
                "worker",
            )
            self.assertIn("Sofía Pérez", restored.worker_names)

    def test_registered_username_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            service = RequestService(Path(directory) / "rama_data.json")
            service.register_account(
                username="ana",
                password="anapass",
                name="Ana Pérez",
                email="ana@example.com",
                phone="5551234567",
            )

            with self.assertRaisesRegex(ValueError, "ya está registrado"):
                service.register_account(
                    username=" ANA ",
                    password="otro123",
                    name="Ana Otra",
                    email="otra@example.com",
                    phone="5551234568",
                )

    def test_corrupt_json_is_reported_without_overwriting_it(self):
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "rama_data.json"
            original_contents = "{ datos incompletos"
            data_path.write_text(original_contents, encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "No se pudieron cargar"):
                RequestService(data_path)

            self.assertEqual(data_path.read_text(encoding="utf-8"), original_contents)

    def test_incomplete_json_records_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "rama_data.json"
            original_contents = json.dumps({
                "version": 1,
                "requests": [{}],
                "accounts": [],
                "workers": [],
            })
            data_path.write_text(original_contents, encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "registros inválidos"):
                RequestService(data_path)

            self.assertEqual(data_path.read_text(encoding="utf-8"), original_contents)

    def test_failed_save_rolls_back_the_in_memory_change(self):
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "rama_data.json"
            service = RequestService(data_path)
            blocked_directory = Path(directory) / "not-a-directory"
            blocked_directory.write_text("file", encoding="utf-8")
            service.data_path = blocked_directory / "rama_data.json"
            original_request_ids = [request["id"] for request in service.requests]

            with self.assertRaises(OSError):
                service.create(
                    name="Ana Pérez",
                    phone="5551234567",
                    address="Calle Arce 18",
                    neighborhood="Centro",
                    quantity="2 montones",
                    photo_path="foto.jpg",
                )

            self.assertEqual(
                [request["id"] for request in service.requests],
                original_request_ids,
            )

    def test_saved_file_has_explicit_schema_version(self):
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "rama_data.json"
            RequestService(data_path)

            saved_data = json.loads(data_path.read_text(encoding="utf-8"))

            self.assertEqual(saved_data["version"], 1)
            self.assertIsInstance(saved_data["requests"], list)
            self.assertIsInstance(saved_data["accounts"], list)
            self.assertIsInstance(saved_data["workers"], list)


if __name__ == "__main__":
    unittest.main()
