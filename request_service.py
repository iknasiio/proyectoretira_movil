"""Local request workflow and JSON persistence for the Rama mobile app."""

from __future__ import annotations

from datetime import date
from typing import Any

WORKERS = ("Lucía Méndez", "Diego Rojas", "Mateo Silva")
DEMO_USERS = (
    {"username": "elena", "password": "elena123", "name": "Elena Martínez", "phone": "555 010 2048", "role": "citizen"},
    {"username": "javier", "password": "javier123", "name": "Javier Torres", "phone": "555 010 2047", "role": "citizen"},
    {"username": "mariana", "password": "mariana123", "name": "Mariana López", "phone": "555 010 2046", "role": "citizen"},
    {"username": "carlos", "password": "carlos123", "name": "Carlos Díaz", "phone": "555 010 2045", "role": "citizen"},
    {"username": "admin", "password": "admin123", "name": "Administración municipal", "role": "admin"},
    {"username": "lucia", "password": "lucia123", "name": "Lucía Méndez", "role": "worker"},
    {"username": "diego", "password": "diego123", "name": "Diego Rojas", "role": "worker"},
    {"username": "mateo", "password": "mateo123", "name": "Mateo Silva", "role": "worker"},
)
STATUS_LABELS = {
    "submitted": "Por revisar",
    "accepted": "Aceptada",
    "assigned": "Asignada",
    "in_progress": "En recolección",
    "pending": "Pendiente",
    "completed": "Completada",
}

INITIAL_REQUESTS = [
    {
        "id": "RM-1048",
        "name": "Elena Martínez",
        "phone": "555 010 2048",
        "address": "Calle Los Olmos 184",
        "neighborhood": "Las Flores",
        "quantity": "2 montones",
        "description": "Ramas de jacarandá, junto a la banqueta.",
        "date": "2026-09-30",
        "status": "submitted",
        "worker": "",
        "pending_reason": "",
    },
    {
        "id": "RM-1047",
        "name": "Javier Torres",
        "phone": "555 010 2047",
        "address": "Avenida del Parque 52",
        "neighborhood": "Centro",
        "quantity": "1 montón",
        "description": "Poda de árbol pequeño, lista para retirar.",
        "date": "2026-09-29",
        "status": "accepted",
        "worker": "",
        "pending_reason": "",
    },
    {
        "id": "RM-1046",
        "name": "Mariana López",
        "phone": "555 010 2046",
        "address": "Calle Naranjo 311",
        "neighborhood": "Las Flores",
        "quantity": "3 montones",
        "description": "Restos de poda al lado de la entrada.",
        "date": "2026-09-28",
        "status": "in_progress",
        "worker": "Lucía Méndez",
        "pending_reason": "",
    },
    {
        "id": "RM-1045",
        "name": "Carlos Díaz",
        "phone": "555 010 2045",
        "address": "Pasaje del Sol 7",
        "neighborhood": "La Estación",
        "quantity": "1 montón",
        "description": "Ramas pequeñas de arbusto.",
        "date": "2026-09-26",
        "status": "completed",
        "worker": "Diego Rojas",
        "pending_reason": "",
    },
]

_TRANSITIONS = {
    "submitted": {"accepted"},
    "accepted": {"assigned"},
    "assigned": {"in_progress", "pending"},
    "in_progress": {"completed", "pending"},
    "pending": {"in_progress", "completed"},
    "completed": set(),
}


class RequestService:
    """Manage the in-memory requests used during the application demo."""

    def __init__(self):
        self.requests = [request.copy() for request in INITIAL_REQUESTS]

    def authenticate(self, username: str, password: str) -> dict[str, str] | None:
        normalized_username = username.strip().casefold()
        for account in DEMO_USERS:
            if (account["username"] == normalized_username
                    and account["password"] == password):
                return {
                    key: account[key]
                    for key in ("username", "name", "role", "phone")
                    if key in account
                }
        return None

    def create(self, *, name: str, phone: str, address: str, neighborhood: str,
               quantity: str, description: str = "") -> dict[str, Any]:
        values = (name.strip(), phone.strip(), address.strip(), neighborhood.strip(), quantity.strip())
        if not all(values):
            raise ValueError("Completa nombre, teléfono, dirección, colonia y cantidad.")
        if quantity not in {"1 montón", "2 montones", "3 montones", "Más de 3 montones"}:
            raise ValueError("Selecciona una cantidad válida de ramas.")
        last_number = max(
            (int(item["id"].removeprefix("RM-")) for item in self.requests
             if str(item.get("id", "")).startswith("RM-")
             and str(item["id"])[3:].isdigit()),
            default=1047,
        )
        request = {
            "id": f"RM-{last_number + 1}",
            "name": values[0],
            "phone": values[1],
            "address": values[2],
            "neighborhood": values[3],
            "quantity": values[4],
            "description": description.strip(),
            "date": date.today().isoformat(),
            "status": "submitted",
            "worker": "",
        }
        self.requests.insert(0, request)
        return request

    def transition(self, request_id: str, status: str, *, worker: str = "",
                   reason: str = "") -> dict[str, Any]:
        request = self.get(request_id)
        if status not in _TRANSITIONS.get(request["status"], set()):
            raise ValueError(f"No se puede pasar de {STATUS_LABELS[request['status']]} a {STATUS_LABELS.get(status, status)}.")
        if status == "assigned":
            if worker not in WORKERS:
                raise ValueError("Selecciona un trabajador válido.")
            request["worker"] = worker
        if status == "pending":
            if len(reason.strip()) < 4:
                raise ValueError("Escribe un motivo para dejar la solicitud pendiente.")
            request["pending_reason"] = reason.strip()
        elif status in {"in_progress", "completed"}:
            request["pending_reason"] = ""
        request["status"] = status
        return request

    def get(self, request_id: str) -> dict[str, Any]:
        for request in self.requests:
            if request["id"] == request_id:
                return request
        raise ValueError("No encontramos esa solicitud.")

    def for_citizen(self, name: str) -> list[dict[str, Any]]:
        return [item for item in self.requests if item["name"].casefold() == name.strip().casefold()]

    def for_worker(self, worker: str) -> list[dict[str, Any]]:
        return [
            item for item in self.requests
            if item["worker"] == worker
            and item["status"] in {"assigned", "in_progress", "pending"}
        ]

    def route_for_worker(self, worker: str) -> list[dict[str, Any]]:
        return sorted(
            self.for_worker(worker),
            key=lambda item: (
                item["neighborhood"].casefold(),
                item["address"].casefold(),
                item["id"],
            ),
        )
