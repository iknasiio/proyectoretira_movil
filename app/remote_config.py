"""Remote display and service-area configuration with explicit validation."""

from __future__ import annotations

from typing import Any

import requests

DEFAULT_REMOTE_CONFIG_URL = (
    "https://raw.githubusercontent.com/iknasiio/"
    "proyectoretira_movil/main/remote_config.json"
)
DEFAULT_REMOTE_CONFIG = {
    "municipality": "Temuco, Chile",
    "announcement": "Solicita el retiro municipal de ramas y restos de poda.",
}
_CONFIG_KEYS = tuple(DEFAULT_REMOTE_CONFIG)


class RemoteConfigError(ValueError):
    """Raised when a remote configuration response cannot be used."""


def fetch_remote_config(
    url: str = DEFAULT_REMOTE_CONFIG_URL, *, timeout: float = 4,
) -> dict[str, str]:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    try:
        payload: Any = response.json()
    except ValueError as error:
        raise RemoteConfigError("La respuesta no contiene JSON válido.") from error
    if not isinstance(payload, dict):
        raise RemoteConfigError("La configuración remota debe ser un objeto JSON.")

    config = DEFAULT_REMOTE_CONFIG.copy()
    for key in _CONFIG_KEYS:
        value = payload.get(key, config[key])
        if not isinstance(value, str) or not value.strip():
            raise RemoteConfigError(
                f"El valor remoto «{key}» debe ser texto no vacío."
            )
        config[key] = value.strip()
    return config
