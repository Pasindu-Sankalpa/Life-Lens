"""Turn ordinary sentences into profile updates. Numbers only stick if they appear in the text."""

from __future__ import annotations

import re
from typing import Any


WORD_COUNTS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
}

EVENT_PATTERNS = (
    ("another_child", r"\b(another child|have a baby|new baby|have another kid|second child|third child)\b"),
    ("buy_home", r"\b(buy a home|buy a house|purchase a home|purchase a house)\b"),
    ("change_jobs", r"\b(change jobs|new job|lose my job|leave my job)\b"),
    ("raise", r"\b(get a raise|got a raise|salary increase|pay raise)\b"),
    ("child_starts_college", r"\b(starts college|start college|goes to college|child starts school)\b"),
    ("pay_off_debt", r"\b(pay off (?:my |the |our )?(?:other )?debt|debt is paid|debt.?free)\b"),
    ("get_married", r"\b(get married|getting married|just married)\b"),
    ("retire_earlier", r"\b(retire earlier|retire sooner|early retirement)\b"),
)

AMOUNT = r"(\$?\s*\d[\d,]*(?:\.\d+)?\s*(?:k|m|grand|thousand)?)"


def extract_message(text: str, last_question_key: str | None = None) -> dict[str, Any]:
    cleaned = " ".join(text.strip().split())
    low = cleaned.lower()
    result: dict[str, Any] = {
        "updates": {},
        "sources": {},
        "dependents": None,
        "dependents_mode": None,  # replace | fill_ages | clear
        "education_per_child": None,
        "education_is_estimate": False,
        "clear_education": False,
        "life_event": detect_life_event(low),
        "scenario_patch": parse_scenario(low),
        "education_choice": None,
        "is_skip": _is_skip(low),
        "is_education_question": _is_education_question(low),
        "heard": [],
    }
    if result["is_skip"] and last_question_key and not result["scenario_patch"]:
        _apply_skip(result, last_question_key)
        return result

    _ages_and_household(low, result)
    _money_fields(low, result)
    _education(low, result)
    _years_and_percent(low, result)
    _short_answer(cleaned, low, last_question_key, result)
    if result["life_event"] and result["life_event"] in {"another_child", "child_starts_college"}:
        result["dependents"] = None
        result["dependents_mode"] = None
    return result


def detect_life_event(low: str) -> str | None:
    if not re.search(r"\b(what if|suppose|imagine|simulate)\b", low) and not re.search(
        r"\b(another child|have a baby|buy a home|buy a house|change jobs|get a raise|starts college|pay off|get married|retire earlier)\b",
        low,
    ):
        # Still allow explicit event phrases without "what if".
        pass
    for name, pattern in EVENT_PATTERNS:
        if re.search(pattern, low):
            return name
    if re.search(r"\bemployer coverage disappears\b|\bwork (?:insurance|coverage) (?:disappears|is gone|goes away)\b", low):
        return None  # handled as a scenario, not the job-change story
    return None


def parse_scenario(low: str) -> dict[str, Any] | None:
    patch: dict[str, Any] = {"profile": {}, "sources": {}}
    triggered = bool(re.search(r"\b(what if|what happens|suppose|instead|only want|change)\b", low))

    if re.search(r"\b(employer|work|group)\b", low) and re.search(r"\b(disappear|disappears|gone|lose|lost|without|drops|zero|no longer)\b", low):
        patch["profile"]["existing_employer_coverage"] = 0
        triggered = True
    if re.search(r"\bmortgage\b", low) and re.search(r"\b(paid off|pay off|already paid|no mortgage|were zero|was zero)\b", low):
        patch["profile"]["mortgage_balance"] = 0
        triggered = True
    if re.search(r"\b(college|education|tuition)\b", low) and re.search(
        r"\b(not include|don't include|do not include|without|leave out|skip|no college|decide not|not to include)\b",
        low,
    ):
        patch["clear_education"] = True
        triggered = True
    years = re.search(r"\b(\d{1,2})\s+years?\b", low)
    if years and re.search(r"\b(income|salary|replace|support)\b", low):
        patch["profile"]["income_replacement_years"] = int(years.group(1))
        patch["sources"]["income_replacement_years"] = "user"
        triggered = True
    percent = re.search(r"\b(\d{1,3})\s*%", low)
    if percent and re.search(r"\b(income|salary|replace)\b", low):
        patch["profile"]["income_replacement_percent"] = int(percent.group(1)) / 100
        triggered = True
    if not triggered or (not patch["profile"] and not patch.get("clear_education")):
        return None
    return patch


def number_is_grounded(text: str, value: float) -> bool:
    low = text.lower().replace(",", "").replace("$", "")
    rounded = int(round(value))
    if re.search(rf"\b{rounded}\b", low):
        return True
    if rounded >= 1000 and rounded % 1000 == 0:
        k = rounded // 1000
        if re.search(rf"\b{k}\s*(k|grand|thousand)\b", low):
            return True
    if rounded >= 1_000_000 and rounded % 1_000_000 == 0:
        m = rounded // 1_000_000
        if re.search(rf"\b{m}\s*m\b", low):
            return True
    return False


def _is_skip(low: str) -> bool:
    stripped = low.strip(" .!?")
    return stripped in {
        "skip",
        "i don't know",
        "i dont know",
        "idk",
        "not sure",
        "later",
        "pass",
        "no idea",
        "unsure",
    }


def _is_education_question(low: str) -> bool:
    if re.search(r"\b(what if|i am|i'm|my mortgage|i make|i earn)\b", low):
        return False
    return bool(
        re.search(
            r"\b(what is|what's|whats|explain|difference between|compare|how does|tell me about)\b",
            low,
        )
        and re.search(r"\b(term|whole life|permanent|universal life|cash value|lincoln)\b", low)
    )


def _apply_skip(result: dict[str, Any], key: str) -> None:
    result["sources"][key] = "skipped"
    if key == "include_education":
        result["education_choice"] = "unknown"
        return
    if key == "partner":
        result["updates"]["partner"] = None
        return
    if key == "dependents":
        result["dependents_mode"] = "clear"
        result["updates"]["dependents_confirmed"] = True
        return
    if key in {
        "annual_income",
        "mortgage_balance",
        "other_debt",
        "existing_employer_coverage",
        "existing_personal_coverage",
        "savings_allocated",
        "lifelong_legacy_goal",
        "other_needs",
        "income_replacement_years",
        "age",
    }:
        result["updates"][key] = None


def _ages_and_household(low: str, result: dict[str, Any]) -> None:
    age_candidates: list[int] = []
    for match in re.finditer(r"\b(?:i'm|i am|im)\s+(\d{1,2})\b", low):
        age_candidates.append(int(match.group(1)))
    for match in re.finditer(r"\b(\d{1,2})\s+years old\b", low):
        age_candidates.append(int(match.group(1)))
    for match in re.finditer(r"\bage\s+(\d{1,2})\b", low):
        age_candidates.append(int(match.group(1)))
    for value in age_candidates:
        if 16 <= value <= 90:
            result["updates"]["age"] = value
            result["sources"]["age"] = "user"
            result["heard"].append(f"age {value}")
            break

    if re.search(r"\bcash value\b", low):
        result["updates"]["cash_value_interest"] = True
        result["sources"]["cash_value_interest"] = "user"
        result["heard"].append("an interest in cash value")

    if re.search(r"\b(not married|no spouse|single|unmarried)\b", low):
        result["updates"]["partner"] = False
        result["sources"]["partner"] = "user"
    elif re.search(r"\b(married|spouse|wife|husband|partner)\b", low):
        result["updates"]["partner"] = True
        result["sources"]["partner"] = "user"
        result["heard"].append("married" if "married" in low else "a partner")

    if re.search(r"\b(no|zero|without)\s+(kids|children|dependents)\b", low) or re.search(
        r"\bno one (else )?depends\b", low
    ):
        result["dependents_mode"] = "clear"
        result["updates"]["dependents_confirmed"] = True
        result["heard"].append("no dependents")
        return

    ages = _dependent_ages(low)
    count = _dependent_count(low)
    if ages and count and count != len(ages):
        count = len(ages)
    if ages:
        result["dependents"] = [
            {"age": item, "label": f"Child {index + 1}", "education_goal": None, "education_is_estimate": False}
            for index, item in enumerate(ages)
        ]
        result["dependents_mode"] = "replace"
        result["updates"]["dependents_confirmed"] = True
        result["heard"].append("children ages " + " and ".join(str(item) for item in ages))
    elif count:
        result["dependents"] = [
            {"age": None, "label": f"Child {index + 1}", "education_goal": None, "education_is_estimate": False}
            for index in range(count)
        ]
        result["dependents_mode"] = "replace"
        result["updates"]["dependents_confirmed"] = True
        result["heard"].append(f"{count} dependents")


def _dependent_ages(low: str) -> list[int]:
    match = re.search(
        r"\b(?:kids?|children|child|dependents?).{0,48}?\b(?:aged|ages|age)\s+((?:\d{1,2}\s*(?:,|and|&)\s*)+\d{1,2}|\d{1,2})\b",
        low,
    )
    if not match:
        match = re.search(r"\bages\s+((?:\d{1,2}\s*(?:,|and|&)\s*)+\d{1,2}|\d{1,2})\b", low)
    if not match:
        return []
    return [int(item) for item in re.findall(r"\d{1,2}", match.group(1)) if int(item) <= 40]


def _dependent_count(low: str) -> int | None:
    match = re.search(r"\b(one|two|three|four|five|six|\d+)\s+(kids|children|dependents)\b", low)
    if not match:
        match = re.search(r"\b(a|an|one)\s+(kid|child|dependent)\b", low)
        if match:
            return 1
        return None
    token = match.group(1)
    if token.isdigit():
        value = int(token)
    else:
        value = WORD_COUNTS.get(token)
    if value and 1 <= value <= 10:
        return value
    return None


def _money_fields(low: str, result: dict[str, Any]) -> None:
    income = _first_amount(
        low,
        [
            rf"\b(?:make|makes|making|earn|earns|earning|salary(?: of)?|income(?: of)?)\s+(?:around\s+|about\s+|roughly\s+)?{AMOUNT}",
            rf"\b{AMOUNT}\s+(?:a year|per year|salary|income)\b",
        ],
    )
    if income is not None:
        result["updates"]["annual_income"] = income
        result["sources"]["annual_income"] = "user"
        result["heard"].append(f"income {_dollars(income)}")

    mortgage = _first_amount(
        low,
        [
            rf"\b(?:owe|owing|owed)\s+(?:about\s+|around\s+|roughly\s+)?{AMOUNT}\s+(?:on|against)\s+(?:my\s+|our\s+|the\s+)?(?:house|home|mortgage)",
            rf"\b(?:mortgage|house|home)\s+(?:balance\s+)?(?:of\s+|is\s+|around\s+|about\s+)?{AMOUNT}",
            rf"\b{AMOUNT}\s+(?:mortgage|on the house|on our house|on my house)\b",
        ],
    )
    if mortgage is not None:
        result["updates"]["mortgage_balance"] = mortgage
        result["sources"]["mortgage_balance"] = "user"
        result["heard"].append(f"mortgage {_dollars(mortgage)}")
    elif re.search(r"\b(no mortgage|mortgage is paid|house is paid off|don't have a mortgage|do not have a mortgage)\b", low):
        result["updates"]["mortgage_balance"] = 0
        result["sources"]["mortgage_balance"] = "user"

    debt = _first_amount(
        low,
        [
            rf"\b{AMOUNT}\s+(?:in\s+)?(?:other\s+|student\s+|credit[- ]card\s+|car\s+|auto\s+)?debt\b",
            rf"\b(?:other|student|credit[- ]card|car|auto)\s+debt\s+(?:of\s+|is\s+|around\s+)?{AMOUNT}",
        ],
    )
    if debt is not None:
        result["updates"]["other_debt"] = debt
        result["sources"]["other_debt"] = "user"
        result["heard"].append(f"other debt {_dollars(debt)}")
    elif re.search(r"\b(no other debt|debt[- ]free|don't have (?:any )?other debt)\b", low):
        result["updates"]["other_debt"] = 0
        result["sources"]["other_debt"] = "user"

    work = _first_amount(
        low,
        [
            rf"\b{AMOUNT}\s+(?:of\s+)?(?:coverage\s+|life insurance\s+)?(?:through|from|at)\s+work\b",
            rf"\b{AMOUNT}\s+(?:in\s+)?(?:employer|group|work)\s+(?:coverage|insurance|life)\b",
            rf"\bwork\s+(?:gives|provides|gave)\s+(?:me\s+)?(?:about\s+|around\s+)?{AMOUNT}",
        ],
    )
    if work is not None:
        result["updates"]["existing_employer_coverage"] = work
        result["sources"]["existing_employer_coverage"] = "user"
        result["heard"].append(f"work coverage {_dollars(work)}")
    elif re.search(r"\b(no|don't have|do not have)\b.{0,40}\b(work|employer|group)\b.{0,20}\b(coverage|insurance)\b", low):
        result["updates"]["existing_employer_coverage"] = 0
        result["sources"]["existing_employer_coverage"] = "user"

    personal = _first_amount(
        low,
        [
            rf"\b{AMOUNT}\s+(?:of\s+)?(?:personal|individual|private|my own)\s+(?:coverage|insurance|policy|life)\b",
            rf"\b(?:personal|individual|private)\s+(?:coverage|insurance|policy)\s+(?:of\s+|is\s+)?{AMOUNT}",
        ],
    )
    if personal is not None:
        result["updates"]["existing_personal_coverage"] = personal
        result["sources"]["existing_personal_coverage"] = "user"
    elif re.search(r"\b(no|don't have|do not have)\b.{0,30}\b(personal|individual|own)\b.{0,20}\b(coverage|insurance|policy)\b", low):
        result["updates"]["existing_personal_coverage"] = 0
        result["sources"]["existing_personal_coverage"] = "user"

    savings = _first_amount(
        low,
        [
            rf"\b(?:savings|assets)\s+(?:of\s+)?{AMOUNT}\s+(?:earmarked|set aside|for (?:the|my|our) family)",
            rf"\b{AMOUNT}\s+(?:in\s+)?savings\s+(?:earmarked|set aside|for (?:the|my|our) family)",
        ],
    )
    if savings is not None:
        result["updates"]["savings_allocated"] = savings
        result["sources"]["savings_allocated"] = "user"

    legacy = _first_amount(
        low,
        [
            rf"\b(?:legacy|leave|estate goal|lifelong goal)\s+(?:of\s+|about\s+)?{AMOUNT}",
            rf"\b{AMOUNT}\s+(?:legacy|to leave behind)\b",
        ],
    )
    if legacy is not None and re.search(r"\b(legacy|leave|estate|lifelong)\b", low):
        result["updates"]["lifelong_legacy_goal"] = legacy
        result["sources"]["lifelong_legacy_goal"] = "user"

    budget = _first_amount(
        low,
        [
            rf"\b(?:budget|afford|spend)\s+(?:of\s+|about\s+|around\s+)?{AMOUNT}\s+(?:a|per)\s+month",
            rf"\b{AMOUNT}\s+(?:a|per)\s+month\b",
        ],
    )
    if budget is not None and re.search(r"\b(budget|afford|spend|premium|month)\b", low):
        result["updates"]["monthly_budget_preference"] = budget
        result["sources"]["monthly_budget_preference"] = "user"
        result["heard"].append(f"a monthly budget preference of {_dollars(budget)}")


def _education(low: str, result: dict[str, Any]) -> None:
    if not re.search(r"\b(college|university|education|tuition)\b", low):
        if re.search(r"\b(use a placeholder|rough placeholder|estimate is fine|that's fine as an estimate)\b", low):
            result["education_choice"] = "placeholder"
            result["updates"]["include_education"] = True
            result["sources"]["include_education"] = "estimated"
            result["education_is_estimate"] = True
        return
    if re.search(r"\b(not include|don't include|do not include|leave out|without college|no college|skip college|decide not)\b", low):
        result["updates"]["include_education"] = False
        result["sources"]["include_education"] = "user"
        result["clear_education"] = True
        result["heard"].append("education left out")
        return
    amount = _first_amount(
        low,
        [
            rf"\b(?:college|education|tuition)\s+(?:of\s+|around\s+|about\s+|cost(?:s)?\s+)?{AMOUNT}",
            rf"\b{AMOUNT}\s+(?:for|toward|towards)\s+(?:college|education|tuition)\b",
            rf"\b{AMOUNT}\s+per child\b",
        ],
    )
    if amount is not None:
        result["updates"]["include_education"] = True
        result["sources"]["include_education"] = "user"
        result["education_per_child"] = amount
        result["education_is_estimate"] = False
        result["heard"].append(f"education {_dollars(amount)} per child")
        return
    if re.search(r"\b(placeholder|rough estimate|estimate|not sure how much|don't know how much)\b", low):
        result["education_choice"] = "placeholder"
        result["updates"]["include_education"] = True
        result["sources"]["include_education"] = "estimated"
        result["education_is_estimate"] = True
        result["heard"].append("education placeholder")
        return
    result["updates"]["include_education"] = True
    result["sources"]["include_education"] = "user"
    result["education_is_estimate"] = True
    result["education_choice"] = "include_estimate"
    result["heard"].append("education included")


def _years_and_percent(low: str, result: dict[str, Any]) -> None:
    if result["scenario_patch"] and "income_replacement_years" in result["scenario_patch"].get("profile", {}):
        return
    match = re.search(r"\b(\d{1,2})\s+years?\b", low)
    if match and re.search(r"\b(income|salary|replace|support|for my family)\b", low):
        years = int(match.group(1))
        if 1 <= years <= 50:
            result["updates"]["income_replacement_years"] = years
            result["sources"]["income_replacement_years"] = "user"
            result["heard"].append(f"{years} years of income support")
    percent = re.search(r"\b(\d{1,3})\s*(?:%|percent)\b", low)
    if percent and re.search(r"\b(income|salary|replace)\b", low):
        value = int(percent.group(1))
        if 10 <= value <= 100:
            result["updates"]["income_replacement_percent"] = value / 100
            result["sources"]["income_replacement_percent"] = "user"


def _short_answer(cleaned: str, low: str, last_key: str | None, result: dict[str, Any]) -> None:
    if not last_key or result["updates"] or result["dependents_mode"]:
        return
    stripped = low.strip(" .!?")
    if last_key == "age":
        match = re.fullmatch(r"(\d{1,2})", stripped)
        if match and 16 <= int(match.group(1)) <= 90:
            result["updates"]["age"] = int(match.group(1))
            result["sources"]["age"] = "user"
    elif last_key == "partner":
        if re.fullmatch(r"(yes|yeah|yep|married|we are|i am)", stripped):
            result["updates"]["partner"] = True
            result["sources"]["partner"] = "user"
        elif re.fullmatch(r"(no|nope|single|not married)", stripped):
            result["updates"]["partner"] = False
            result["sources"]["partner"] = "user"
    elif last_key == "dependents":
        if stripped in {"no", "none", "no one", "nobody"}:
            result["dependents_mode"] = "clear"
            result["updates"]["dependents_confirmed"] = True
    elif last_key in {
        "annual_income",
        "mortgage_balance",
        "other_debt",
        "existing_employer_coverage",
        "existing_personal_coverage",
        "savings_allocated",
        "lifelong_legacy_goal",
        "other_needs",
    }:
        if stripped in {"no", "none", "zero", "0", "don't have any", "do not have any"}:
            result["updates"][last_key] = 0
            result["sources"][last_key] = "user"
        else:
            amount = _parse_amount(stripped)
            if amount is not None:
                result["updates"][last_key] = amount
                result["sources"][last_key] = "user"
    elif last_key == "income_replacement_years":
        match = re.fullmatch(r"(\d{1,2})(?:\s+years?)?", stripped)
        if match and 1 <= int(match.group(1)) <= 50:
            result["updates"]["income_replacement_years"] = int(match.group(1))
            result["sources"]["income_replacement_years"] = "user"
    elif last_key == "include_education":
        if re.search(r"\b(no|leave it out|leave out|without|don't|not now)\b", stripped):
            result["updates"]["include_education"] = False
            result["sources"]["include_education"] = "user"
            result["clear_education"] = True
        elif re.search(r"\b(placeholder|estimate|rough|not sure|don't know)\b", stripped):
            result["updates"]["include_education"] = True
            result["sources"]["include_education"] = "estimated"
            result["education_is_estimate"] = True
            result["education_choice"] = "placeholder"
        elif re.search(r"\b(yes|yeah|include|please)\b", stripped):
            result["updates"]["include_education"] = True
            result["sources"]["include_education"] = "estimated"
            result["education_is_estimate"] = True
            result["education_choice"] = "placeholder"
        else:
            amount = _parse_amount(stripped)
            if amount is not None:
                result["updates"]["include_education"] = True
                result["sources"]["include_education"] = "user"
                result["education_per_child"] = amount
    elif last_key == "dependent_ages":
        ages = [int(item) for item in re.findall(r"\d{1,2}", stripped) if int(item) <= 40]
        if ages:
            result["dependents"] = [
                {"age": item, "label": f"Child {index + 1}", "education_goal": None, "education_is_estimate": False}
                for index, item in enumerate(ages)
            ]
            result["dependents_mode"] = "fill_ages"


def _first_amount(low: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, low)
        if not match:
            continue
        amount = _parse_amount(match.group(1))
        if amount is not None:
            return amount
    return None


def _parse_amount(token: str) -> float | None:
    raw = token.lower().replace("$", "").replace(",", "").strip()
    raw = raw.replace("thousand", "k").replace("grand", "k")
    raw = raw.replace(" ", "")
    match = re.fullmatch(r"(\d+(?:\.\d+)?)(k|m)?", raw)
    if not match:
        return None
    value = float(match.group(1))
    suffix = match.group(2)
    if suffix == "k":
        value *= 1_000
    elif suffix == "m":
        value *= 1_000_000
    if value < 0 or value > 100_000_000:
        return None
    return value


def _dollars(value: float) -> str:
    return f"${int(round(value)):,}"
