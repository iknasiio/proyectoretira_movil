import unittest
from unittest.mock import Mock, patch

import requests

from remote_config import (
    DEFAULT_REMOTE_CONFIG,
    RemoteConfigError,
    fetch_remote_config,
)


class RemoteConfigTests(unittest.TestCase):
    @patch("remote_config.requests.get")
    def test_loads_remote_values_and_uses_defaults_for_optional_fields(self, get):
        response = Mock()
        response.json.return_value = {"municipality": "Valdivia, Chile"}
        get.return_value = response

        config = fetch_remote_config("https://example.test/config.json")

        self.assertEqual(config["municipality"], "Valdivia, Chile")
        self.assertEqual(
            config["announcement"], DEFAULT_REMOTE_CONFIG["announcement"],
        )
        get.assert_called_once_with(
            "https://example.test/config.json", timeout=4,
        )

    @patch("remote_config.requests.get")
    def test_rejects_empty_or_invalid_remote_values(self, get):
        response = Mock()
        response.json.return_value = {"municipality": ""}
        get.return_value = response

        with self.assertRaisesRegex(RemoteConfigError, "municipality"):
            fetch_remote_config()

    @patch("remote_config.requests.get")
    def test_rejects_non_object_json(self, get):
        response = Mock()
        response.json.return_value = ["not", "an", "object"]
        get.return_value = response

        with self.assertRaisesRegex(RemoteConfigError, "objeto JSON"):
            fetch_remote_config()

    @patch("remote_config.requests.get")
    def test_propagates_network_errors_for_the_app_to_handle(self, get):
        get.side_effect = requests.Timeout("timeout")

        with self.assertRaises(requests.Timeout):
            fetch_remote_config()

    @patch("remote_config.requests.get")
    def test_reports_invalid_json(self, get):
        response = Mock()
        response.json.side_effect = ValueError("invalid JSON")
        get.return_value = response

        with self.assertRaisesRegex(RemoteConfigError, "JSON válido"):
            fetch_remote_config()


if __name__ == "__main__":
    unittest.main()
