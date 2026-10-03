"""LifeLens HTTP API."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_session, init_db
from app.llm import llm_status
from app.service import (
    DISCLAIMER,
    apply_scenario,
    compare_view,
    create_session,
    delete_all_sessions,
    delete_session,
    discard_scenario,
    handle_message,
    list_sessions,
    run_event,
    search_knowledge,
    seed,
    set_mode,
    state,
    stress_view,
    summary_view,
    timeline_view,
    update_profile,
)

EVENTS = {
    "another_child",
    "buy_home",
    "change_jobs",
    "raise",
    "child_starts_college",
    "pay_off_debt",
    "get_married",
    "retire_earlier",
}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    db = next(get_session())
    try:
        seed(db)
    finally:
        db.close()
    yield


app = FastAPI(title="LincolnLens", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SessionCreate(BaseModel):
    mode: Literal["quick", "guided"] = "quick"


class SessionMode(BaseModel):
    mode: Literal["quick", "guided"]


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class DependentIn(BaseModel):
    label: str | None = None
    age: int | None = None
    education_goal: float | None = None
    education_is_estimate: bool | None = None


class ProfilePatch(BaseModel):
    age: int | None = None
    partner: bool | None = None
    annual_income: float | None = None
    income_replacement_years: int | None = None
    income_replacement_percent: float | None = None
    mortgage_balance: float | None = None
    mortgage_years_remaining: int | None = None
    other_debt: float | None = None
    existing_employer_coverage: float | None = None
    existing_personal_coverage: float | None = None
    savings_allocated: float | None = None
    lifelong_legacy_goal: float | None = None
    other_needs: float | None = None
    include_education: bool | None = None
    cash_value_interest: bool | None = None
    monthly_budget_preference: float | None = None
    dependents: list[DependentIn] | None = None


class EventIn(BaseModel):
    event: str


class StressIn(BaseModel):
    coverage: int = Field(ge=0, le=50_000_000)


def db_session() -> Any:
    yield from get_session()


def _missing(exc: KeyError) -> HTTPException:
    return HTTPException(status_code=404, detail="Session not found")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "lifelens", "llm": llm_status(), "disclaimer": DISCLAIMER}


@app.get("/api/sessions")
def sessions(db: Session = Depends(db_session)) -> list[dict[str, Any]]:
    return list_sessions(db)


@app.delete("/api/sessions")
def remove_all_sessions(db: Session = Depends(db_session)) -> dict[str, bool]:
    delete_all_sessions(db)
    return {"ok": True}


@app.post("/api/sessions")
def open_session(body: SessionCreate, db: Session = Depends(db_session)) -> dict[str, Any]:
    return create_session(db, body.mode)


@app.get("/api/sessions/{session_id}")
def read_session(session_id: str, db: Session = Depends(db_session)) -> dict[str, Any]:
    try:
        return state(db, session_id)
    except KeyError as exc:
        raise _missing(exc) from exc


@app.delete("/api/sessions/{session_id}")
def remove_session(session_id: str, db: Session = Depends(db_session)) -> dict[str, bool]:
    try:
        delete_session(db, session_id)
    except KeyError as exc:
        raise _missing(exc) from exc
    return {"ok": True}


@app.patch("/api/sessions/{session_id}")
def patch_session(session_id: str, body: SessionMode, db: Session = Depends(db_session)) -> dict[str, Any]:
    try:
        return set_mode(db, session_id, body.mode)
    except KeyError as exc:
        raise _missing(exc) from exc


@app.post("/api/sessions/{session_id}/messages")
def post_message(session_id: str, body: MessageIn, db: Session = Depends(db_session)) -> dict[str, Any]:
    try:
        return handle_message(db, session_id, body.content)
    except KeyError as exc:
        raise _missing(exc) from exc


@app.patch("/api/sessions/{session_id}/profile")
def patch_profile(session_id: str, body: ProfilePatch, db: Session = Depends(db_session)) -> dict[str, Any]:
    try:
        payload = body.model_dump(exclude_unset=True)
        if "dependents" in payload and payload["dependents"] is not None:
            payload["dependents"] = [item if isinstance(item, dict) else item for item in payload["dependents"]]
        return update_profile(db, session_id, payload)
    except KeyError as exc:
        raise _missing(exc) from exc


@app.post("/api/sessions/{session_id}/events")
def post_event(session_id: str, body: EventIn, db: Session = Depends(db_session)) -> dict[str, Any]:
    if body.event not in EVENTS:
        raise HTTPException(status_code=422, detail="Unknown life event")
    try:
        return run_event(db, session_id, body.event)
    except KeyError as exc:
        raise _missing(exc) from exc


@app.post("/api/sessions/{session_id}/scenarios/{scenario_id}/apply")
def post_apply(session_id: str, scenario_id: str, db: Session = Depends(db_session)) -> dict[str, Any]:
    try:
        return apply_scenario(db, session_id, scenario_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Scenario not found") from exc


@app.post("/api/sessions/{session_id}/scenarios/{scenario_id}/discard")
def post_discard(session_id: str, scenario_id: str, db: Session = Depends(db_session)) -> dict[str, Any]:
    try:
        return discard_scenario(db, session_id, scenario_id)
    except KeyError as exc:
        raise _missing(exc) from exc


@app.get("/api/sessions/{session_id}/timeline")
def read_timeline(session_id: str, year_offset: int | None = None, db: Session = Depends(db_session)) -> dict[str, Any]:
    try:
        return timeline_view(db, session_id, year_offset)
    except KeyError as exc:
        raise _missing(exc) from exc


@app.post("/api/sessions/{session_id}/stress")
def post_stress(session_id: str, body: StressIn, db: Session = Depends(db_session)) -> dict[str, Any]:
    try:
        return stress_view(db, session_id, body.coverage)
    except KeyError as exc:
        raise _missing(exc) from exc


@app.get("/api/sessions/{session_id}/compare")
def read_compare(session_id: str, db: Session = Depends(db_session)) -> dict[str, Any]:
    try:
        return compare_view(db, session_id)
    except KeyError as exc:
        raise _missing(exc) from exc


@app.get("/api/sessions/{session_id}/summary")
def read_summary(session_id: str, db: Session = Depends(db_session)) -> dict[str, Any]:
    try:
        return summary_view(db, session_id)
    except KeyError as exc:
        raise _missing(exc) from exc


@app.get("/api/knowledge")
def knowledge(q: str = "", db: Session = Depends(db_session)) -> dict[str, Any]:
    return {"query": q, "notes": search_knowledge(db, q)}
