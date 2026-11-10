"""Port: the stored list of CA-office clients and which one is active.

A CA office posts for many clients, so the "Company" of ``domain.config`` is
really *one of* a stored list. This port is the contract for owning that list;
``adapters.persistence.sqlite_client_repo.SqliteClientRepo`` is the Phase-0
implementation (SQLite — ADR-0007). The engine can change later (Postgres, a
remote service) behind this same interface without touching callers (P3).

Methods and return shapes mirror v1 ``store.py`` exactly — the logic is migrated
unchanged (P5); only the module-of-functions becomes a port + adapter.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Protocol


class DuplicateGSTIN(ValueError):
    """Raised when a save would put the same GSTIN on two clients.

    Part of the contract: callers (the clients API) catch this to return a 409,
    so it lives on the port, not inside one adapter.
    """


class ClientRepository(Protocol):
    """Persistent client list + active-client pointer.

    ``init`` is called once at startup to create/seed the store and load the
    active client onto ``domain.config.COMPANY``. The mutating methods keep that
    process-wide ``COMPANY`` in step in place, exactly as v1 did — the one piece
    of global state the migration carries unchanged.
    """

    def init(self) -> None:
        """Create the schema, seed the built-in client, load the active one."""
        ...

    def active_id(self) -> Optional[int]:
        """Id of the active client, or None if the store is empty."""
        ...

    def get_active(self) -> Optional[Dict]:
        """The active client (falls back to the oldest row if the pointer is stale)."""
        ...

    def get(self, client_id: int) -> Optional[Dict]:
        """One client by id, or None."""
        ...

    def search(self, q: str = "", limit: int = 200) -> List[Dict]:
        """Clients matching a free-text query on name / GSTIN / PAN."""
        ...

    def create(self, data: Dict, activate_it: bool = True) -> Dict:
        """Add a client; raises ``DuplicateGSTIN`` on a clashing GSTIN."""
        ...

    def update(self, client_id: int, data: Dict) -> Optional[Dict]:
        """Edit a client; raises ``DuplicateGSTIN`` on a clashing GSTIN. None if absent."""
        ...

    def activate(self, client_id: int) -> Optional[Dict]:
        """Point the app at this client. None if absent."""
        ...

    def delete(self, client_id: int) -> bool:
        """Remove a client. False if absent or it is the only one left."""
        ...
