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
        self.assertEqual(
            self.service.recover_password("sofia"),
            "sofia123",
        )

    def test_registration_rejects_duplicate_usernames(self):
        with self.assertRaises(ValueError):
            self.service.register_account(
                username="elena",
                password="newpassword",
                name="Elena Another",
                email="elena2@example.com",
                phone="555 010 2000",
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
