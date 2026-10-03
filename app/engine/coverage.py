"""Auditable life-insurance needs engine.

Coverage need
    = income replacement
    + mortgage payoff
    + other debt
    + education goals
    + other needs named by the user
    + lifelong legacy goal
    - existing coverage
    - assets the user earmarked for these needs

Every dollar on screen is produced here. Defaults are returned as named
assumptions. Unknown money is not invented; if a field was skipped or not
yet answered, it contributes $0 and is listed as open.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date
from typing import Any


INDEPENDENT_AGE = 22
COLLEGE_START_AGE = 18
DEFAULT_REPLACEMENT_PERCENT = 0.70
DEFAULT_REPLACEMENT_YEARS = 10
DEFAULT_COLLEGE_COST = 100_000
DEFAULT_MORTGAGE_YEARS = 20
STRESS_STEP = 25_000

# Existing resources reduce obligations first, then education, then income.
RESOURCE_ORDER = ("other_debt", "other_needs", "mortgage", "education", "income", "legacy")

ALLOCATION_COPY = {
    "mortgage": ("Keep the home", "The mortgage balance still outstanding after existing resources."),
    "income": ("Give your family an income runway", "Income support that is not already offset."),
    "education": ("Help protect education plans", "Education funding still uncovered."),
    "other_debt": ("Clear other debt", "Other debt still outstanding after existing resources."),
    "other_needs": ("Cover other needs you named", "Other amounts you asked to include."),
    "legacy": ("Leave a lifelong amount", "The lifelong goal that remains after other needs."),
}


@dataclass
class DependentIn:
    age: int | None = None
    education_goal: float | None = None
    education_is_estimate: bool = False
    label: str = ""


@dataclass
class Inputs:
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
    dependents_confirmed: bool = False
    dependents: list[DependentIn] = field(default_factory=list)
    # user | assumption | estimated | skipped | unknown
    sources: dict[str, str] = field(default_factory=dict)


def money(value: float | int | None) -> int:
    return int(round(value or 0))


def _source(inputs: Inputs, key: str, default: str = "unknown") -> str:
    return inputs.sources.get(key, default)


def _closed(inputs: Inputs, key: str) -> bool:
    return _source(inputs, key) in {"user", "skipped", "assumption"}


def calculate(inputs: Inputs) -> dict[str, Any]:
    assumptions: list[dict[str, Any]] = []
    facts: list[dict[str, Any]] = []

    percent = inputs.income_replacement_percent
    percent_source = _source(inputs, "income_replacement_percent")
    if inputs.annual_income and percent is None:
        percent = DEFAULT_REPLACEMENT_PERCENT
        percent_source = "assumption"

    years = inputs.income_replacement_years
    years_source = _source(inputs, "income_replacement_years")
    if inputs.annual_income and years is None:
        years = DEFAULT_REPLACEMENT_YEARS
        years_source = "assumption"

    income_amount = 0
    if inputs.annual_income and percent and years:
        income_amount = money(inputs.annual_income * percent * years)

    mortgage_amount = money(inputs.mortgage_balance) if inputs.mortgage_balance is not None else 0
    mortgage_years = inputs.mortgage_years_remaining
    mortgage_years_source = _source(inputs, "mortgage_years_remaining")
    if mortgage_amount > 0 and mortgage_years is None:
        if inputs.age is not None and inputs.age < 65:
            mortgage_years = min(30, max(1, 65 - inputs.age))
        else:
            mortgage_years = DEFAULT_MORTGAGE_YEARS
        mortgage_years_source = "assumption"

    debt_amount = money(inputs.other_debt) if inputs.other_debt is not None else 0
    other_amount = money(inputs.other_needs) if inputs.other_needs is not None else 0
    legacy_amount = money(inputs.lifelong_legacy_goal) if inputs.lifelong_legacy_goal is not None else 0

    education_amount = 0
    education_estimated = False
    education_detail_parts: list[str] = []
    per_child: list[dict[str, Any]] = []
    for index, dependent in enumerate(inputs.dependents):
        goal = 0
        estimated = False
        if inputs.include_education is False:
            goal = 0
        elif dependent.education_goal is not None and inputs.include_education is not False:
            goal = money(dependent.education_goal)
            estimated = bool(dependent.education_is_estimate)
        elif inputs.include_education is True:
            goal = DEFAULT_COLLEGE_COST
            estimated = True
        label = dependent.label or f"Child {index + 1}"
        per_child.append(
            {
                "label": label,
                "age": dependent.age,
                "education_goal": goal,
                "education_is_estimate": estimated,
                "years_of_dependency": _dependency_years(dependent.age),
                "college_start": _college_start(dependent.age),
                "college_end": _college_end(dependent.age),
            }
        )
        if goal:
            education_amount += goal
            if estimated:
                education_estimated = True
            education_detail_parts.append(f"{label} {fmt(goal)}")

    employer = money(inputs.existing_employer_coverage) if inputs.existing_employer_coverage is not None else 0
    personal = money(inputs.existing_personal_coverage) if inputs.existing_personal_coverage is not None else 0
    savings = money(inputs.savings_allocated) if inputs.savings_allocated is not None else 0

    components = [
        _component(
            "income",
            "Replace family income",
            income_amount,
            _income_detail(inputs.annual_income, percent, years, years_source),
        ),
        _component("mortgage", "Pay off the mortgage", mortgage_amount, "Balance that would need to be cleared"),
        _component("other_debt", "Other debt", debt_amount, "Debts other than the mortgage"),
        _component(
            "education",
            "Education goals",
            education_amount,
            ", ".join(education_detail_parts) if education_detail_parts else "No education amount in the plan",
        ),
        _component("other_needs", "Other needs", other_amount, "Amounts you asked to include"),
        _component("legacy", "Lifelong legacy goal", legacy_amount, "Protection that would not expire with a term period"),
    ]
    components = [item for item in components if item["amount"] > 0]
    gross = sum(item["amount"] for item in components)

    resources = []
    if employer:
        resources.append({"key": "employer", "label": "Existing work insurance", "amount": employer, "detail": "Coverage you said is through work"})
    if personal:
        resources.append({"key": "personal", "label": "Existing personal insurance", "amount": personal, "detail": "Personal coverage you already have"})
    if savings:
        resources.append({"key": "savings", "label": "Assets earmarked for these needs", "amount": savings, "detail": "Savings you said can be used for this plan"})
    total_resources = sum(item["amount"] for item in resources)
    gap = max(0, gross - total_resources)

    allocation = _allocate_gap(components, total_resources)

    if inputs.annual_income is not None:
        facts.append(_fact("annual_income", "Income", fmt(inputs.annual_income), "user"))
    if percent is not None and inputs.annual_income:
        bucket = facts if percent_source == "user" else assumptions
        bucket.append(
            _fact(
                "income_replacement_percent",
                "Income replaced",
                f"{round(percent * 100)}%",
                percent_source,
                editable=True,
            )
        )
    if years is not None and inputs.annual_income:
        bucket = facts if years_source == "user" else assumptions
        bucket.append(
            _fact(
                "income_replacement_years",
                "Income support",
                f"{years} years",
                years_source,
                editable=True,
            )
        )
    if inputs.mortgage_balance is not None:
        facts.append(_fact("mortgage_balance", "Mortgage", fmt(inputs.mortgage_balance), _source(inputs, "mortgage_balance", "user"), editable=True))
    if mortgage_amount > 0 and mortgage_years is not None:
        bucket = facts if mortgage_years_source == "user" else assumptions
        bucket.append(
            _fact(
                "mortgage_years_remaining",
                "Mortgage timeline",
                f"{mortgage_years} years",
                mortgage_years_source,
                editable=True,
            )
        )
    if inputs.other_debt is not None:
        facts.append(_fact("other_debt", "Other debt", fmt(inputs.other_debt), _source(inputs, "other_debt", "user"), editable=True))
    if inputs.existing_employer_coverage is not None:
        facts.append(
            _fact(
                "existing_employer_coverage",
                "Work coverage",
                fmt(inputs.existing_employer_coverage),
                _source(inputs, "existing_employer_coverage", "user"),
                editable=True,
            )
        )
    if inputs.existing_personal_coverage is not None:
        facts.append(
            _fact(
                "existing_personal_coverage",
                "Personal coverage",
                fmt(inputs.existing_personal_coverage),
                _source(inputs, "existing_personal_coverage", "user"),
                editable=True,
            )
        )
    if inputs.savings_allocated is not None:
        facts.append(_fact("savings_allocated", "Earmarked savings", fmt(inputs.savings_allocated), _source(inputs, "savings_allocated", "user"), editable=True))
    if inputs.lifelong_legacy_goal is not None:
        facts.append(_fact("lifelong_legacy_goal", "Lifelong goal", fmt(inputs.lifelong_legacy_goal), _source(inputs, "lifelong_legacy_goal", "user"), editable=True))
    if inputs.monthly_budget_preference is not None:
        facts.append(
            _fact(
                "monthly_budget_preference",
                "Monthly budget preference",
                fmt(inputs.monthly_budget_preference),
                _source(inputs, "monthly_budget_preference", "user"),
                editable=True,
            )
        )
    if inputs.include_education is True:
        assumptions.append(
            _fact(
                "include_education",
                "Education",
                "Included" + (" · placeholder" if education_estimated else ""),
                "estimated" if education_estimated else _source(inputs, "include_education", "user"),
                editable=True,
            )
        )
    elif inputs.include_education is False:
        facts.append(_fact("include_education", "Education", "Left out", _source(inputs, "include_education", "user")))

    for key, label in (
        ("existing_personal_coverage", "Personal coverage"),
        ("existing_employer_coverage", "Work coverage"),
        ("other_debt", "Other debt"),
        ("savings_allocated", "Earmarked savings"),
        ("lifelong_legacy_goal", "Lifelong goal"),
    ):
        value = getattr(inputs, key)
        source = _source(inputs, key)
        if value is None and source == "skipped":
            assumptions.append(_fact(key, label, "Left out for now", "skipped", editable=True))
        elif value is None and key in {"existing_personal_coverage", "lifelong_legacy_goal", "savings_allocated"}:
            assumptions.append(_fact(key, label, "Not entered · counted as $0", "unknown", editable=True))

    if inputs.annual_income is None:
        assumptions.append(_fact("annual_income", "Income", "Not entered", "unknown", editable=True))
    if inputs.mortgage_balance is None:
        assumptions.append(_fact("mortgage_balance", "Mortgage", "Not entered · not in the total", "unknown", editable=True))
    if not inputs.dependents_confirmed:
        assumptions.append(_fact("dependents", "Dependents", "Not entered", "unknown", editable=True))
    elif any(item["age"] is None for item in per_child):
        assumptions.append(_fact("dependent_ages", "Dependent ages", "Not entered", "unknown", editable=True))
    if inputs.include_education is None and inputs.dependents:
        assumptions.append(_fact("include_education", "Education", "Not chosen yet", "unknown", editable=True))

    gap_low, gap_high, band_note = _sensitivity(
        inputs=inputs,
        percent=percent or 0,
        years=years,
        years_source=years_source,
        education_amount=education_amount,
        education_estimated=education_estimated,
        fixed_rest=mortgage_amount + debt_amount + other_amount + legacy_amount,
        resources=total_resources,
    )

    timeline = _timeline(
        inputs=inputs,
        percent=percent or 0,
        years=years or 0,
        mortgage_amount=mortgage_amount,
        mortgage_years=mortgage_years or 0,
        debt_amount=debt_amount,
        other_amount=other_amount,
        legacy_amount=legacy_amount,
        education_children=per_child,
        resources=total_resources,
    )
    need_profile = _need_profile(
        inputs=inputs,
        income_amount=income_amount,
        mortgage_amount=mortgage_amount,
        mortgage_years=mortgage_years,
        mortgage_years_source=mortgage_years_source,
        debt_amount=debt_amount,
        education_amount=education_amount,
        legacy_amount=legacy_amount,
        other_amount=other_amount,
        years=years,
        years_source=years_source,
        children=per_child,
    )
    comparison = _comparison(need_profile, inputs)
    missing = _missing(inputs)
    ready = gross > 0
    open_essentials = [item["key"] for item in missing if item["essential"]]
    completeness = "ready" if ready and not open_essentials else ("partial" if ready else "empty")

    return {
        "ready": ready,
        "completeness": completeness,
        "formula": (
            "Coverage need = income replacement + mortgage + other debt + education + other needs + legacy goal. "
            "Protection gap = coverage need − work coverage − personal coverage − earmarked savings. "
            "Income replacement = annual income × replacement percent × years. "
            "No discount rate or inflation factor is applied, so the arithmetic stays visible."
        ),
        "components": components,
        "gross_need": gross,
        "resources": resources,
        "total_resources": total_resources,
        "gap": gap,
        "gap_low": gap_low,
        "gap_high": gap_high,
        "band_note": band_note,
        "gap_allocation": allocation,
        "resource_order_note": (
            "Work coverage, personal coverage, and earmarked savings are applied first to other debt, "
            "then other named needs, then the mortgage, then education, then income support, then any lifelong goal. "
            "The amounts below are what remains."
        ),
        "facts": facts,
        "assumptions": assumptions,
        "timeline": timeline,
        "need_profile": need_profile,
        "comparison": comparison,
        "stress_samples": _stress_samples(
            gross=gross,
            mortgage=mortgage_amount,
            debt=debt_amount,
            other=other_amount,
            annual_support=money((inputs.annual_income or 0) * (percent or 0)),
            income_years=years or 0,
            education=education_amount,
            legacy=legacy_amount,
        ),
        "professional_questions": _professional_questions(inputs, need_profile, education_estimated),
        "missing": missing,
        "children": per_child,
        "resolved": {
            "income_replacement_percent": percent,
            "income_replacement_years": years,
            "mortgage_years_remaining": mortgage_years,
            "education_is_estimate": education_estimated,
        },
    }


def fmt(value: float | int | None) -> str:
    return f"${money(value):,}"


def _component(key: str, label: str, amount: int, detail: str) -> dict[str, Any]:
    return {"key": key, "label": label, "amount": amount, "detail": detail, "sign": 1}


def _fact(key: str, label: str, value: str, source: str, editable: bool = False) -> dict[str, Any]:
    return {"key": key, "label": label, "value": value, "source": source, "editable": editable}


def _income_detail(income: float | None, percent: float | None, years: int | None, years_source: str) -> str:
    if not income or not percent or not years:
        return "Income replacement needs an income amount"
    note = " · length is an assumption you can change" if years_source == "assumption" else ""
    return f"{fmt(income)} × {round(percent * 100)}% × {years} years{note}"


def _dependency_years(age: int | None) -> int | None:
    if age is None:
        return None
    return max(0, INDEPENDENT_AGE - age)


def _college_start(age: int | None) -> int | None:
    if age is None or age >= INDEPENDENT_AGE:
        return None
    return max(0, COLLEGE_START_AGE - age)


def _college_end(age: int | None) -> int | None:
    if age is None or age >= INDEPENDENT_AGE:
        return None
    return max(0, INDEPENDENT_AGE - age)


def _allocate_gap(components: list[dict[str, Any]], resources: int) -> list[dict[str, Any]]:
    by_key = {item["key"]: item["amount"] for item in components}
    remaining = resources
    allocation = []
    for key in RESOURCE_ORDER:
        amount = by_key.get(key, 0)
        if amount <= 0:
            continue
        covered = min(remaining, amount)
        remaining -= covered
        left = amount - covered
        if left <= 0:
            continue
        title, blurb = ALLOCATION_COPY[key]
        allocation.append({"key": key, "label": title, "amount": left, "blurb": blurb})
    # Narrative order for the card, not subtraction order.
    narrative = ["mortgage", "income", "education", "other_debt", "other_needs", "legacy"]
    order = {key: index for index, key in enumerate(narrative)}
    allocation.sort(key=lambda item: order.get(item["key"], 99))
    return allocation


def _sensitivity(
    inputs: Inputs,
    percent: float,
    years: int | None,
    years_source: str,
    education_amount: int,
    education_estimated: bool,
    fixed_rest: int,
    resources: int,
) -> tuple[int, int, str]:
    if not inputs.annual_income or not years:
        gap = max(0, fixed_rest + education_amount - resources)
        return gap, gap, "Add income to see how the range moves."

    low_years = years
    high_years = years
    notes = []
    if years_source != "user":
        low_years = max(1, years - 3)
        high_years = years + 3
        notes.append(f"income support of {low_years}–{high_years} years")
    low_edu = education_amount
    high_edu = education_amount
    if education_estimated and education_amount:
        low_edu = money(education_amount * 0.75)
        high_edu = money(education_amount * 1.25)
        notes.append("the education placeholder moving 25% either way")
    low_income = money(inputs.annual_income * percent * low_years)
    high_income = money(inputs.annual_income * percent * high_years)
    low = max(0, low_income + fixed_rest + low_edu - resources)
    high = max(0, high_income + fixed_rest + high_edu - resources)
    if not notes:
        return low, high, "You set the inputs that move this range, so the low and high match the estimate."
    return low, high, "The range only flexes " + " and ".join(notes) + "."


def _timeline(
    inputs: Inputs,
    percent: float,
    years: int,
    mortgage_amount: int,
    mortgage_years: int,
    debt_amount: int,
    other_amount: int,
    legacy_amount: int,
    education_children: list[dict[str, Any]],
    resources: int,
) -> dict[str, Any]:
    child_ends = [item["years_of_dependency"] or 0 for item in education_children]
    college_ends = [item["college_end"] or 0 for item in education_children]
    horizon = max([years, mortgage_years, *child_ends, *college_ends, 15])
    if inputs.age is not None:
        horizon = min(horizon, max(10, 90 - inputs.age))
    horizon = int(min(max(horizon, 10), 45))
    start_year = date.today().year
    points = []
    annual_support = (inputs.annual_income or 0) * percent
    for offset in range(horizon + 1):
        income_left = money(annual_support * max(0, years - offset))
        if mortgage_amount and mortgage_years:
            mortgage_left = money(mortgage_amount * max(0, 1 - offset / mortgage_years))
        else:
            mortgage_left = mortgage_amount if offset == 0 else mortgage_amount
        education_left = 0
        for child in education_children:
            end = child["college_end"]
            if end is None:
                continue
            if offset < end:
                education_left += child["education_goal"]
        need = income_left + mortgage_left + debt_amount + education_left + other_amount + legacy_amount
        points.append(
            {
                "year_offset": offset,
                "calendar_year": start_year + offset,
                "need": need,
                "gap": max(0, need - resources),
                "income": income_left,
                "mortgage": mortgage_left,
                "education": education_left,
                "debt": debt_amount,
                "legacy": legacy_amount,
                "existing": resources,
            }
        )
    rows = []
    if mortgage_amount and mortgage_years:
        rows.append({"key": "mortgage", "label": "Mortgage", "start": 0, "end": mortgage_years, "tone": "mortgage"})
    if years:
        rows.append({"key": "income", "label": "Income needed by family", "start": 0, "end": years, "tone": "income"})
    for index, child in enumerate(education_children):
        end = child["years_of_dependency"]
        if end:
            rows.append(
                {
                    "key": f"child-{index}",
                    "label": f"{child['label']} dependent",
                    "start": 0,
                    "end": end,
                    "tone": "child",
                }
            )
        if child["education_goal"] and child["college_start"] is not None and child["college_end"]:
            rows.append(
                {
                    "key": f"college-{index}",
                    "label": f"{child['label']} college",
                    "start": child["college_start"],
                    "end": child["college_end"],
                    "tone": "college",
                }
            )
    if resources:
        rows.append({"key": "existing", "label": "Existing resources", "start": 0, "end": horizon, "tone": "existing"})
    return {
        "start_year": start_year,
        "horizon": horizon,
        "points": points,
        "rows": rows,
        "debt_note": "Other debt stays level because no payoff schedule was provided.",
        "existing_note": "Existing coverage is held flat. Employer coverage may not be portable, which is a question for a professional.",
    }


def _need_profile(
    inputs: Inputs,
    income_amount: int,
    mortgage_amount: int,
    mortgage_years: int | None,
    mortgage_years_source: str,
    debt_amount: int,
    education_amount: int,
    legacy_amount: int,
    other_amount: int,
    years: int | None,
    years_source: str,
    children: list[dict[str, Any]],
) -> dict[str, Any]:
    temporary = income_amount + mortgage_amount + debt_amount + education_amount + other_amount
    total = temporary + legacy_amount
    temp_share = (temporary / total) if total else 1
    if not total:
        temporary_level = "Unknown"
        lifelong_level = "Unknown"
    else:
        temporary_level = "High" if temp_share >= 0.8 else ("Medium" if temp_share >= 0.45 else "Low")
        if legacy_amount <= 0:
            lifelong_level = "Low"
        else:
            share = legacy_amount / total
            lifelong_level = "High" if share >= 0.35 else "Medium"
    if inputs.cash_value_interest:
        cash = "Mentioned"
    else:
        cash = "Not selected"

    drivers = []
    if mortgage_amount:
        if mortgage_years:
            suffix = "assumed" if mortgage_years_source == "assumption" else "from what you entered"
            drivers.append({"label": "Mortgage", "years": mortgage_years, "detail": f"~{mortgage_years} years · {suffix}"})
        else:
            drivers.append({"label": "Mortgage", "years": None, "detail": "Balance included, timeline not set"})
    dep_years = [item["years_of_dependency"] for item in children if item["years_of_dependency"]]
    if dep_years:
        youngest = max(dep_years)
        drivers.append({"label": "Youngest dependent", "years": youngest, "detail": f"~{youngest} years of dependency"})
    elif children and any(item["age"] is None for item in children):
        drivers.append({"label": "Dependents", "years": None, "detail": "Ages not entered yet"})
    if years and income_amount:
        how = "selected" if years_source == "user" else "assumed until you change it"
        drivers.append({"label": "Income replacement", "years": years, "detail": f"{years} years · {how}"})
    college_ends = [item["college_end"] for item in children if item["education_goal"] and item["college_end"]]
    if college_ends:
        last = max(college_ends)
        drivers.append({"label": "College window", "years": last, "detail": f"Last education window ends in ~{last} years"})
    elif education_amount:
        drivers.append({"label": "Education", "years": None, "detail": "Included, timing needs ages"})
    if legacy_amount:
        drivers.append({"label": "Legacy goal", "years": None, "detail": fmt(legacy_amount)})
    else:
        drivers.append({"label": "Legacy goal", "years": None, "detail": "None selected"})

    finite = [item["years"] for item in drivers if isinstance(item.get("years"), int)]
    horizon = max(finite) if finite else 0
    if not total:
        headline = "The map starts once a need is entered"
    elif lifelong_level == "Low" and temporary_level in {"High", "Medium"}:
        headline = "Your need is mostly time-bound"
    elif lifelong_level == "High":
        headline = "You described a meaningful lifelong goal"
    else:
        headline = "Your picture mixes a time limit with a longer goal"

    return {
        "temporary": temporary_level,
        "lifelong": lifelong_level,
        "cash_value": cash,
        "temporary_amount": temporary,
        "legacy_amount": legacy_amount,
        "horizon_years": horizon,
        "headline": headline,
        "drivers": drivers,
    }


def _comparison(profile: dict[str, Any], inputs: Inputs) -> dict[str, Any]:
    horizon = profile["horizon_years"] or 0
    if horizon <= 10:
        suggested = 10
    elif horizon <= 15:
        suggested = 15
    elif horizon <= 20:
        suggested = 20
    elif horizon <= 30:
        suggested = 30
    else:
        suggested = None

    if suggested:
        term_period = (
            f"Level-premium term periods are commonly offered for 10, 15, 20, or 30 years. "
            f"The longest time-bound item on your map is about {horizon} years, so a {suggested}-year period is a concrete thing to discuss."
        )
    elif horizon > 30:
        term_period = (
            f"The longest item on your map runs about {horizon} years. Common level-premium term periods stop at 30 years, "
            f"so anything meant to last beyond that is part of the permanent-coverage conversation."
        )
    else:
        term_period = "Once a few timelines are filled in, this panel names a term length that matches them."

    term_points = [
        "Designed for a defined period, which matches needs that end — a mortgage, income support, or a child's dependency.",
        "Premiums for a level-premium term period are generally fixed for that period, and the death benefit is a stated face amount.",
        "Initial cost is generally lower than permanent coverage of a similar face amount.",
        "There is no cash-value account to draw on or to borrow against.",
    ]
    permanent_points = [
        "Permanent coverage is built to last longer than a term period, sometimes for a lifetime. Whole life is the traditional form: a lifelong death benefit, typically a fixed premium, and a cash-value component.",
        "Cash value, if the contract has it, can be a reason to consider permanent coverage. Growth, access, and any guarantees depend on the specific contract and are not illustrated here.",
        "Lincoln's public consumer pages present permanent coverage largely as indexed universal life and variable universal life, alongside term. Whole life is explained here because it is the classic permanent comparison, not because this tool quotes a Lincoln whole life policy.",
        "Permanent coverage generally costs more in the early years and involves more moving parts: charges, and for variable or indexed designs, limits on how cash value can change.",
    ]
    if inputs.lifelong_legacy_goal:
        permanent_points.insert(0, f"You set a lifelong goal of {fmt(inputs.lifelong_legacy_goal)}. A term period would not, by itself, still be in force after it expires.")
    if inputs.cash_value_interest:
        permanent_points.insert(0, "You mentioned an interest in cash value. That question belongs with permanent coverage, with the contract charges made explicit by a professional.")
    if suggested and profile["temporary"] == "High" and profile["lifelong"] == "Low":
        fit_term = "The needs you have actually named line up with a defined period."
        fit_permanent = "A lifelong contract is a different goal than the one currently on your map."
    elif profile["lifelong"] in {"Medium", "High"}:
        fit_term = "Term coverage can still match the part of the need that ends."
        fit_permanent = "The lifelong piece is the part a term period is not built to carry."
    else:
        fit_term = "Term coverage is the usual starting point when the goals have end dates."
        fit_permanent = "Permanent coverage becomes relevant if a goal should outlast those end dates."

    return {
        "headline": profile["headline"],
        "summary": term_period,
        "suggested_term_years": suggested,
        "term": {
            "title": "Term insurance",
            "fit": fit_term,
            "points": term_points,
        },
        "permanent": {
            "title": "Permanent coverage, including whole life",
            "fit": fit_permanent,
            "points": permanent_points,
        },
        "lincoln_note": (
            "Lincoln's public materials distinguish term coverage from permanent coverage, and they point people toward a financial professional "
            "before a product decision. This panel is education for your timeline. It is not a product recommendation, a premium, or an illustration."
        ),
        "sources": [
            {
                "title": "Lincoln Financial · Life insurance",
                "url": "https://www.lincolnfinancial.com/public/individuals/products/lifeinsurance",
            },
            {
                "title": "Lincoln Financial · Term life",
                "url": "https://www.lincolnfinancial.com/public/individuals/products/lifeinsurance/termlife",
            },
            {
                "title": "Lincoln Financial · Permanent life",
                "url": "https://www.lincolnfinancial.com/public/individuals/products/lifeinsurance/permanentlife",
            },
            {
                "title": "Lincoln Financial · Ready to get started",
                "url": "https://www.lincolnfinancial.com/public/individuals/products/lifeinsurance/readytogetstarted",
            },
        ],
    }


def _stress_samples(
    gross: int,
    mortgage: int,
    debt: int,
    other: int,
    annual_support: int,
    income_years: int,
    education: int,
    legacy: int,
) -> list[dict[str, Any]]:
    if gross <= 0 and mortgage + debt + education + legacy + annual_support <= 0:
        return []
    top = max(gross, 1_000_000)
    top = int(((top + STRESS_STEP - 1) // STRESS_STEP) * STRESS_STEP)
    top = min(top, 5_000_000)
    samples = []
    coverage = 0
    while coverage <= top:
        samples.append(
            _stress_one(
                coverage,
                mortgage=mortgage,
                debt=debt,
                other=other,
                annual_support=annual_support,
                income_years=income_years,
                education=education,
                legacy=legacy,
            )
        )
        coverage += STRESS_STEP
    return samples


def _stress_one(
    coverage: int,
    mortgage: int,
    debt: int,
    other: int,
    annual_support: int,
    income_years: int,
    education: int,
    legacy: int,
) -> dict[str, Any]:
    remaining = coverage
    items: list[dict[str, str]] = []

    def take(need: int) -> tuple[str, int]:
        nonlocal remaining
        if need <= 0:
            return "skip", 0
        if remaining >= need:
            remaining -= need
            return "yes", need
        if remaining > 0:
            filled = remaining
            remaining = 0
            return "partial", filled
        return "no", 0

    if mortgage > 0:
        status, filled = take(mortgage)
        items.append(_stress_item("Mortgage", status, mortgage, filled, "the mortgage"))
    if debt > 0:
        status, filled = take(debt)
        items.append(_stress_item("Other debt", status, debt, filled, "other debt"))
    if other > 0:
        status, filled = take(other)
        items.append(_stress_item("Other needs", status, other, filled, "other needs"))
    if annual_support > 0 and income_years > 0:
        target = annual_support * income_years
        status, filled = take(target)
        years_covered = filled / annual_support if annual_support else 0
        if status == "yes":
            detail = f"{income_years} years of income support"
        elif status == "partial":
            shown = max(1, int(years_covered)) if years_covered >= 0.5 else 0
            detail = f"About {shown} years of income support" if shown else "Less than a year of income support"
        else:
            detail = "Income support not covered"
        items.append({"label": "Income support", "status": status, "detail": detail})
    if education > 0:
        status, filled = take(education)
        if status == "partial":
            detail = f"Education partly covered ({fmt(filled)} of {fmt(education)})"
        elif status == "yes":
            detail = "Education goal covered"
        else:
            detail = "Education goal not covered"
        items.append({"label": "Education", "status": status, "detail": detail})
    if legacy > 0:
        status, filled = take(legacy)
        items.append(_stress_item("Lifelong goal", status, legacy, filled, "the lifelong goal"))
    if remaining > 0:
        items.append({"label": "Buffer", "status": "yes", "detail": f"Additional buffer of {fmt(remaining)}"})
    if not items:
        items.append({"label": "Plan", "status": "no", "detail": "Add a need to test an amount"})
    return {"coverage": coverage, "items": items}


def _stress_item(label: str, status: str, need: int, filled: int, noun: str) -> dict[str, str]:
    if status == "yes":
        detail = f"{label} covered"
    elif status == "partial":
        detail = f"{label} partly covered ({fmt(filled)} of {fmt(need)})"
    else:
        detail = f"{label} not covered"
    return {"label": label, "status": status, "detail": detail.replace(label, noun).capitalize() if False else detail}


def _missing(inputs: Inputs) -> list[dict[str, Any]]:
    rows = []

    def add(key: str, label: str, essential: bool) -> None:
        rows.append({"key": key, "label": label, "essential": essential})

    if not inputs.dependents_confirmed:
        add("dependents", "Who depends on your income", True)
    if inputs.annual_income is None and not _closed(inputs, "annual_income"):
        add("annual_income", "Income", True)
    if inputs.mortgage_balance is None and not _closed(inputs, "mortgage_balance"):
        add("mortgage_balance", "Mortgage balance", True)
    if inputs.other_debt is None and not _closed(inputs, "other_debt"):
        add("other_debt", "Other debt", True)
    if inputs.existing_employer_coverage is None and not _closed(inputs, "existing_employer_coverage"):
        add("existing_employer_coverage", "Coverage through work", True)
    if inputs.include_education is None and inputs.dependents_confirmed and inputs.dependents:
        add("include_education", "Whether to include education", True)
    if inputs.dependents_confirmed and any(item.age is None for item in inputs.dependents):
        add("dependent_ages", "Ages of the people who depend on you", True)
    if inputs.annual_income and inputs.income_replacement_years is None and not _closed(inputs, "income_replacement_years"):
        add("income_replacement_years", "How many years of income to replace", False)
    if inputs.existing_personal_coverage is None and not _closed(inputs, "existing_personal_coverage"):
        add("existing_personal_coverage", "Personal life insurance", False)
    if inputs.age is None and not _closed(inputs, "age"):
        add("age", "Your age", False)
    if inputs.partner is None and not _closed(inputs, "partner"):
        add("partner", "Whether anyone shares the household", False)
    if inputs.savings_allocated is None and not _closed(inputs, "savings_allocated"):
        add("savings_allocated", "Savings you want counted", False)
    if inputs.lifelong_legacy_goal is None and not _closed(inputs, "lifelong_legacy_goal"):
        add("lifelong_legacy_goal", "Any lifelong or legacy goal", False)
    return rows


def _professional_questions(inputs: Inputs, profile: dict[str, Any], education_estimated: bool) -> list[str]:
    questions = []
    if (inputs.existing_employer_coverage or 0) > 0:
        questions.append("Should my employer coverage count toward a long-term plan, or does it end if I leave the job?")
    if profile.get("horizon_years"):
        questions.append("What term length matches this family timeline, and what happens in the year after it ends?")
    if not inputs.lifelong_legacy_goal:
        questions.append("Do I have a lifelong coverage need that is not on this map yet?")
    if education_estimated:
        questions.append("How much of the education plan should sit inside life insurance versus savings that are already underway?")
    if inputs.partner:
        questions.append("How should this plan be coordinated with my partner's income and any coverage they already have?")
    if (inputs.mortgage_balance or 0) > 0:
        questions.append("If we refinance, move, or pay the mortgage down faster, how should the coverage change?")
    if inputs.cash_value_interest:
        questions.append("If cash value matters, which contract charges and risks come with that feature?")
    if not questions:
        questions.append("Which of these assumptions would a professional change first?")
    return questions[:6]


def apply_patch(inputs: Inputs, patch: dict[str, Any]) -> Inputs:
    """Return a new Inputs with a scenario patch applied. Does not mutate the original."""

    cloned = deepcopy(inputs)
    for key, value in (patch.get("profile") or {}).items():
        if not hasattr(cloned, key) or key in {"dependents", "sources"}:
            continue
        setattr(cloned, key, value)
    sources = dict(cloned.sources)
    for key, source in (patch.get("sources") or {}).items():
        sources[key] = source
    for key in (patch.get("profile") or {}):
        sources.setdefault(key, "user")
    cloned.sources = sources
    if patch.get("clear_education"):
        cloned.include_education = False
        cloned.sources["include_education"] = patch.get("sources", {}).get("include_education", "user")
        for dependent in cloned.dependents:
            dependent.education_goal = 0
            dependent.education_is_estimate = False
    for item in patch.get("add_dependents") or []:
        cloned.dependents.append(
            DependentIn(
                age=item.get("age"),
                education_goal=item.get("education_goal"),
                education_is_estimate=bool(item.get("education_is_estimate")),
                label=item.get("label") or f"Child {len(cloned.dependents) + 1}",
            )
        )
        cloned.dependents_confirmed = True
        if item.get("education_goal"):
            cloned.include_education = True
    if patch.get("adjust_dependents") == "college_start":
        candidates = [dep for dep in cloned.dependents if dep.age is None or dep.age < INDEPENDENT_AGE]
        if candidates:
            chosen = max(candidates, key=lambda dep: -1 if dep.age is None else dep.age)
            chosen.age = COLLEGE_START_AGE
            if chosen.education_goal:
                chosen.education_goal = money(chosen.education_goal * 0.5)
                chosen.education_is_estimate = True
    if patch.get("education_per_child") is not None:
        cloned.include_education = True
        amount = money(patch["education_per_child"])
        estimate = bool(patch.get("education_is_estimate"))
        if not cloned.dependents:
            cloned.dependents.append(DependentIn(label="Child 1", education_goal=amount, education_is_estimate=estimate))
            cloned.dependents_confirmed = True
        for dependent in cloned.dependents:
            dependent.education_goal = amount
            dependent.education_is_estimate = estimate
    return cloned


def life_event_patch(event: str, inputs: Inputs) -> dict[str, Any] | None:
    catalog = {
        "another_child": "Have another child",
        "buy_home": "Buy a home",
        "change_jobs": "Change jobs",
        "raise": "Get a raise",
        "child_starts_college": "A child starts college",
        "pay_off_debt": "Pay off other debt",
        "get_married": "Get married",
        "retire_earlier": "Retire earlier",
    }
    if event not in catalog:
        return None
    label = catalog[event]
    note = ""
    patch: dict[str, Any] = {"profile": {}, "sources": {}}
    if event == "another_child":
        education = DEFAULT_COLLEGE_COST if inputs.include_education else None
        patch["add_dependents"] = [
            {
                "age": 0,
                "label": "New child",
                "education_goal": education,
                "education_is_estimate": bool(education),
            }
        ]
        note = "Adds a newborn. Dependency runs to age 22."
        if education:
            note += f" Education uses the {fmt(DEFAULT_COLLEGE_COST)} placeholder because education is already in the plan."
        else:
            note += " Education was not added, because it is not part of the current plan."
    elif event == "buy_home":
        if not inputs.mortgage_balance:
            patch["profile"] = {"mortgage_balance": 400_000, "mortgage_years_remaining": 30}
            patch["sources"] = {"mortgage_balance": "assumption", "mortgage_years_remaining": "assumption"}
            note = "No mortgage was on the plan, so this preview uses a $400,000 balance over 30 years. Replace it with your number."
        else:
            patch["profile"] = {
                "mortgage_balance": money((inputs.mortgage_balance or 0) + 250_000),
                "mortgage_years_remaining": 30,
            }
            patch["sources"] = {"mortgage_balance": "assumption", "mortgage_years_remaining": "assumption"}
            note = "Adds $250,000 to the mortgage and resets the timeline to 30 years. This is a preview, not a loan quote."
    elif event == "change_jobs":
        patch["profile"] = {"existing_employer_coverage": 0}
        note = "Sets employer coverage to $0. Personal coverage is unchanged."
    elif event == "raise":
        if not inputs.annual_income:
            return {"label": label, "patch": {}, "note": "Income is not on the plan yet, so a raise cannot be applied.", "empty": True}
        patch["profile"] = {"annual_income": money(inputs.annual_income * 1.15)}
        note = "Increases income by 15% and recalculates income replacement. The replacement percent and years stay the same."
    elif event == "child_starts_college":
        if not inputs.dependents:
            return {"label": label, "patch": {}, "note": "Add a child before running this event.", "empty": True}
        patch["adjust_dependents"] = "college_start"
        note = "Moves the oldest dependent still at home to age 18 and cuts that education goal in half, as a stand-in for costs already underway."
    elif event == "pay_off_debt":
        patch["profile"] = {"other_debt": 0}
        note = "Clears other debt. The mortgage is unchanged."
    elif event == "get_married":
        patch["profile"] = {"partner": True}
        note = "Marks a partner in the household. It does not add their income; that stays a conversation with a professional."
    elif event == "retire_earlier":
        current = inputs.income_replacement_years or DEFAULT_REPLACEMENT_YEARS
        patch["profile"] = {"income_replacement_years": max(5, current - 5)}
        patch["sources"] = {"income_replacement_years": "user"}
        note = f"Shortens income support from {current} years to {max(5, current - 5)} years."
    return {"label": label, "patch": patch, "note": note, "empty": False}
