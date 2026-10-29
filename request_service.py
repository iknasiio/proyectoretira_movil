"""Local request workflow and JSON persistence for the Rama mobile app."""

from __future__ import annotations

from copy import deepcopy
import json
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

WORKERS = ("Lucía Méndez", "Diego Rojas", "Mateo Silva")
DEMO_USERS = (
    {"username": "elena", "password": "elena123", "name": "Elena Martínez", "email": "elena@example.com", "phone": "555 010 2048", "role": "citizen"},
    {"username": "javier", "password": "javier123", "name": "Javier Torres", "email": "javier@example.com", "phone": "555 010 2047", "role": "citizen"},
    {"username": "mariana", "password": "mariana123", "name": "Mariana López", "email": "mariana@example.com", "phone": "555 010 2046", "role": "citizen"},
    {"username": "carlos", "password": "carlos123", "name": "Carlos Díaz", "email": "carlos@example.com", "phone": "555 010 2045", "role": "citizen"},
    {"username": "admin", "password": "admin123", "name": "Administración municipal", "email": "admin@example.com", "role": "admin"},
    {"username": "lucia", "password": "lucia123", "name": "Lucía Méndez", "email": "lucia@example.com", "phone": "555 010 2050", "role": "worker"},
    {"username": "diego", "password": "diego123", "name": "Diego Rojas", "email": "diego@example.com", "phone": "555 010 2051", "role": "worker"},
    {"username": "mateo", "password": "mateo123", "name": "Mateo Silva", "email": "mateo@example.com", "phone": "555 010 2052", "role": "worker"},
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
    "assigned": {"assigned", "in_progress", "pending"},
    "in_progress": {"completed", "pending"},
    "pending": {"in_progress", "completed"},
    "completed": set(),
}


class RequestService:
    """Manage requests and accounts, optionally persisting them as local JSON."""

    def __init__(self, data_path: str | Path | None = None):
        self.data_path = Path(data_path) if data_path is not None else None
        if self.data_path and self.data_path.exists():
            self._load()
            return

        self.requests = [request.copy() for request in INITIAL_REQUESTS]
        self.accounts = [
            dict(account) for account in DEMO_USERS
            if account["role"] != "worker"
        ]
        self.workers = [
            dict(account) for account in DEMO_USERS
            if account["role"] == "worker"
        ]
        self._save()

    def _load(self) -> None:
        data_path = self.data_path
        if data_path is None:
            raise RuntimeError("No se configuró la ruta de los datos locales.")
        try:
            data = json.loads(data_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(
                f"No se pudieron cargar los datos locales de {data_path}."
            ) from error
        if (
            not isinstance(data, dict)
            or data.get("version") != 1
            or not isinstance(data.get("requests"), list)
            or not isinstance(data.get("accounts"), list)
            or not isinstance(data.get("workers"), list)
            or not all(isinstance(item, dict) for item in data["requests"])
            or not all(isinstance(item, dict) for item in data["accounts"])
            or not all(isinstance(item, dict) for item in data["workers"])
        ):
            raise RuntimeError(
                f"Los datos locales de {data_path} tienen un formato no compatible."
            )
        required_request_fields = {
            "id", "name", "phone", "address", "neighborhood",
            "quantity", "date", "status", "worker",
        }
        valid_requests = all(
            required_request_fields.issubset(request)
            and all(isinstance(request[key], str) for key in required_request_fields)
            and request["status"] in STATUS_LABELS
            for request in data["requests"]
        )
        required_account_fields = {"username", "password", "name", "role"}
        valid_accounts = all(
            required_account_fields.issubset(account)
            and all(isinstance(account[key], str) for key in required_account_fields)
            and account["role"] in {"citizen", "admin"}
            for account in data["accounts"]
        )
        valid_workers = all(
            required_account_fields.issubset(worker)
            and all(isinstance(worker[key], str) for key in required_account_fields)
            and worker["role"] == "worker"
            for worker in data["workers"]
        )
        if not (valid_requests and valid_accounts and valid_workers):
            raise RuntimeError(
                f"Los datos locales de {data_path} contienen registros inválidos."
            )
        self.requests = data["requests"]
        self.workers = data["workers"]
        self.accounts = data["accounts"] + self.workers
        self._saved_state = self._snapshot()

    def _snapshot(
        self,
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[dict[str, str]]]:
        return deepcopy((self.requests, self.accounts, self.workers))

    def _restore_snapshot(
        self,
        snapshot: tuple[
            list[dict[str, Any]],
            list[dict[str, str]],
            list[dict[str, str]],
        ],
    ) -> None:
        self.requests, self.accounts, self.workers = deepcopy(snapshot)

    def _save(self) -> None:
        data_path = self.data_path
        if data_path is None:
            return
        saved_state = getattr(self, "_saved_state", None)
        temporary_path = None
        try:
            data_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "version": 1,
                "requests": self.requests,
                "accounts": [
                    account for account in self.accounts
                    if account["role"] != "worker"
                ],
                "workers": self.workers,
            }
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=data_path.parent,
                prefix=f"{data_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(data, temporary_file, ensure_ascii=False, indent=2)
                temporary_file.write("\n")
            if temporary_path is None:
                raise RuntimeError("No se creó el archivo temporal de datos.")
            os.replace(temporary_path, data_path)
        except (OSError, TypeError) as error:
            if saved_state is not None:
                self._restore_snapshot(saved_state)
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError as cleanup_error:
                    raise OSError(
                        f"{error} Además, no se pudo limpiar "
                        f"{temporary_path}: {cleanup_error}"
                    ) from cleanup_error
            raise
        self._saved_state = self._snapshot()

    @property
    def worker_names(self) -> tuple[str, ...]:
        return tuple(worker["name"] for worker in self.workers)

    def authenticate(self, username: str, password: str) -> dict[str, str] | None:
        normalized_username = username.strip().casefold()
        accounts = [
            account for account in self.accounts if account["role"] != "worker"
        ] + self.workers
        for account in accounts:
            if (account["username"] == normalized_username
                    and account["password"] == password):
                return {
                    key: account[key]
                    for key in ("username", "name", "role", "phone")
                    if key in account
                }
        return None

    def register_account(self, *, username: str, password: str,
                         name: str, email: str, phone: str) -> dict[str, str]:
        normalized_username = username.strip().casefold()
        if not normalized_username or len(password.strip()) < 6:
            raise ValueError("Escribe un usuario y una contraseña de al menos 6 caracteres.")
        if not name.strip() or "@" not in email.strip() or sum(character.isdigit() for character in phone) < 8:
            raise ValueError("Escribe nombre, correo y número de teléfono válidos.")
        if any(account["username"] == normalized_username for account in self.accounts):
            raise ValueError("Ese usuario ya está registrado.")
        account = {
            "username": normalized_username,
            "password": password,
            "name": name.strip(),
            "email": email.strip(),
            "phone": phone.strip(),
            "role": "citizen",
        }
        self.accounts.append(account)
        self._save()
        return account

    def recovery_account(self, username: str) -> dict[str, str] | None:
        normalized_username = username.strip().casefold()
        if not normalized_username:
            return None
        account = next(
            (
                item
                for item in self.accounts + self.workers
                if item["username"] == normalized_username
            ),
            None,
        )
        if account is None:
            return None
        return {
            key: account[key]
            for key in ("username", "name", "email", "role")
            if key in account
        }

    def list_workers(self) -> list[dict[str, str]]:
        return [
            {key: worker[key] for key in ("username", "name", "role", "phone")}
            for worker in self.workers
        ]

    def create_worker(self, *, username: str, name: str,
                      password: str, phone: str = "") -> dict[str, str]:
        normalized_username = username.strip().casefold()
        normalized_name = name.strip()
        normalized_phone = phone.strip()
        if len(normalized_username) < 3 or not normalized_name:
            raise ValueError("El usuario debe tener al menos 3 caracteres y el nombre no puede estar vacío.")
        if len(password) < 6:
            raise ValueError("La contraseña debe tener al menos 6 caracteres.")
        if not self._username_is_available(normalized_username):
            raise ValueError("Ya existe una cuenta con ese usuario.")
        if any(worker["name"].casefold() == normalized_name.casefold()
               for worker in self.workers):
            raise ValueError("Ya existe un trabajador con ese nombre.")
        if sum(character.isdigit() for character in normalized_phone) < 8:
            raise ValueError("El teléfono debe tener al menos 8 dígitos.")
        worker = {
            "username": normalized_username,
            "password": password,
            "name": normalized_name,
            "phone": normalized_phone,
            "role": "worker",
        }
        self.workers.append(worker)
        self.accounts.append(worker)
        self._save()
        return {key: worker[key] for key in ("username", "name", "role", "phone")}

    def update_worker(self, current_username: str, *, username: str,
                      name: str, password: str = "", phone: str = "") -> dict[str, str]:
        worker = self._get_worker(current_username)
        normalized_username = username.strip().casefold()
        normalized_name = name.strip()
        normalized_phone = phone.strip() if phone else worker.get("phone", "").strip()
        if len(normalized_username) < 3 or not normalized_name:
            raise ValueError("El usuario debe tener al menos 3 caracteres y el nombre no puede estar vacío.")
        if password and len(password) < 6:
            raise ValueError("La contraseña debe tener al menos 6 caracteres.")
        if not self._username_is_available(normalized_username, ignore_worker=worker):
            raise ValueError("Ya existe una cuenta con ese usuario.")
        for other in self.workers:
            if other is worker:
                continue
            if other["name"].casefold() == normalized_name.casefold():
                raise ValueError("Ya existe un trabajador con ese nombre.")
        if sum(character.isdigit() for character in normalized_phone) < 8:
            raise ValueError("El teléfono debe tener al menos 8 dígitos.")

        previous_name = worker["name"]
        worker["username"] = normalized_username
        worker["name"] = normalized_name
        worker["phone"] = normalized_phone
        if password:
            worker["password"] = password
        if previous_name != normalized_name:
            for request in self.requests:
                if request["worker"] == previous_name:
                    request["worker"] = normalized_name
        self._save()
        return {key: worker[key] for key in ("username", "name", "role", "phone")}

    def delete_worker(self, username: str) -> None:
        worker = self._get_worker(username)
        active_statuses = {"assigned", "in_progress", "pending"}
        if any(
            request["worker"] == worker["name"]
            and request["status"] in active_statuses
            for request in self.requests
        ):
            raise ValueError("No se puede eliminar: el trabajador tiene retiros activos asignados.")
        self.workers.remove(worker)
        self.accounts = [
            account for account in self.accounts
            if account["username"] != worker["username"]
        ]
        self._save()

    def _get_worker(self, username: str) -> dict[str, str]:
        normalized_username = username.strip().casefold()
        for worker in self.workers:
            if worker["username"] == normalized_username:
                return worker
        raise ValueError("No encontramos ese trabajador.")

    def _username_is_available(
        self, username: str, *, ignore_worker: dict[str, str] | None = None,
    ) -> bool:
        if any(
            account["username"] == username and account["role"] != "worker"
            for account in self.accounts
        ):
            return False
        return not any(
            worker is not ignore_worker and worker["username"] == username
            for worker in self.workers
        )

    def create(self, *, name: str, phone: str, address: str, neighborhood: str,
               quantity: str, photo_path: str,
               description: str = "") -> dict[str, Any]:
        values = (name.strip(), phone.strip(), address.strip(), neighborhood.strip(), quantity.strip())
        if not all(values):
            raise ValueError("Completa nombre, teléfono, dirección, colonia y cantidad.")
        if quantity not in {"1 montón", "2 montones", "3 montones", "Más de 3 montones"}:
            raise ValueError("Selecciona una cantidad válida de ramas.")
        if not photo_path.strip():
            raise ValueError("Adjunta una foto de las ramas para enviar la solicitud.")
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
            "photo_path": photo_path,
            "date": date.today().isoformat(),
            "status": "submitted",
            "worker": "",
        }
        self.requests.insert(0, request)
        self._save()
        return request

    def update_request(self, request_id: str, *, citizen_name: str,
                       address: str, neighborhood: str, quantity: str,
                       photo_path: str, description: str = "") -> dict[str, Any]:
        request = self.get(request_id)
        if request["name"].strip().casefold() != citizen_name.strip().casefold():
            raise ValueError("No tienes permiso para editar esta solicitud.")
        values = (address.strip(), neighborhood.strip(), quantity.strip())
        if not all(values):
            raise ValueError("Completa dirección, colonia y cantidad.")
        if quantity not in {"1 montón", "2 montones", "3 montones", "Más de 3 montones"}:
            raise ValueError("Selecciona una cantidad válida de ramas.")
        if not photo_path.strip():
            raise ValueError("Adjunta una foto de las ramas para guardar la solicitud.")
        request.update({
            "address": values[0],
            "neighborhood": values[1],
            "quantity": values[2],
            "description": description.strip(),
            "photo_path": photo_path,
        })
        self._save()
        return request

    def delete_request(self, request_id: str, *, citizen_name: str) -> dict[str, Any]:
        request = self.get(request_id)
        if request["name"].strip().casefold() != citizen_name.strip().casefold():
            raise ValueError("No tienes permiso para eliminar esta solicitud.")
        self.requests.remove(request)
        self._save()
        return request

    def transition(self, request_id: str, status: str, *, worker: str = "",
                   reason: str = "") -> dict[str, Any]:
        request = self.get(request_id)
        if status not in _TRANSITIONS.get(request["status"], set()):
            raise ValueError(f"No se puede pasar de {STATUS_LABELS[request['status']]} a {STATUS_LABELS.get(status, status)}.")
        if status == "assigned":
            if worker not in self.worker_names:
                raise ValueError("Selecciona un trabajador válido.")
            request["worker"] = worker
        if status == "pending":
            if len(reason.strip()) < 4:
                raise ValueError("Escribe un motivo para dejar la solicitud pendiente.")
            request["pending_reason"] = reason.strip()
        elif status in {"in_progress", "completed"}:
            request["pending_reason"] = ""
        request["status"] = status
        self._save()
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
