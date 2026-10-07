import unittest

from request_service import RequestService, WORKERS


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
            description="Junto al portón verde.",
        )
        self.assertEqual(request["status"], "submitted")
        self.service.transition(request["id"], "accepted")
        self.service.transition(request["id"], "assigned", worker=WORKERS[0])
        self.service.transition(request["id"], "in_progress")
        self.service.transition(request["id"], "completed")
        self.assertEqual(self.service.get(request["id"])["status"], "completed")
        self.assertEqual(self.service.get(request["id"])["worker"], WORKERS[0])

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
                quantity="1 montón",
            )

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

    def test_admin_can_create_worker_and_worker_can_authenticate(self):
        worker = self.service.create_worker(
            username="  sofia ", name="Sofía Pérez", password="ramas123",
        )

        self.assertEqual(worker["username"], "sofia")
        self.assertEqual(self.service.authenticate("SOFIA", "ramas123")["name"], "Sofía Pérez")
        self.assertIn("Sofía Pérez", self.service.worker_names)

    def test_editing_worker_updates_credentials_and_existing_assignments(self):
        self.service.transition("RM-1048", "accepted")
        self.service.transition("RM-1048", "assigned", worker=WORKERS[0])

        self.service.update_worker(
            "lucia", username="lucia-m", name="Lucía Méndez Rojas",
            password="nuevo123",
        )

        self.assertIsNone(self.service.authenticate("lucia", "lucia123"))
        self.assertEqual(
            self.service.authenticate("lucia-m", "nuevo123")["name"],
            "Lucía Méndez Rojas",
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

    def test_worker_route_is_ordered_by_neighborhood_and_address(self):
        self.service.transition("RM-1048", "accepted")
        self.service.transition("RM-1048", "assigned", worker=WORKERS[0])

        route = self.service.route_for_worker(WORKERS[0])

        self.assertEqual([item["id"] for item in route], ["RM-1048", "RM-1046"])


if __name__ == "__main__":
    unittest.main()
