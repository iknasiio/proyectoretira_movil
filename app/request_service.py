"""Local request workflow and JSON persistence for the Rama mobile app."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import hmac
import json
import os
import secrets
import tempfile
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

WORKERS = ("Lucía Méndez", "Diego Rojas", "Mateo Silva")
DEMO_USERS = (
    {"username": "elena", "password": "elena123", "name": "Elena Martínez", "email": "elena@example.com", "phone": "555010204", "role": "citizen"},
    {"username": "javier", "password": "javier123", "name": "Javier Torres", "email": "javier@example.com", "phone": "555010204", "role": "citizen"},
    {"username": "mariana", "password": "mariana123", "name": "Mariana López", "email": "mariana@example.com", "phone": "555010204", "role": "citizen"},
    {"username": "carlos", "password": "carlos123", "name": "Carlos Díaz", "email": "carlos@example.com", "phone": "555010204", "role": "citizen"},
    {"username": "admin", "password": "admin123", "name": "Administración municipal", "email": "admin@example.com", "role": "admin"},
    {"username": "lucia", "password": "lucia123", "name": "Lucía Méndez", "email": "lucia@example.com", "phone": "555010205", "role": "worker"},
    {"username": "diego", "password": "diego123", "name": "Diego Rojas", "email": "diego@example.com", "phone": "555010205", "role": "worker"},
    {"username": "mateo", "password": "mateo123", "name": "Mateo Silva", "email": "mateo@example.com", "phone": "555010205", "role": "worker"},
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
        "phone": "555010204",
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
        "phone": "555010204",
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
        "phone": "555010204",
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
        "phone": "555010204",
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


RESET_CODE_TTL_SECONDS = 10 * 60
RESET_MAX_ATTEMPTS = 5
DATA_FILE_NAMES = {
    "requests": "solicitudes.json",
    "accounts": "cuentas.json",
    "workers": "trabajadores.json",
}


class RequestService:
    """Manage requests and accounts, optionally persisting them as local JSON."""

    def __init__(
        self,
        data_path: str | Path | None = None,
        *,
        data_dir: str | Path | None = None,
        legacy_data_path: str | Path | None = None,
    ):
        if data_path is not None and data_dir is not None:
            raise ValueError("Usa data_path o data_dir, no ambos.")
        if data_path is not None:
            legacy_path = Path(data_path)
            self.data_dir = legacy_path.parent
            self.legacy_data_path = (
                Path(legacy_data_path)
                if legacy_data_path is not None else legacy_path
            )
        elif data_dir is not None:
            self.data_dir = Path(data_dir)
            self.legacy_data_path = (
                Path(legacy_data_path)
                if legacy_data_path is not None
                else self.data_dir / "rama_data.json"
            )
        else:
            self.data_dir = None
            self.legacy_data_path = None
        # Códigos de recuperación pendientes: solo en memoria, nunca en disco.
        self._reset_codes: dict[str, dict[str, Any]] = {}
        self._load()

    @property
    def data_files(self) -> dict[str, Path]:
        if self.data_dir is None:
            return {}
        return {
            key: self.data_dir / filename
            for key, filename in DATA_FILE_NAMES.items()
        }

    def _load(self) -> None:
        data_files = self.data_files
        if not data_files:
            self._initialize_demo_data()
            return

        present_files = {
            key: path for key, path in data_files.items() if path.exists()
        }
        migrated = False
        if present_files and len(present_files) != len(data_files):
            missing = sorted(
                path.name for key, path in data_files.items()
                if key not in present_files
            )
            raise RuntimeError(
                "La persistencia local está incompleta. Faltan los archivos: "
                f"{', '.join(missing)}."
            )
        if len(present_files) == len(data_files):
            data = {"version": 1}
            data.update({
                key: self._read_split_file(path, key)
                for key, path in data_files.items()
            })
        elif self.legacy_data_path and self.legacy_data_path.exists():
            data = self._read_legacy_file(self.legacy_data_path)
            migrated = True
        else:
            self._initialize_demo_data()
            return

        self._validate_data(data, self.data_dir)
        self.requests = data["requests"]
        self.workers = data["workers"]
        self.accounts = data["accounts"] + self.workers
        self._saved_state = self._snapshot()
        if migrated:
            self._save()
            self.legacy_data_path.unlink()

    @staticmethod
    def _read_split_file(path: Path, key: str) -> list[dict[str, Any]]:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(
                f"No se pudieron cargar los datos locales de {path}."
            ) from error
        if (
            not isinstance(document, dict)
            or document.get("version") != 1
            or not isinstance(document.get(key), list)
            or not all(isinstance(item, dict) for item in document[key])
        ):
            raise RuntimeError(
                f"Los datos locales de {path} tienen un formato no compatible."
            )
        return document[key]

    @staticmethod
    def _read_legacy_file(path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(
                f"No se pudieron cargar los datos locales de {path}."
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
                f"Los datos locales de {path} tienen un formato no compatible."
            )
        return data

    @staticmethod
    def _validate_data(data: dict[str, Any], location: Path) -> None:
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
                f"Los datos locales de {location} tienen un formato no compatible."
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
                f"Los datos locales de {location} contienen registros inválidos."
            )

    def _initialize_demo_data(self) -> None:
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
        data_files = self.data_files
        if not data_files:
            return
        saved_state = getattr(self, "_saved_state", None)
        temporary_paths: dict[Path, Path] = {}
        original_files: dict[Path, bytes | None] = {}
        replaced_files: list[Path] = []
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            data = {
                "requests": self.requests,
                "accounts": [
                    account for account in self.accounts
                    if account["role"] != "worker"
                ],
                "workers": self.workers,
            }
            for key, data_path in data_files.items():
                original_files[data_path] = (
                    data_path.read_bytes() if data_path.exists() else None
                )
                with tempfile.NamedTemporaryFile(
                    "w",
                    encoding="utf-8",
                    dir=self.data_dir,
                    prefix=f"{data_path.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as temporary_file:
                    temporary_path = Path(temporary_file.name)
                    temporary_paths[data_path] = temporary_path
                    json.dump(
                        {"version": 1, key: data[key]},
                        temporary_file,
                        ensure_ascii=False,
                        indent=2,
                    )
                    temporary_file.write("\n")
            for data_path in data_files.values():
                os.replace(temporary_paths[data_path], data_path)
                replaced_files.append(data_path)
        except (OSError, TypeError) as error:
            if saved_state is not None:
                self._restore_snapshot(saved_state)
            rollback_errors = []
            for data_path in reversed(replaced_files):
                try:
                    original = original_files[data_path]
                    if original is None:
                        data_path.unlink(missing_ok=True)
                    else:
                        self._restore_file(data_path, original)
                except OSError as rollback_error:
                    rollback_errors.append(
                        f"{data_path.name}: {rollback_error}"
                    )
            cleanup_errors = self._cleanup_temporary_files(temporary_paths)
            if rollback_errors or cleanup_errors:
                details = rollback_errors + cleanup_errors
                raise OSError(
                    f"{error} No se pudo completar la restauración: "
                    f"{'; '.join(details)}"
                ) from error
            raise
        cleanup_errors = self._cleanup_temporary_files(temporary_paths)
        if cleanup_errors:
            raise OSError(
                "No se pudieron limpiar archivos temporales: "
                + "; ".join(cleanup_errors)
            )
        self._saved_state = self._snapshot()

    @staticmethod
    def _restore_file(path: Path, content: bytes) -> None:
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                "wb",
                dir=path.parent,
                prefix=f"{path.name}.rollback.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_file.write(content)
            os.replace(temporary_path, path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _cleanup_temporary_files(
        temporary_paths: dict[Path, Path],
    ) -> list[str]:
        errors = []
        for temporary_path in temporary_paths.values():
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError as error:
                errors.append(f"{temporary_path.name}: {error}")
        return errors

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
        normalized_phone = phone.strip()
        if (not name.strip() or "@" not in email.strip()
                or len(normalized_phone) != 9 or not normalized_phone.isdigit()):
            raise ValueError("Escribe nombre, correo y número de teléfono válidos.")
        if any(account["username"] == normalized_username for account in self.accounts):
            raise ValueError("Ese usuario ya está registrado.")
        account = {
            "username": normalized_username,
            "password": password,
            "name": name.strip(),
            "email": email.strip(),
            "phone": normalized_phone,
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

    @staticmethod
    def _reset_digest(code: str, salt: str) -> str:
        return hashlib.sha256(f"{salt}:{code}".encode("utf-8")).hexdigest()

    def create_password_reset(self, username: str) -> dict[str, str] | None:
        """Genera un código de 6 dígitos para la cuenta y lo deja pendiente.

        Devuelve usuario, nombre, correo y el código en claro (para enviarlo
        por correo), o None si el usuario no existe o no tiene correo.
        """
        normalized_username = username.strip().casefold()
        account = next(
            (
                item for item in self.accounts + self.workers
                if item["username"] == normalized_username
            ),
            None,
        )
        if account is None or "@" not in account.get("email", ""):
            return None
        code = f"{secrets.randbelow(1_000_000):06d}"
        salt = secrets.token_hex(8)
        self._reset_codes[normalized_username] = {
            "salt": salt,
            "digest": self._reset_digest(code, salt),
            "expires_at": time.monotonic() + RESET_CODE_TTL_SECONDS,
            "attempts": 0,
        }
        return {
            "username": normalized_username,
            "name": account["name"],
            "email": account["email"].strip(),
            "code": code,
        }

    def cancel_password_reset(self, username: str) -> None:
        self._reset_codes.pop(username.strip().casefold(), None)

    def reset_password(self, username: str, code: str, new_password: str) -> None:
        """Cambia la contraseña si el código es válido, vigente y no usado."""
        normalized_username = username.strip().casefold()
        pending = self._reset_codes.get(normalized_username)
        if pending is None:
            raise ValueError("Solicita un código nuevo para cambiar la contraseña.")
        if time.monotonic() > pending["expires_at"]:
            del self._reset_codes[normalized_username]
            raise ValueError("El código venció. Solicita uno nuevo.")
        if len(new_password) < 6:
            raise ValueError("La nueva contraseña debe tener al menos 6 caracteres.")
        candidate = self._reset_digest(code.strip(), pending["salt"])
        if not hmac.compare_digest(candidate, pending["digest"]):
            pending["attempts"] += 1
            if pending["attempts"] >= RESET_MAX_ATTEMPTS:
                del self._reset_codes[normalized_username]
                raise ValueError(
                    "Demasiados intentos fallidos. Solicita un código nuevo."
                )
            remaining = RESET_MAX_ATTEMPTS - pending["attempts"]
            raise ValueError(f"Código incorrecto. Te quedan {remaining} intentos.")
        for account in self.accounts + self.workers:
            if account["username"] == normalized_username:
                account["password"] = new_password
        del self._reset_codes[normalized_username]
        self._save()

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
        if len(normalized_phone) != 9 or not normalized_phone.isdigit():
            raise ValueError("El teléfono debe tener exactamente 9 dígitos.")
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
        if len(normalized_phone) != 9 or not normalized_phone.isdigit():
            raise ValueError("El teléfono debe tener exactamente 9 dígitos.")

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
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
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
        if status == "accepted":
            request["accepted_at"] = datetime.now().astimezone().isoformat(
                timespec="seconds",
            )
        elif status == "completed":
            request["completed_at"] = datetime.now().astimezone().isoformat(
                timespec="seconds",
            )
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
