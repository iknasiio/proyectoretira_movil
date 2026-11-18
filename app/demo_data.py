"""Synthetic requests used only by the presentation dashboard."""

from datetime import date, datetime, time, timedelta

from .request_service import WORKERS

_STATUSES = (
    "completed", "submitted", "completed", "accepted",
    "completed", "assigned", "completed", "in_progress",
    "completed", "completed",
) * 3 + ("completed",) * 6 + ("pending",) * 4
SIMULATED_REQUEST_COUNT = len(_STATUSES)
_NEIGHBORHOODS = ("Centro", "Las Flores", "La Estación", "El Bosque")
_QUANTITIES = ("1 montón", "2 montones", "3 montones", "Más de 3 montones")


def simulated_dashboard_requests(today: date | None = None) -> list[dict[str, str]]:
    """Return a rolling 30-day sample, separate from persisted user requests."""
    end_date = today or date.today()
    requests = []
    for index, status in enumerate(_STATUSES):
        created_day = end_date - timedelta(days=(index * 7) % 30)
        created_at = datetime.combine(created_day, time(9))
        request = {
            "id": f"SIM-{index + 1:04d}",
            "name": f"Usuario de simulación {index + 1:02d}",
            "phone": "",
            "address": f"Dirección ficticia {index + 1:02d}",
            "neighborhood": _NEIGHBORHOODS[index % len(_NEIGHBORHOODS)],
            "quantity": _QUANTITIES[index % len(_QUANTITIES)],
            "description": "Registro sintético para presentación.",
            "date": created_day.isoformat(),
            "created_at": created_at.isoformat(),
            "status": status,
            "worker": "",
            "pending_reason": "",
        }
        if status != "submitted":
            accepted_at = created_at + timedelta(hours=1)
            request["accepted_at"] = accepted_at.isoformat()
        if status in {"assigned", "in_progress", "pending", "completed"}:
            request["worker"] = WORKERS[index % len(WORKERS)]
        if status == "pending":
            request["pending_reason"] = "Caso simulado en espera de coordinación."
        if status == "completed":
            elapsed_days = min((end_date - created_day).days, 3)
            completed_at = created_at + timedelta(days=elapsed_days, hours=2)
            request["completed_at"] = completed_at.isoformat()
        requests.append(request)
    return requests
