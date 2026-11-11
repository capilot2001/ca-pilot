"""Company config + stored clients API.

Same endpoints and behaviour as v1 main.py, with the module-level ``store``
calls replaced by the injected ``ClientRepository`` (the composition root
chooses the adapter). ``/api/config`` is "the active client"; the clients
endpoints manage the list a CA office posts for.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import get_client_repo
from app.domain.clients import fill_state_code
from app.domain.config import COMPANY
from app.domain.validate import validate_gstin
from app.ports.client_repository import ClientRepository, DuplicateGSTIN

from .schemas import ClientIn, CompanyIn

router = APIRouter(prefix="/api", tags=["clients"])

Repo = Annotated[ClientRepository, Depends(get_client_repo)]


def _clean(c: CompanyIn) -> dict:
    d = c.model_dump()
    d["gstin"] = d["gstin"].strip().upper()
    d["pan"] = d["pan"].strip().upper()
    d["name"] = d["name"].strip()
    # fill_state_code is applied by the repo too; repeated here for the no-DB
    # fallback in set_config below, which writes onto COMPANY without the repo.
    return fill_state_code(d)


def _not_found():
    raise HTTPException(status_code=404, detail="Client not found.")


# ---- company configuration -------------------------------------------------
@router.get("/config")
def get_config(repo: Repo):
    """The active client. Served from the store when there is one so a restart
    resumes on the same client rather than on config.py's defaults."""
    d = repo.get_active()
    if d:
        return d
    d = COMPANY.to_dict()
    ok, reason = validate_gstin(COMPANY.gstin)
    d["gstin_valid"] = ok
    d["gstin_reason"] = reason
    return d


@router.post("/config")
def set_config(c: CompanyIn, repo: Repo):
    """Edit the active client. Writes through to its stored row — repo.update
    mutates the shared COMPANY in place, so every module that imported it by
    name sees the change."""
    active = repo.active_id()
    if active is not None:
        try:
            return repo.update(active, _clean(c))
        except DuplicateGSTIN as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    # No stored row yet (startup skipped, e.g. an import-only test harness).
    for k, v in _clean(c).items():
        setattr(COMPANY, k, v)
    ok, reason = validate_gstin(COMPANY.gstin)
    return {**COMPANY.to_dict(), "gstin_valid": ok, "gstin_reason": reason}


# ---- stored clients --------------------------------------------------------
@router.get("/clients")
def list_clients(repo: Repo, q: str = Query("", description="search name / GSTIN / PAN")):
    return {"clients": repo.search(q), "active_id": repo.active_id()}


@router.post("/clients", status_code=201)
def create_client(c: ClientIn, repo: Repo, activate: bool = True):
    try:
        return repo.create(_clean(c), activate_it=activate)
    except DuplicateGSTIN as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/clients/{client_id}")
def update_client(client_id: int, c: ClientIn, repo: Repo):
    try:
        d = repo.update(client_id, _clean(c))
    except DuplicateGSTIN as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return d or _not_found()


@router.post("/clients/{client_id}/activate")
def activate_client(client_id: int, repo: Repo):
    """Point the whole app at this client — every later extraction, export and
    reconciliation classifies against its GSTIN."""
    return repo.activate(client_id) or _not_found()


@router.delete("/clients/{client_id}")
def delete_client(client_id: int, repo: Repo):
    if not repo.delete(client_id):
        raise HTTPException(
            status_code=409,
            detail="Client not found, or it is the only one left — the app needs "
                   "one client GSTIN to classify purchases against.")
    return {"deleted": client_id, "active_id": repo.active_id()}
