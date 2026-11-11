"""Client-record normalization shared by the API and the client store.

``fill_state_code`` is pure domain logic — it derives a GST state code from a
GSTIN — so it lives here rather than inside one adapter. Both the clients API
(shaping a request body) and the SQLite ``ClientRepository`` (on write and on
read) use it, which is why it is not a repository method. Lifted verbatim from
v1 ``store._fill_state_code`` (P5).
"""
from __future__ import annotations

from typing import Dict

from .validate import state_code_from_gstin


def fill_state_code(d: Dict) -> Dict:
    """A blank State code, filled from the GSTIN that already states it.

    A GSTIN's first two digits ARE the registration's state code, so leaving
    the field empty on the client form is a typo the record can correct itself
    — and an expensive one to leave standing: COMPANY.state derives from it, so
    a blank propagates into place of supply and nature of transaction, and
    EVERY invoice for that client fails import with "Place of Supply is not
    specified" / "Taxability Type could not be determined". Applied on the way
    in and on the way out, so a row already saved blank is repaired on read
    without a migration.
    """
    if not str(d.get("state_code") or "").strip():
        derived = state_code_from_gstin(str(d.get("gstin") or "").strip().upper())
        if derived:
            d = {**d, "state_code": derived}
    return d
