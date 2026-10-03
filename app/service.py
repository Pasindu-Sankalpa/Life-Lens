"""Session orchestration. Conversation in, engine out, sources attached."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.coverage import (
    DEFAULT_COLLEGE_COST,
    DependentIn,
    Inputs,
    apply_patch,
    calculate,
    fmt,
    life_event_patch,
)
from app.engine.parse import extract_message, number_is_grounded
from app.knowledge import CHUNKS, KNOWLEDGE_VERSION, Embedder
from app.llm import explain_with_notes, interpret
from app.models import (
    CalculationRow,
    DependentRow,
    KnowledgeRow,
    MessageRow,
    MetaRow,
    ProfileRow,
    ScenarioRow,
    SessionRow,
    utcnow,
)
from app.questions import questions_for
from app.tools import (
    compare_coverage_types,
    get_coverage_timeline,
    retrieve_lincoln_guidance,
    stress_coverage,
)

EMBEDDER = Embedder()

PROFILE_FIELDS = (
    "age",
    "partner",
    "annual_income",
    "income_replacement_years",
    "income_replacement_percent",
    "mortgage_balance",
    "mortgage_years_remaining",
    "other_debt",
    "existing_employer_coverage",
    "existing_personal_coverage",
    "savings_allocated",
    "lifelong_legacy_goal",
    "other_needs",
    "include_education",
    "cash_value_interest",
    "dependents_confirmed",
    "monthly_budget_preference",
)

MONEY_FIELDS = {
    "annual_income",
    "mortgage_balance",
    "other_debt",
    "existing_employer_coverage",
    "existing_personal_coverage",
    "savings_allocated",
    "lifelong_legacy_goal",
    "other_needs",
    "monthly_budget_preference",
}

EVENT_WORDS = {
    "another_child": ("another child", "have a baby", "new baby"),
    "buy_home": ("buy a home", "buy a house"),
    "change_jobs": ("change jobs", "new job", "lose my job", "leave my job"),
    "raise": ("raise", "salary increase"),
    "child_starts_college": ("starts college", "start college", "goes to college"),
    "pay_off_debt": ("pay off", "debt-free", "debt free"),
    "get_married": ("get married", "getting married"),
    "retire_earlier": ("retire earlier", "retire sooner", "early retirement"),
}


def new_id() -> str:
    return uuid.uuid4().hex


def seed(db: Session) -> None:
    current = db.get(MetaRow, "knowledge_version")
    if current and current.value == KNOWLEDGE_VERSION and db.scalar(select(KnowledgeRow.id).limit(1)):
        return
    db.query(KnowledgeRow).delete()
    for chunk in CHUNKS:
        db.add(
            KnowledgeRow(
                id=new_id(),
                slug=chunk["slug"],
                topic=chunk["topic"],
                title=chunk["title"],
                content=chunk["content"],
                source_name=chunk["source_name"],
                source_url=chunk["source_url"],
                embedding=None,
            )
        )
    if current is None:
        db.add(MetaRow(key="knowledge_version", value=KNOWLEDGE_VERSION))
    else:
        current.value = KNOWLEDGE_VERSION
    db.commit()


def create_session(db: Session, mode: str) -> dict[str, Any]:
    mode = mode if mode in {"quick", "guided"} else "quick"
    session = SessionRow(id=new_id(), mode=mode, title="New plan")
    profile = ProfileRow(id=new_id(), session_id=session.id, field_sources={}, dependents_confirmed=False)
    session.profile = profile
    db.add(session)
    db.flush()
    opening, questions = _opening(profile, mode)
    _add_message(db, session, "assistant", opening, {"questions": questions, "tools": []})
    if questions:
        session.last_question_key = questions[0]["key"]
    db.commit()
    return state(db, session.id)


def list_sessions(db: Session) -> list[dict[str, Any]]:
    rows = db.scalars(select(SessionRow).order_by(SessionRow.updated_at.desc())).all()
    payload = []
    for row in rows:
        latest = db.scalars(
            select(CalculationRow)
            .where(CalculationRow.session_id == row.id, CalculationRow.kind == "base")
            .order_by(CalculationRow.created_at.desc())
        ).first()
        gap = latest.result.get("gap") if latest and latest.result else None
        payload.append(
            {
                "id": row.id,
                "title": row.title,
                "mode": row.mode,
                "updated_at": row.updated_at.isoformat(),
                "gap": gap,
            }
        )
    return payload


def state(db: Session, session_id: str) -> dict[str, Any]:
    session = _session(db, session_id)
    profile = session.profile
    assert profile is not None
    base_inputs = to_inputs(profile)
    base_calc = calculate(base_inputs)
    active = None
    calculation = base_calc
    if session.active_scenario_id:
        scenario = db.get(ScenarioRow, session.active_scenario_id)
        if scenario is not None:
            calculation = scenario.result
            active = _scenario_brief(scenario)
    return {
        "session": {
            "id": session.id,
            "mode": session.mode,
            "title": session.title,
            "status": session.status,
            "last_question_key": session.last_question_key,
        },
        "profile": serialize_profile(profile),
        "messages": [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "payload": message.payload or {},
                "created_at": message.created_at.isoformat(),
            }
            for message in sorted(session.messages, key=lambda item: _ts(item.created_at))
        ],
        "calculation": calculation,
        "base_calculation": base_calc,
        "active_scenario": active,
        "scenarios": [
            _scenario_brief(item)
            for item in sorted(session.scenarios, key=lambda item: _ts(item.created_at), reverse=True)[:8]
        ],
        "questions": questions_for(_question_keys(base_inputs, session.mode)),
    }


def delete_session(db: Session, session_id: str) -> None:
    session = _session(db, session_id)
    db.delete(session)
    db.commit()


def set_mode(db: Session, session_id: str, mode: str) -> dict[str, Any]:
    session = _session(db, session_id)
    session.mode = mode if mode in {"quick", "guided"} else session.mode
    session.updated_at = utcnow()
    db.commit()
    return state(db, session_id)


def handle_message(db: Session, session_id: str, content: str) -> dict[str, Any]:
    session = _session(db, session_id)
    profile = session.profile
    assert profile is not None
    text = content.strip()
    if session.title == "New plan":
        session.title = text[:72] + ("…" if len(text) > 72 else "")
    _add_message(db, session, "user", text, {})

    extracted = extract_message(text, session.last_question_key)
    tool_trace: list[dict[str, Any]] = []
    preface = ""
    retrieval_query = text if extracted["is_education_question"] else ""
    llm = interpret(text, serialize_profile(profile), [item["key"] for item in calculate(to_inputs(profile))["missing"]])
    if llm:
        if llm.get("error"):
            tool_trace.append({"name": "llm", "status": "unavailable", "detail": llm["error"]})
        preface = _safe_preface(llm.get("preface") or "")
        _apply_llm_tools(text, extracted, llm.get("tool_calls") or [], tool_trace)
        for call in llm.get("tool_calls") or []:
            if call["name"] == "retrieve_lincoln_guidance":
                retrieval_query = call["arguments"].get("query") or retrieval_query or text
    else:
        tool_trace.append({"name": "llm", "status": "offline", "detail": "Private model is not reachable. The extractor is handling this turn."})

    if extracted["life_event"] and not (extracted["scenario_patch"] and extracted["scenario_patch"].get("profile")):
        return _preview_event(db, session, extracted["life_event"], preface, tool_trace)

    _apply_extraction(profile, extracted)
    _touch(session)
    base_inputs = to_inputs(profile)
    base_calc = calculate(base_inputs)
    _store_calculation(db, session, base_calc, "base", "Current plan")
    tool_trace.append({"name": "calculate_coverage_need", "status": "ok", "source": "engine"})
    tool_trace.append({"name": "get_coverage_timeline", "status": "ok", "source": "engine"})
    tool_trace.append({"name": "compare_coverage_types", "status": "ok", "source": "engine"})

    notes = _notes(db, retrieval_query) if retrieval_query else []
    if notes:
        tool_trace.append({"name": "retrieve_lincoln_guidance", "status": "ok", "source": "knowledge"})

    if extracted["scenario_patch"]:
        simulated = apply_patch(base_inputs, extracted["scenario_patch"])
        scenario_calc = calculate(simulated)
        label = _scenario_label(extracted["scenario_patch"], text)
        scenario = _store_scenario(db, session, label, extracted["scenario_patch"].get("note", ""), extracted["scenario_patch"], scenario_calc, base_calc["gap"])
        tool_trace.append({"name": "simulate_scenario", "status": "ok", "source": "engine"})
        reply = _compose(
            extracted=extracted,
            base_calc=base_calc,
            scenario_calc=scenario_calc,
            scenario_label=label,
            scenario_note=extracted["scenario_patch"].get("note", ""),
            questions=[],
            preface=preface,
            notes=notes,
            note_prose=_note_prose(text, notes),
        )
        _add_message(db, session, "assistant", reply, {"tools": tool_trace, "questions": [], "scenario_id": scenario.id, "notes": _public_notes(notes)})
        session.last_question_key = None
        session.active_scenario_id = scenario.id
        db.commit()
        return state(db, session.id)

    questions = questions_for(_question_keys(base_inputs, session.mode))
    if extracted.get("education_choice") == "unknown":
        questions = questions_for(["include_education"])
    reply = _compose(
        extracted=extracted,
        base_calc=base_calc,
        scenario_calc=None,
        scenario_label="",
        scenario_note="",
        questions=questions,
        preface=preface,
        notes=notes,
        note_prose=_note_prose(text, notes) if extracted["is_education_question"] else "",
    )
    _add_message(
        db,
        session,
        "assistant",
        reply,
        {"tools": tool_trace, "questions": questions, "notes": _public_notes(notes)},
    )
    session.last_question_key = questions[0]["key"] if questions else None
    session.active_scenario_id = None
    db.commit()
    return state(db, session.id)


def update_profile(db: Session, session_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    session = _session(db, session_id)
    profile = session.profile
    assert profile is not None
    dependents = patch.pop("dependents", None)
    sources = dict(profile.field_sources or {})
    for key, value in patch.items():
        if key not in PROFILE_FIELDS:
            continue
        cleaned = _clean_field(key, value)
        setattr(profile, key, cleaned)
        sources[key] = "user" if cleaned is not None else "skipped"
    profile.field_sources = sources
    if dependents is not None:
        _replace_dependents(db, profile, dependents, keep_education=False)
        profile.dependents_confirmed = True
        sources = dict(profile.field_sources or {})
        sources["dependents"] = "user"
        profile.field_sources = sources
    _apply_education_defaults(profile)
    _touch(session)
    calc = calculate(to_inputs(profile))
    _store_calculation(db, session, calc, "base", "Current plan")
    session.active_scenario_id = None
    _add_message(
        db,
        session,
        "assistant",
        f"Updated. The estimated protection gap is {fmt(calc['gap'])}." if calc["ready"] else "Updated. Add a need and the map will fill in.",
        {"tools": [{"name": "update_customer_profile", "status": "ok"}, {"name": "calculate_coverage_need", "status": "ok", "source": "engine"}]},
    )
    db.commit()
    return state(db, session.id)


def run_event(db: Session, session_id: str, event: str) -> dict[str, Any]:
    session = _session(db, session_id)
    return _preview_event(db, session, event, "", [{"name": "simulate_scenario", "status": "ok", "source": "life-event"}])


def apply_scenario(db: Session, session_id: str, scenario_id: str) -> dict[str, Any]:
    session = _session(db, session_id)
    scenario = db.get(ScenarioRow, scenario_id)
    if scenario is None or scenario.session_id != session.id:
        raise KeyError(scenario_id)
    profile = session.profile
    assert profile is not None
    updated = apply_patch(to_inputs(profile), scenario.patch or {})
    _write_inputs(db, profile, updated)
    scenario.applied = True
    session.active_scenario_id = None
    _touch(session)
    calc = calculate(to_inputs(profile))
    _store_calculation(db, session, calc, "base", "Current plan")
    _add_message(
        db,
        session,
        "assistant",
        f"I kept “{scenario.label}” on the plan. The estimated protection gap is now {fmt(calc['gap'])}.",
        {"tools": [{"name": "update_customer_profile", "status": "ok"}, {"name": "calculate_coverage_need", "status": "ok", "source": "engine"}]},
    )
    db.commit()
    return state(db, session.id)


def discard_scenario(db: Session, session_id: str, scenario_id: str) -> dict[str, Any]:
    session = _session(db, session_id)
    if session.active_scenario_id == scenario_id:
        session.active_scenario_id = None
    scenario = db.get(ScenarioRow, scenario_id)
    if scenario and scenario.session_id == session.id:
        _add_message(db, session, "assistant", f"Discarded the preview “{scenario.label}”. Your saved plan is unchanged.", {"tools": []})
    db.commit()
    return state(db, session.id)


def timeline_view(db: Session, session_id: str, year_offset: int | None) -> dict[str, Any]:
    snapshot = state(db, session_id)
    return get_coverage_timeline(snapshot["calculation"], year_offset)


def stress_view(db: Session, session_id: str, coverage: int) -> dict[str, Any]:
    snapshot = state(db, session_id)
    sample = stress_coverage(snapshot["calculation"], coverage)
    return {"requested": coverage, "sample": sample}


def compare_view(db: Session, session_id: str) -> dict[str, Any]:
    snapshot = state(db, session_id)
    return compare_coverage_types(snapshot["calculation"])


def summary_view(db: Session, session_id: str) -> dict[str, Any]:
    snapshot = state(db, session_id)
    calc = snapshot["calculation"]
    return {
        "session": snapshot["session"],
        "profile": snapshot["profile"],
        "gap": calc.get("gap"),
        "gap_low": calc.get("gap_low"),
        "gap_high": calc.get("gap_high"),
        "band_note": calc.get("band_note"),
        "components": calc.get("components"),
        "resources": calc.get("resources"),
        "gap_allocation": calc.get("gap_allocation"),
        "formula": calc.get("formula"),
        "assumptions": calc.get("assumptions"),
        "facts": calc.get("facts"),
        "need_profile": calc.get("need_profile"),
        "professional_questions": calc.get("professional_questions"),
        "comparison": calc.get("comparison"),
        "disclaimer": DISCLAIMER,
    }


def search_knowledge(db: Session, query: str) -> list[dict[str, Any]]:
    return _public_notes(_notes(db, query or "term permanent whole life"))


def to_inputs(profile: ProfileRow) -> Inputs:
    sources = dict(profile.field_sources or {})
    dependents = [
        DependentIn(
            age=item.age,
            education_goal=item.education_goal,
            education_is_estimate=item.education_is_estimate,
            label=item.label,
        )
        for item in profile.dependents
    ]
    return Inputs(
        age=profile.age,
        partner=profile.partner,
        annual_income=profile.annual_income,
        income_replacement_years=profile.income_replacement_years,
        income_replacement_percent=profile.income_replacement_percent,
        mortgage_balance=profile.mortgage_balance,
        mortgage_years_remaining=profile.mortgage_years_remaining,
        other_debt=profile.other_debt,
        existing_employer_coverage=profile.existing_employer_coverage,
        existing_personal_coverage=profile.existing_personal_coverage,
        savings_allocated=profile.savings_allocated,
        lifelong_legacy_goal=profile.lifelong_legacy_goal,
        other_needs=profile.other_needs,
        include_education=profile.include_education,
        cash_value_interest=profile.cash_value_interest,
        monthly_budget_preference=profile.monthly_budget_preference,
        dependents_confirmed=bool(profile.dependents_confirmed),
        dependents=dependents,
        sources=sources,
    )


def serialize_profile(profile: ProfileRow) -> dict[str, Any]:
    payload = {field: getattr(profile, field) for field in PROFILE_FIELDS}
    payload["field_sources"] = profile.field_sources or {}
    payload["dependents"] = [
        {
            "id": item.id,
            "label": item.label,
            "age": item.age,
            "education_goal": item.education_goal,
            "education_is_estimate": item.education_is_estimate,
        }
        for item in profile.dependents
    ]
    return payload


DISCLAIMER = (
    "LifeLens is an educational needs-analysis tool. It does not provide insurance, tax, or investment advice, "
    "and it does not quote premiums or recommend a specific product. Every coverage figure is an estimate from the "
    "assumptions shown. Talk with a licensed financial professional before making a decision."
)


def _preview_event(db: Session, session: SessionRow, event: str, preface: str, tool_trace: list[dict[str, Any]]) -> dict[str, Any]:
    profile = session.profile
    assert profile is not None
    base_inputs = to_inputs(profile)
    base_calc = calculate(base_inputs)
    spec = life_event_patch(event, base_inputs)
    if spec is None:
        _add_message(db, session, "assistant", "I can preview another child, a home, a job change, a raise, college starting, paying off debt, marriage, or retiring earlier.", {"tools": tool_trace})
        db.commit()
        return state(db, session.id)
    if spec.get("empty") or not spec.get("patch"):
        _add_message(db, session, "assistant", spec.get("note") or "That event needs more of the plan filled in first.", {"tools": tool_trace})
        db.commit()
        return state(db, session.id)
    patch = spec["patch"]
    patch["note"] = spec.get("note") or ""
    scenario_calc = calculate(apply_patch(base_inputs, patch))
    _store_calculation(db, session, base_calc, "base", "Current plan")
    scenario = _store_scenario(db, session, spec["label"], spec.get("note") or "", patch, scenario_calc, base_calc["gap"])
    tool_trace.append({"name": "simulate_scenario", "status": "ok", "source": "engine"})
    tool_trace.append({"name": "calculate_coverage_need", "status": "ok", "source": "engine"})
    reply = _compose(
        extracted={"heard": [], "education_choice": None, "is_education_question": False},
        base_calc=base_calc,
        scenario_calc=scenario_calc,
        scenario_label=spec["label"],
        scenario_note=spec.get("note") or "",
        questions=[],
        preface=preface,
        notes=[],
        note_prose="",
    )
    _add_message(db, session, "assistant", reply, {"tools": tool_trace, "questions": [], "scenario_id": scenario.id})
    session.active_scenario_id = scenario.id
    session.last_question_key = None
    _touch(session)
    db.commit()
    return state(db, session.id)


def _apply_llm_tools(text: str, extracted: dict[str, Any], calls: list[dict[str, Any]], trace: list[dict[str, Any]]) -> None:
    for call in calls:
        name = call["name"]
        arguments = call.get("arguments") or {}
        if name == "update_customer_profile":
            accepted = {}
            for key, value in arguments.items():
                if key == "dependents":
                    continue
                if key not in PROFILE_FIELDS or key in extracted["updates"]:
                    continue
                cleaned = _clean_field(key, value)
                if cleaned is None:
                    continue
                if not _grounded(text, key, cleaned):
                    trace.append({"name": name, "status": "rejected", "field": key, "reason": "Number was not in the message."})
                    continue
                accepted[key] = cleaned
            if accepted:
                extracted["updates"].update(accepted)
                for key in accepted:
                    extracted["sources"].setdefault(key, "user")
                trace.append({"name": name, "status": "ok", "fields": list(accepted)})
            dependents = arguments.get("dependents")
            if extracted["dependents"] is None and isinstance(dependents, list) and dependents:
                grounded = []
                for item in dependents:
                    age = item.get("age") if isinstance(item, dict) else None
                    if age is None or number_is_grounded(text, float(age)):
                        grounded.append(item)
                if grounded:
                    extracted["dependents"] = [
                        {
                            "age": item.get("age"),
                            "label": item.get("label") or f"Child {index + 1}",
                            "education_goal": None,
                            "education_is_estimate": False,
                        }
                        for index, item in enumerate(grounded)
                    ]
                    extracted["dependents_mode"] = "replace"
                    extracted["updates"]["dependents_confirmed"] = True
                    trace.append({"name": name, "status": "ok", "fields": ["dependents"]})
        elif name == "simulate_scenario" and not extracted["scenario_patch"]:
            profile_patch = {}
            for key, value in arguments.items():
                if key == "clear_education":
                    continue
                if key not in PROFILE_FIELDS:
                    continue
                cleaned = _clean_field(key, value)
                if cleaned is None:
                    continue
                if cleaned == 0 or _grounded(text, key, cleaned) or key == "include_education":
                    profile_patch[key] = cleaned
            patch: dict[str, Any] = {"profile": profile_patch, "sources": {key: "user" for key in profile_patch}}
            if arguments.get("clear_education") or arguments.get("include_education") is False:
                patch["clear_education"] = True
            if patch["profile"] or patch.get("clear_education"):
                extracted["scenario_patch"] = patch
                trace.append({"name": name, "status": "ok"})
        elif name == "life_event" and not extracted["life_event"]:
            event = str(arguments.get("event") or "")
            words = EVENT_WORDS.get(event, ())
            if event and any(word in text.lower() for word in words):
                extracted["life_event"] = event
                trace.append({"name": "simulate_scenario", "status": "ok", "event": event})
        elif name in {"calculate_coverage_need", "get_coverage_timeline", "compare_coverage_types", "retrieve_lincoln_guidance"}:
            trace.append({"name": name, "status": "queued"})


def _apply_extraction(profile: ProfileRow, extracted: dict[str, Any]) -> None:
    sources = dict(profile.field_sources or {})
    for key, value in extracted["updates"].items():
        if key not in PROFILE_FIELDS:
            continue
        setattr(profile, key, value)
    sources.update(extracted.get("sources") or {})
    profile.field_sources = sources
    mode = extracted.get("dependents_mode")
    if mode == "clear":
        profile.dependents.clear()
        profile.dependents_confirmed = True
    elif mode == "fill_ages" and extracted.get("dependents"):
        ages = [item.get("age") for item in extracted["dependents"]]
        targets = [item for item in profile.dependents if item.age is None] or list(profile.dependents)
        if len(ages) == len(profile.dependents):
            targets = list(profile.dependents)
        for row, age in zip(targets, ages):
            row.age = age
        profile.dependents_confirmed = True
    elif mode == "replace" and extracted.get("dependents") is not None:
        _replace_dependents(None, profile, extracted["dependents"], keep_education=True)
        profile.dependents_confirmed = True
    if extracted.get("clear_education"):
        profile.include_education = False
        for dependent in profile.dependents:
            dependent.education_goal = 0
            dependent.education_is_estimate = False
    if extracted.get("education_per_child") is not None:
        profile.include_education = True
        for dependent in profile.dependents:
            dependent.education_goal = extracted["education_per_child"]
            dependent.education_is_estimate = bool(extracted.get("education_is_estimate"))
        if not profile.dependents:
            profile.dependents.append(
                DependentRow(
                    id=new_id(),
                    profile_id=profile.id,
                    position=0,
                    label="Child 1",
                    age=None,
                    education_goal=extracted["education_per_child"],
                    education_is_estimate=bool(extracted.get("education_is_estimate")),
                )
            )
            profile.dependents_confirmed = True
    _apply_education_defaults(profile)


def _apply_education_defaults(profile: ProfileRow) -> None:
    if profile.include_education is True:
        for dependent in profile.dependents:
            if dependent.education_goal is None:
                dependent.education_goal = DEFAULT_COLLEGE_COST
                dependent.education_is_estimate = True
    elif profile.include_education is False:
        for dependent in profile.dependents:
            dependent.education_goal = 0
            dependent.education_is_estimate = False


def _replace_dependents(db: Session | None, profile: ProfileRow, dependents: list[dict[str, Any]], keep_education: bool) -> None:
    previous = [
        (item.education_goal, item.education_is_estimate)
        for item in profile.dependents
    ]
    if db is not None:
        for item in list(profile.dependents):
            db.delete(item)
    profile.dependents.clear()
    for index, item in enumerate(dependents):
        education_goal = item.get("education_goal")
        education_is_estimate = bool(item.get("education_is_estimate"))
        if keep_education and education_goal is None and index < len(previous):
            education_goal, education_is_estimate = previous[index]
        profile.dependents.append(
            DependentRow(
                id=new_id(),
                profile_id=profile.id,
                position=index,
                label=item.get("label") or f"Child {index + 1}",
                age=item.get("age"),
                education_goal=education_goal,
                education_is_estimate=education_is_estimate,
            )
        )


def _write_inputs(db: Session, profile: ProfileRow, inputs: Inputs) -> None:
    for field in PROFILE_FIELDS:
        setattr(profile, field, getattr(inputs, field))
    profile.field_sources = dict(inputs.sources)
    _replace_dependents(
        db,
        profile,
        [
            {
                "label": item.label,
                "age": item.age,
                "education_goal": item.education_goal,
                "education_is_estimate": item.education_is_estimate,
            }
            for item in inputs.dependents
        ],
        keep_education=False,
    )


def _compose(
    extracted: dict[str, Any],
    base_calc: dict[str, Any],
    scenario_calc: dict[str, Any] | None,
    scenario_label: str,
    scenario_note: str,
    questions: list[dict[str, str]],
    preface: str,
    notes: list[dict[str, Any]],
    note_prose: str,
) -> str:
    lines = []
    if preface:
        lines.append(preface)
    heard = extracted.get("heard") or []
    if heard and scenario_calc is None:
        lines.append("Got it — " + ", ".join(heard) + ".")
    if scenario_calc is not None:
        lines.append(
            f"{scenario_label} moves the estimated protection gap from {fmt(base_calc['gap'])} to {fmt(scenario_calc['gap'])}."
        )
        if scenario_note:
            lines.append(scenario_note)
        lines.append("This is a preview. The saved plan stays as it is until you keep the change.")
    elif base_calc["ready"]:
        if base_calc["completeness"] == "partial":
            lines.append(
                f"With what is filled in, the estimated protection gap is {fmt(base_calc['gap'])}. It will move as the open items are added."
            )
        else:
            lines.append(f"The estimated protection gap is {fmt(base_calc['gap'])}.")
        lines.append("That figure is produced by the coverage engine. The model does not do the arithmetic.")
        assumed = [item for item in base_calc["assumptions"] if item["source"] in {"assumption", "estimated"}]
        if any(item["key"] == "income_replacement_years" for item in assumed):
            lines.append("Income support is using 10 years at 70% of income until you choose otherwise.")
        if any(item["key"] == "include_education" and item["source"] == "estimated" for item in assumed):
            lines.append(f"Education is using a {fmt(DEFAULT_COLLEGE_COST)} placeholder per child. You can replace it.")
    elif not heard:
        lines.append("Tell me about the household in whatever way is natural. A sentence or two is enough to start the map.")
    if extracted.get("education_choice") == "unknown":
        lines.append(
            f"That's okay. We can leave education out for now, you can enter an amount, or I can use a {fmt(DEFAULT_COLLEGE_COST)} placeholder per child and mark it as an estimate."
        )
    elif questions and scenario_calc is None:
        if len(questions) == 1:
            lines.append(questions[0]["prompt"])
        else:
            lines.append("Two things would help finish the picture:")
            for question in questions:
                lines.append(question["prompt"])
    if note_prose:
        lines.append(note_prose)
    elif notes and extracted.get("is_education_question"):
        lines.append(notes[0]["content"])
    if notes:
        lines.append("Sources are listed with the answer. They are educational notes linked to public Lincoln pages, not a product recommendation.")
    return "\n\n".join(line for line in lines if line)


def _note_prose(question: str, notes: list[dict[str, Any]]) -> str:
    if not notes:
        return ""
    allowed: set[int] = set()
    for note in notes:
        for raw in re.findall(r"\$?\d[\d,]*", note["content"]):
            digits = raw.replace("$", "").replace(",", "")
            if digits.isdigit():
                allowed.add(int(digits))
    allowed.add(DEFAULT_COLLEGE_COST)
    return explain_with_notes(question, notes, allowed)


def _notes(db: Session, query: str) -> list[dict[str, Any]]:
    rows = db.scalars(select(KnowledgeRow)).all()
    chunks = [
        {
            "title": row.title,
            "topic": row.topic,
            "content": row.content,
            "source_name": row.source_name,
            "source_url": row.source_url,
            "embedding": row.embedding,
            "slug": row.slug,
        }
        for row in rows
    ]
    found = retrieve_lincoln_guidance(query, chunks, EMBEDDER, limit=3)
    by_slug = {row.slug: row for row in rows}
    for chunk in chunks:
        row = by_slug.get(chunk["slug"])
        if row is not None and chunk.get("embedding") and not row.embedding:
            row.embedding = chunk["embedding"]
    return found


def _public_notes(notes: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {"title": note["title"], "source_name": note["source_name"], "source_url": note["source_url"], "content": note["content"]}
        for note in notes
    ]


def _question_keys(inputs: Inputs, mode: str) -> list[str]:
    missing = [item["key"] for item in calculate(inputs)["missing"]]
    limit = 1 if mode == "guided" else 2
    return missing[:limit]


def _opening(profile: ProfileRow, mode: str) -> tuple[str, list[dict[str, str]]]:
    if mode == "guided":
        questions = questions_for(_question_keys(to_inputs(profile), mode))
        text = "I'll ask one question at a time. You can also tell me the whole picture in a sentence whenever you want.\n\n" + questions[0]["prompt"]
        return text, questions
    return (
        "Let's figure out what your household would actually need.\n\nTell me about your situation however you'd like. For example: “I'm 37, married, two kids, make around $120k and still owe $300k on our house.”",
        [],
    )


def _scenario_label(patch: dict[str, Any], text: str) -> str:
    profile = patch.get("profile") or {}
    if "income_replacement_years" in profile:
        return f"Income support for {profile['income_replacement_years']} years"
    if profile.get("existing_employer_coverage") == 0:
        return "Employer coverage removed"
    if profile.get("mortgage_balance") == 0:
        return "Mortgage already paid"
    if patch.get("clear_education"):
        return "Education left out"
    trimmed = " ".join(text.split())
    return trimmed[:80] if trimmed else "What-if"


def _store_calculation(db: Session, session: SessionRow, result: dict[str, Any], kind: str, label: str) -> None:
    db.add(CalculationRow(id=new_id(), session_id=session.id, kind=kind, label=label, result=result))


def _store_scenario(
    db: Session,
    session: SessionRow,
    label: str,
    note: str,
    patch: dict[str, Any],
    result: dict[str, Any],
    base_gap: int,
) -> ScenarioRow:
    scenario = ScenarioRow(
        id=new_id(),
        session_id=session.id,
        label=label,
        note=note,
        patch=patch,
        result=result,
        base_gap=base_gap,
        scenario_gap=result.get("gap") or 0,
        applied=False,
    )
    db.add(scenario)
    db.flush()
    return scenario


def _scenario_brief(scenario: ScenarioRow) -> dict[str, Any]:
    return {
        "id": scenario.id,
        "label": scenario.label,
        "note": scenario.note,
        "base_gap": scenario.base_gap,
        "scenario_gap": scenario.scenario_gap,
        "applied": scenario.applied,
        "created_at": scenario.created_at.isoformat(),
    }


def _add_message(db: Session, session: SessionRow, role: str, content: str, payload: dict[str, Any]) -> None:
    db.add(MessageRow(id=new_id(), session_id=session.id, role=role, content=content, payload=payload))


def _session(db: Session, session_id: str) -> SessionRow:
    session = db.get(SessionRow, session_id)
    if session is None:
        raise KeyError(session_id)
    return session


def _touch(session: SessionRow) -> None:
    session.updated_at = utcnow()


def _ts(value: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


def _clean_field(key: str, value: Any) -> Any:
    if value is None:
        return None
    if key in {"partner", "include_education", "cash_value_interest", "dependents_confirmed"}:
        return bool(value)
    if key in {"age", "income_replacement_years", "mortgage_years_remaining"}:
        number = int(value)
        if key == "age" and not 16 <= number <= 90:
            return None
        if key != "age" and not 1 <= number <= 50:
            return None
        return number
    if key == "income_replacement_percent":
        number = float(value)
        if number > 1:
            number = number / 100
        if not 0.1 <= number <= 1:
            return None
        return number
    if key in MONEY_FIELDS:
        number = float(value)
        if number < 0 or number > 100_000_000:
            return None
        return number
    return value


def _grounded(text: str, key: str, value: Any) -> bool:
    if key in {"partner", "include_education", "cash_value_interest", "dependents_confirmed"}:
        return True
    if key == "income_replacement_percent":
        percent = int(round(float(value) * 100))
        return bool(re.search(rf"\b{percent}\s*(%|percent)\b", text.lower()))
    if isinstance(value, (int, float)):
        return number_is_grounded(text, float(value))
    return False


def _safe_preface(text: str) -> str:
    cleaned = " ".join(text.split())
    if not cleaned or len(cleaned) > 280:
        return ""
    if re.search(r"\$|\d{3,}|premium|recommend|should buy|need \$", cleaned, flags=re.I):
        return ""
    return cleaned
