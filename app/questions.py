"""One source of truth for what the interviewer asks, and why the question is being asked."""

from __future__ import annotations

QUESTIONS: dict[str, dict[str, str]] = {
    "dependents": {
        "prompt": "Who depends on your income?",
        "why": "People who rely on your income are the reason a protection period exists. Children, a partner, or anyone else you support changes how long that period lasts.",
        "hint": "For example: “Two kids, ages 3 and 7” or “No one else depends on me.”",
    },
    "dependent_ages": {
        "prompt": "How old are the people who depend on you?",
        "why": "Ages turn “I have kids” into a timeline. Dependency and education windows are counted to age 22, and only if you tell us the ages.",
        "hint": "Ages are enough: “3 and 7”.",
    },
    "annual_income": {
        "prompt": "What income would your household lose?",
        "why": "We use income to estimate financial support the household could lose. The engine multiplies it by a replacement percent and a number of years — both visible, both changeable.",
        "hint": "A rough annual number is fine.",
    },
    "mortgage_balance": {
        "prompt": "How much remains on your mortgage?",
        "why": "A mortgage is an obligation the household may need to keep paying. Including the balance estimates how much coverage could allow them to remain in the home. Say zero if there isn’t one.",
        "hint": "The current balance, or “no mortgage”.",
    },
    "other_debt": {
        "prompt": "Is there other debt — student loans, a car, cards?",
        "why": "Other debt is a separate obligation from the mortgage. Leaving it out makes the gap look smaller than the household’s actual liabilities.",
        "hint": "A total is enough, or “none”.",
    },
    "existing_employer_coverage": {
        "prompt": "Do you already have life insurance through work?",
        "why": "Existing insurance may already cover part of the need, so we don’t want to double-count it. Work coverage is kept separate because it may not continue if you leave the job.",
        "hint": "The face amount, or “none”.",
    },
    "existing_personal_coverage": {
        "prompt": "Do you have any personal life insurance, separate from work?",
        "why": "Personal coverage is counted alongside work coverage. Keeping them separate matters, because one of them may not follow you if you change jobs.",
        "hint": "The face amount, or “none”.",
    },
    "include_education": {
        "prompt": "Should this plan help with education?",
        "why": "Education is a future cost with an end date. It belongs in the picture only if you want it there. If you don’t know the cost, we can leave it out or mark a placeholder you can replace.",
        "hint": "Yes, no, a dollar amount, or “use a placeholder”.",
    },
    "income_replacement_years": {
        "prompt": "How many years of income support do you want the plan to cover?",
        "why": "A lump-sum need depends on how long the household should be able to replace income. Ten years is only a starting assumption until you choose a length.",
        "hint": "For example: “7 years” or “until the youngest is 22”.",
    },
    "age": {
        "prompt": "How old are you?",
        "why": "Age places the mortgage, the children, and any lifelong goal on the same clock. It does not change today’s dollar need by itself.",
        "hint": "Just the number.",
    },
    "partner": {
        "prompt": "Is there a partner in the household?",
        "why": "A partner changes who the plan is for. This tool does not guess their income; it only records that the household is shared.",
        "hint": "Yes or no is enough.",
    },
    "savings_allocated": {
        "prompt": "Are there savings you want counted against this need?",
        "why": "Money already set aside for the family reduces the gap. We only subtract savings you earmark. Everything else stays out of the formula.",
        "hint": "An amount, or “don’t count any”.",
    },
    "lifelong_legacy_goal": {
        "prompt": "Is any part of this a lifelong goal, rather than something that ends?",
        "why": "A legacy or estate amount does not expire when the mortgage or the kids’ dependency ends. That is what makes permanent coverage a relevant comparison. Zero is a complete answer.",
        "hint": "An amount, or “no lifelong goal”.",
    },
}


def questions_for(keys: list[str]) -> list[dict[str, str]]:
    found = []
    for key in keys:
        item = QUESTIONS.get(key)
        if not item:
            continue
        found.append({"key": key, **item})
    return found
