"""Request bodies for the server API (unchanged from v1 main.py)."""
from __future__ import annotations

from typing import List

from pydantic import BaseModel

from shared.models import Invoice


class CompanyIn(BaseModel):
    name: str
    gstin: str
    state_code: str
    pan: str = ""
    registration_type: str = "Regular"
    address: str = ""
    pincode: str = ""
    stock_enabled: bool = True


# A CA office posts for many clients; the client store keeps the list and
# remembers which one is selected, so /api/config is really "the active client".
class ClientIn(CompanyIn):
    pass


class InvoiceBatch(BaseModel):
    invoices: List[Invoice]
