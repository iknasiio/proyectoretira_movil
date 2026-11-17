import io
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from app.main import RamaMobileApp
from app.request_service import RequestService, WORKERS


class RequestServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = RequestService()

    def test_new_request_can_be_accepted_assigned_and_completed(self):
        request = self.service.create(
            name="Ana Pérez",
            phone="5551234567",
            address="Calle Arce 18",
            neighborhood="Centro",
            quantity="2 montones",
            photo_path="foto.jpg",
            description="Junto al portón verde.",
        )
        self.assertEqual(request["status"], "submitted")
        self.service.transition(request["id"], "accepted")
        self.service.transition(request["id"], "assigned", worker=WORKERS[0])
        self.service.transition(request["id"], "in_progress")
        self.service.transition(request["id"], "completed")
        self.assertEqual(self.service.get(request["id"])["status"], "completed")
        self.assertEqual(self.service.get(request["id"])["worker"], WORKERS[0])
        self.assertIn("created_at", request)
        self.assertIn("accepted_at", request)
        self.assertIn("completed_at", request)

    def test_worker_only_sees_their_active_assignments(self):
        self.service.transition("RM-1048", "accepted")
        self.service.transition("RM-1048", "assigned", worker=WORKERS[0])
        assignments = self.service.for_worker(WORKERS[0])
        self.assertEqual({item["id"] for item in assignments}, {"RM-1046", "RM-1048"})

    def test_assigned_request_can_be_reassigned_without_changing_status(self):
        self.service.transition("RM-1047", "assigned", worker=WORKERS[0])

        request = self.service.transition(
            "RM-1047", "assigned", worker=WORKERS[1],
        )

        self.assertEqual(request["worker"], WORKERS[1])
        self.assertEqual(request["status"], "assigned")

    def test_invalid_transition_and_unregistered_worker_are_rejected(self):
        with self.assertRaises(ValueError):
            self.service.transition("RM-1048", "completed")
        self.service.transition("RM-1048", "accepted")
        with self.assertRaises(ValueError):
            self.service.transition("RM-1048", "assigned", worker="Otra persona")
        self.assertEqual(self.service.get("RM-1048")["status"], "accepted")

    def test_request_requires_contact_and_location(self):
        with self.assertRaises(ValueError):
            self.service.create(
                name="Ana Pérez", phone="", address="", neighborhood="Centro",
                quantity="1 montón", photo_path="foto.jpg",
            )

    def test_new_request_requires_a_photo(self):
        with self.assertRaisesRegex(ValueError, "foto"):
            self.service.create(
                name="Ana Pérez",
                phone="5551234567",
                address="Calle Arce 18",
                neighborhood="Centro",
                quantity="1 montón",
                photo_path="",
            )

    def test_citizen_can_edit_and_delete_their_request_in_any_status(self):
        self.service.transition("RM-1048", "accepted")
        self.service.transition("RM-1048", "assigned", worker=WORKERS[0])

        edited = self.service.update_request(
            "RM-1048",
            citizen_name="Elena Martínez",
            address="Calle Nueva 10",
            neighborhood="Centro",
            quantity="3 montones",
            photo_path="nueva.jpg",
            description="En la entrada.",
        )

        self.assertEqual(edited["status"], "assigned")
        self.assertEqual(edited["worker"], WORKERS[0])
        self.assertEqual(edited["address"], "Calle Nueva 10")
        self.assertEqual(edited["photo_path"], "nueva.jpg")

        deleted = self.service.delete_request(
            "RM-1048", citizen_name="ELENA MARTÍNEZ",
        )
        self.assertEqual(deleted["id"], "RM-1048")
        with self.assertRaisesRegex(ValueError, "No encontramos"):
            self.service.get("RM-1048")

    def test_citizen_cannot_edit_or_delete_another_citizens_request(self):
        with self.assertRaisesRegex(ValueError, "permiso"):
            self.service.update_request(
                "RM-1048",
                citizen_name="Ana Pérez",
                address="Calle Nueva 10",
                neighborhood="Centro",
                quantity="1 montón",
                photo_path="foto.jpg",
            )
        with self.assertRaisesRegex(ValueError, "permiso"):
            self.service.delete_request(
                "RM-1048", citizen_name="Ana Pérez",
            )
        self.assertEqual(self.service.get("RM-1048")["address"], "Calle Los Olmos 184")

    def test_accounts_authenticate_with_their_own_role_and_contact(self):
        citizen = self.service.authenticate("ELENA", "elena123")
        administrator = self.service.authenticate("admin", "admin123")
        worker = self.service.authenticate("lucia", "lucia123")

        self.assertEqual(citizen["name"], "Elena Martínez")
        self.assertEqual(citizen["phone"], "555 010 2048")
        self.assertEqual(citizen["role"], "citizen")
        self.assertEqual(administrator["role"], "admin")
        self.assertEqual(worker["role"], "worker")
        self.assertIsNone(self.service.authenticate("admin", "incorrecta"))

    def test_new_accounts_can_be_registered_and_recovered(self):
        account = self.service.register_account(
            username="sofia",
            password="sofia123",
            name="Sofía Ramírez",
            email="sofia@example.com",
            phone="555 010 2099",
        )

        self.assertEqual(account["role"], "citizen")
        self.assertEqual(account["email"], "sofia@example.com")
        self.assertEqual(
            self.service.authenticate("SOFIA", "sofia123")["name"],
            "Sofía Ramírez",
        )
        recovered_account = self.service.recovery_account("SOFIA")
        self.assertEqual(recovered_account["username"], "sofia")
        self.assertEqual(recovered_account["email"], "sofia@example.com")
        self.assertNotIn("password", recovered_account)
        self.assertIsNone(self.service.recovery_account("usuario-inexistente"))

    def test_registration_rejects_duplicate_usernames(self):
        with self.assertRaises(ValueError):
            self.service.register_account(
                username="elena",
                password="newpassword",
                name="Elena Another",
                email="elena2@example.com",
                phone="555 010 2000",
            )

    def test_admin_can_create_worker_and_worker_can_authenticate(self):
        worker = self.service.create_worker(
            username="  sofia ",
            name="Sofía Pérez",
            password="ramas123",
            phone="555 010 2099",
        )

        self.assertEqual(worker["username"], "sofia")
        self.assertEqual(self.service.authenticate("SOFIA", "ramas123")["name"], "Sofía Pérez")
        self.assertEqual(self.service.authenticate("SOFIA", "ramas123")["phone"], "555 010 2099")
        self.assertIn("Sofía Pérez", self.service.worker_names)

    def test_editing_worker_updates_credentials_and_existing_assignments(self):
        self.service.transition("RM-1048", "accepted")
        self.service.transition("RM-1048", "assigned", worker=WORKERS[0])

        self.service.update_worker(
            "lucia",
            username="lucia-m",
            name="Lucía Méndez Rojas",
            password="nuevo123",
            phone="555 010 2999",
        )

        self.assertIsNone(self.service.authenticate("lucia", "lucia123"))
        self.assertEqual(
            self.service.authenticate("lucia-m", "nuevo123")["name"],
            "Lucía Méndez Rojas",
        )
        self.assertEqual(
            self.service.authenticate("lucia-m", "nuevo123")["phone"],
            "555 010 2999",
        )
        self.assertEqual(self.service.get("RM-1048")["worker"], "Lucía Méndez Rojas")
        self.assertEqual(
            self.service.route_for_worker("Lucía Méndez Rojas")[0]["id"],
            "RM-1048",
        )

    def test_worker_cannot_be_deleted_with_active_requests(self):
        with self.assertRaisesRegex(ValueError, "retiros activos"):
            self.service.delete_worker("lucia")

        self.service.delete_worker("mateo")

        self.assertNotIn("Mateo Silva", self.service.worker_names)
        self.assertIsNone(self.service.authenticate("mateo", "mateo123"))

    def test_worker_creation_rejects_duplicate_usernames_and_short_passwords(self):
        for username in ("LUCIA", "admin"):
            with self.subTest(username=username):
                with self.assertRaisesRegex(ValueError, "usuario"):
                    self.service.create_worker(
                        username=username, name="Otra persona",
                        password="ramas123",
                    )
        with self.assertRaisesRegex(ValueError, "6 caracteres"):
            self.service.create_worker(
                username="sofia", name="Sofía Pérez", password="123",
            )

    def test_pending_request_requires_reason_and_can_be_resumed(self):
        self.service.transition("RM-1048", "accepted")
        self.service.transition("RM-1048", "assigned", worker=WORKERS[0])
        self.service.transition("RM-1048", "in_progress")
        with self.assertRaises(ValueError):
            self.service.transition("RM-1048", "pending", reason="  ")

        self.service.transition("RM-1048", "pending", reason="Domicilio cerrado")
        self.assertEqual(
            self.service.route_for_worker(WORKERS[0])[0]["pending_reason"],
            "Domicilio cerrado",
        )
        self.service.transition("RM-1048", "in_progress")
        self.assertEqual(self.service.get("RM-1048")["pending_reason"], "")

    def test_worker_request_card_has_explicit_finalize_button_for_in_progress(self):
        app = RamaMobileApp()
        request = {
            "id": "RM-2000",
            "name": "Ana Pérez",
            "phone": "5551234567",
            "address": "Calle Falsa 123",
            "neighborhood": "Centro",
            "quantity": "1 montón",
            "description": "Ramas pequeñas junto a la reja.",
            "date": "2026-10-08",
            "status": "in_progress",
            "worker": WORKERS[0],
            "pending_reason": "",
        }

        card = app._request_card(request, worker_actions=True)
        texts = []

        def collect(node):
            if hasattr(node, "text") and isinstance(node.text, str):
                texts.append(node.text)
            for child in getattr(node, "children", ()):
                collect(child)

        collect(card)

        self.assertIn("Finalizar", texts)

    def test_status_change_shows_a_local_notification(self):
        app = RamaMobileApp()
        app.service = RequestService()
        app.current_user = {"role": "admin"}
        app._notify = Mock()

        app._change_status("RM-1048", "accepted")

        self.assertEqual(app.service.get("RM-1048")["status"], "accepted")
        app._notify.assert_called_once_with("RM-1048: aceptada.")

    def test_android_photo_picker_uses_the_system_document_picker(self):
        android = ModuleType("android")
        android.activity = Mock()
        android.mActivity = Mock()
        intent_class = Mock()
        intent_class.ACTION_OPEN_DOCUMENT = "open-document"
        intent_class.CATEGORY_OPENABLE = "openable"
        intent_class.FLAG_GRANT_READ_URI_PERMISSION = 1
        intent = intent_class.return_value
        jnius = ModuleType("jnius")
        jnius.JavaException = type("JavaException", (Exception,), {})
        jnius.autoclass = Mock(return_value=intent_class)
        app = RamaMobileApp()

        with patch.dict("sys.modules", {"android": android, "jnius": jnius}):
            app._choose_android_request_photo()

        intent_class.assert_called_once_with("open-document")
        intent.addCategory.assert_called_once_with("openable")
        intent.setType.assert_called_once_with("image/*")
        intent.addFlags.assert_called_once_with(1)
        android.activity.bind.assert_called_once_with(
            on_activity_result=app._on_android_photo_result,
        )
        android.mActivity.startActivityForResult.assert_called_once_with(
            intent, 48127,
        )

    def test_android_photo_content_is_copied_into_private_app_storage(self):
        payload = b"selected image bytes"
        resolver = Mock()
        resolver.getType.return_value = "image/png"
        resolver.openInputStream.return_value = io.BytesIO(payload)
        android = ModuleType("android")
        android.mActivity = SimpleNamespace(
            getContentResolver=Mock(return_value=resolver),
        )

        class DestinationChannel:
            def __init__(self, path):
                self.path = Path(path)

            def transferFrom(self, source, offset, count):
                chunk = source.read(count)
                if chunk:
                    with self.path.open("ab") as destination:
                        destination.write(chunk)
                return len(chunk)

        class OutputStream:
            def __init__(self, path):
                self.channel = DestinationChannel(path)

            def getChannel(self):
                return self.channel

            def close(self):
                pass

        class Channels:
            @staticmethod
            def newChannel(stream):
                return stream

        jnius = ModuleType("jnius")
        jnius.autoclass = Mock(side_effect={
            "java.io.FileOutputStream": OutputStream,
            "java.nio.channels.Channels": Channels,
        }.get)
        app = RamaMobileApp()

        with tempfile.TemporaryDirectory() as data_dir:
            app._user_data_dir = data_dir
            with patch.dict(
                "sys.modules", {"android": android, "jnius": jnius},
            ):
                image_path = app._copy_android_photo("content://selected")
            try:
                self.assertEqual(image_path.suffix, ".png")
                self.assertEqual(image_path.read_bytes(), payload)
            finally:
                image_path.unlink(missing_ok=True)

    def test_android_camera_waits_for_permission_before_opening(self):
        android = ModuleType("android")
        android.__path__ = []
        permissions = ModuleType("android.permissions")
        permissions.Permission = SimpleNamespace(CAMERA="android.permission.CAMERA")
        permissions.request_permissions = Mock()
        android.permissions = permissions
        jnius = ModuleType("jnius")
        jnius.JavaException = type("JavaException", (Exception,), {})
        app = RamaMobileApp()
        app._show_dialog = Mock()
        app._open_request_camera = Mock()

        with (
            patch("app.main.platform", "android"),
            patch.dict(
                "sys.modules",
                {
                    "android": android,
                    "android.permissions": permissions,
                    "jnius": jnius,
                },
            ),
        ):
            app.take_request_photo()

        permissions.request_permissions.assert_called_once_with(
            ["android.permission.CAMERA"], app._on_camera_permission_result,
        )
        app._on_camera_permission_result(
            ["android.permission.CAMERA"], [False],
        )
        app._show_dialog.assert_called_once_with(
            "Permiso de cámara denegado",
            "Autoriza el uso de la cámara para tomar la foto de la solicitud.",
        )
        app._open_request_camera.assert_not_called()

        with patch("app.main.Clock.schedule_once") as schedule_once:
            app._on_camera_permission_result(
                ["android.permission.CAMERA"], [True],
            )
            callback = schedule_once.call_args.args[0]
            callback(0)
        app._open_request_camera.assert_called_once()

    def test_worker_route_is_ordered_by_neighborhood_and_address(self):
        self.service.transition("RM-1048", "accepted")
        self.service.transition("RM-1048", "assigned", worker=WORKERS[0])

        route = self.service.route_for_worker(WORKERS[0])

        self.assertEqual([item["id"] for item in route], ["RM-1048", "RM-1046"])


if __name__ == "__main__":
    unittest.main()
