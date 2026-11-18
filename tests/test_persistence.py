import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.request_service import DEMO_USERS, INITIAL_REQUESTS, RequestService


class RequestServicePersistenceTests(unittest.TestCase):
    def test_requests_and_accounts_survive_app_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / "rama_data.json"
            service = RequestService(data_path)
            service.transition("RM-1048", "accepted")
            service.create(
                name="Ana Pérez",
                phone="555123456",
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
                phone="555123456",
            )
            service.create_worker(
                username="sofia",
                name="Sofía Pérez",
                password="sofiapass",
                phone="555123457",
            )

            restored = RequestService(data_path)

            self.assertEqual(restored.get("RM-1048")["status"], "accepted")
            self.assertIn("accepted_at", restored.get("RM-1048"))
            self.assertIn("created_at", restored.get("RM-1049"))
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
                phone="555123456",
            )

            with self.assertRaisesRegex(ValueError, "ya está registrado"):
                service.register_account(
                    username=" ANA ",
                    password="otro123",
                    name="Ana Otra",
                    email="otra@example.com",
                    phone="555123457",
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
            service.data_dir = blocked_directory
            original_request_ids = [request["id"] for request in service.requests]

            with self.assertRaises(OSError):
                service.create(
                    name="Ana Pérez",
                    phone="555123456",
                    address="Calle Arce 18",
                    neighborhood="Centro",
                    quantity="2 montones",
                    photo_path="foto.jpg",
                )

            self.assertEqual(
                [request["id"] for request in service.requests],
                original_request_ids,
            )

    def test_partial_split_save_restores_files_and_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            service = RequestService(data_dir=Path(directory))
            original_files = {
                path: path.read_bytes()
                for path in service.data_files.values()
            }
            original_request_ids = [request["id"] for request in service.requests]
            replace = os.replace
            replace_calls = 0

            def fail_second_replace(source, destination):
                nonlocal replace_calls
                replace_calls += 1
                if replace_calls == 2:
                    raise OSError("replace failed")
                replace(source, destination)

            with patch(
                "app.request_service.os.replace",
                side_effect=fail_second_replace,
            ):
                with self.assertRaisesRegex(OSError, "replace failed"):
                    service.create(
                        name="Ana Pérez",
                        phone="555123456",
                        address="Calle Arce 18",
                        neighborhood="Centro",
                        quantity="2 montones",
                        photo_path="foto.jpg",
                    )

            self.assertEqual(
                [request["id"] for request in service.requests],
                original_request_ids,
            )
            for path, contents in original_files.items():
                with self.subTest(file=path.name):
                    self.assertEqual(path.read_bytes(), contents)
            self.assertFalse(list(Path(directory).glob("*.tmp")))

    def test_saved_file_has_explicit_schema_version(self):
        with tempfile.TemporaryDirectory() as directory:
            service = RequestService(data_dir=Path(directory))

            for key, path in service.data_files.items():
                with self.subTest(file=path.name):
                    saved_data = json.loads(path.read_text(encoding="utf-8"))
                    self.assertEqual(saved_data["version"], 1)
                    self.assertIsInstance(saved_data[key], list)

    def test_legacy_file_is_split_and_removed_after_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy_path = root / "rama_data.json"
            data_dir = root / "visible_data"
            legacy_path.write_text(
                json.dumps({
                    "version": 1,
                    "requests": INITIAL_REQUESTS,
                    "accounts": [
                        account for account in DEMO_USERS
                        if account["role"] != "worker"
                    ],
                    "workers": [
                        account for account in DEMO_USERS
                        if account["role"] == "worker"
                    ],
                }),
                encoding="utf-8",
            )

            service = RequestService(
                data_dir=data_dir,
                legacy_data_path=legacy_path,
            )

            self.assertEqual(service.get("RM-1048")["name"], "Elena Martínez")
            self.assertFalse(legacy_path.exists())
            self.assertEqual(
                {path.name for path in service.data_files.values()},
                {"solicitudes.json", "cuentas.json", "trabajadores.json"},
            )


if __name__ == "__main__":
    unittest.main()
