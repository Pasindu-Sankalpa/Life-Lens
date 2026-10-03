"""One source of truth for what the interviewer asks, and why the question is being asked."""

from __future__ import annotations

QUESTIONS: dict[str, dict[str, str]] = {
    "dependents": {
        "prompt": "Who relies on you financially?",
        "why": "If your family wanted to stay housed and supported, the people who rely on you are the reason a plan exists. Children, a partner, or anyone else you support changes how long that lasts.",
        "hint": "For example: “Two kids, ages 3 and 7” or “No one else.”",
    },
    "dependent_ages": {
        "prompt": "How old are they?",
        "why": "Ages show how long each person relies on you. We follow that through age 22, which is what draws the lines on your life map.",
        "hint": "Ages are enough, such as “3 and 7”.",
    },
    "annual_income": {
        "prompt": "About how much do you earn in a year?",
        "why": "Income is how we estimate the support to include in the plan. You choose what share to replace, and for how many years. Both are shown, and both can be changed.",
        "hint": "A rough annual number is fine, such as “$110k”.",
    },
    "mortgage_balance": {
        "prompt": "About how much do you still owe on your home?",
        "why": "If your family wanted to remain in the home, the remaining mortgage is one responsibility a plan can help cover. We use only the amount you enter, and you can leave it out later.",
        "hint": "The current balance, “no mortgage”, or “I’m not sure”.",
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
        "prompt": "If your income stopped, how long would you want your family to have support?",
        "why": "The estimate depends on how long that support should last. If you are not sure, we can start with 10 years and you can see what changes when you pick 3 or 5.",
        "hint": "3 years, 5 years, 10 years, or “I’m not sure”.",
    },
    "age": {
        "prompt": "How old are you?",
        "why": "Age places the mortgage, the children, and any lifelong goal on the same clock. It does not change today’s dollar need by itself.",
        "hint": "Just the number.",
    },
    "partner": {
        "prompt": "Is there a partner in the household?",
        "why": "A partner changes who the plan is for. We do not guess their income. We only note that the household is shared.",
        "hint": "Yes or no is enough.",
    },
    "savings_allocated": {
        "prompt": "Are there savings you want counted against this need?",
        "why": "Money already set aside for the family reduces the gap. We only count savings you say can be used. Everything else stays out.",
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
