"""Lincoln-grounded educational notes.

These are original summaries for retrieval. They are not quotations from
Lincoln Financial's site. Each note points at a public page so a reviewer
can check the underlying material.
"""

from __future__ import annotations

import math
import re
from typing import Any

KNOWLEDGE_VERSION = "2026-10-03.2"

CHUNKS: list[dict[str, str]] = [
    {
        "slug": "term-overview",
        "topic": "term",
        "title": "What term coverage is for",
        "source_name": "Lincoln Financial public life insurance pages",
        "source_url": "https://www.lincolnfinancial.com/public/individuals/products/lifeinsurance/termlife",
        "content": (
            "Term life insurance is coverage for a stated period. Lincoln's public term materials describe level-premium "
            "periods, including 10, 15, 20, and 30 years, with a death benefit designed for needs that have an end date. "
            "Those needs often include a mortgage and the years a family is raising children or paying for education. "
            "The premium for a level-premium period is generally fixed during that period, and the initial cost is generally "
            "lower than permanent coverage with a similar death benefit. Term coverage does not build cash value."
        ),
    },
    {
        "slug": "term-fit",
        "topic": "term",
        "title": "Matching a term period to a timeline",
        "source_name": "Lincoln Financial public life insurance pages",
        "source_url": "https://www.lincolnfinancial.com/public/individuals/products/lifeinsurance/termlife",
        "content": (
            "A term period is a planning choice, not a formula output. A 20-year period lines up with a need that ends "
            "inside 20 years, such as a mortgage amortization or the years until a child becomes independent. A 30-year "
            "period is the longer common level-premium option on Lincoln's public term pages. If a goal is meant to last "
            "past those periods, term coverage alone does not carry it. Employer-provided term coverage may also stop "
            "when employment stops, so it is not automatically a substitute for personally owned coverage."
        ),
    },
    {
        "slug": "permanent-overview",
        "topic": "permanent",
        "title": "What permanent coverage is for",
        "source_name": "Lincoln Financial public permanent life pages",
        "source_url": "https://www.lincolnfinancial.com/public/individuals/products/lifeinsurance/permanentlife",
        "content": (
            "Permanent life insurance is built for a longer duration than a term period, including lifetime protection "
            "potential. Lincoln's public permanent materials discuss cash-value potential, flexibility, and the possibility "
            "of living-benefit riders. Those features come with qualifications: costs, investment risk on some designs, "
            "the effect of withdrawals and loans, and the risk that a policy can lapse if it is not funded as required. "
            "LincolnLens does not illustrate cash value, loans, or riders."
        ),
    },
    {
        "slug": "whole-life",
        "topic": "whole",
        "title": "Whole life is an educational comparison",
        "source_name": "Lincoln Financial",
        "source_url": "https://www.lincolnfinancial.com/public/individuals/products/lifeinsurance/permanentlife",
        "retrieved_at": "2026-10-03",
        "topics": "whole,permanent",
        "content": (
            "Whole life is one form of permanent insurance: a death benefit designed to last for a lifetime, often with a "
            "fixed premium schedule and a cash-value component. It is generally more expensive in the early years than term "
            "coverage of the same face amount. Lincoln's current public permanent-life materials describe indexed universal "
            "life and variable universal life. They do not present a whole-life policy. Use whole life only as an educational "
            "comparison. Use Lincoln's term and permanent categories when handing off to a professional. Cash value, guarantees, "
            "and charges are contract-specific and are not calculated here."
        ),
    },
    {
        "slug": "iul-vul",
        "topic": "permanent",
        "title": "Indexed and variable universal life, at a distance",
        "source_name": "Lincoln Financial public permanent life pages",
        "source_url": "https://www.lincolnfinancial.com/public/individuals/products/lifeinsurance/permanentlife",
        "content": (
            "Indexed universal life and variable universal life are permanent designs that add flexibility and a cash-value "
            "account whose value can change. Indexed designs credit interest using a reference to a market index, within "
            "limits described in the contract, and do not invest the cash value directly in the market. Variable designs "
            "can invest in underlying options and can lose value. Both involve charges. Withdrawals, loans, and skipped "
            "premiums can increase the chance a policy lapses. None of those mechanics are projected in LincolnLens."
        ),
    },
    {
        "slug": "cash-value-caution",
        "topic": "cash-value",
        "title": "Cash value is not a coverage-gap input",
        "source_name": "Lincoln Financial public permanent life pages",
        "source_url": "https://www.lincolnfinancial.com/public/individuals/products/lifeinsurance/permanentlife",
        "content": (
            "Cash value is a feature of many permanent policies. It is not the same thing as the death benefit, and it is "
            "not an input to the protection-gap formula. Accessing cash value can reduce the death benefit and can have "
            "tax consequences that this tool does not determine. A person who cares about cash value is describing a "
            "different priority from pure income replacement, and that priority should be discussed with a financial "
            "professional before any product is considered."
        ),
    },
    {
        "slug": "affordability",
        "topic": "affordability",
        "title": "Affordability is a priority conversation",
        "source_name": "LincolnLens planning note",
        "source_url": "https://www.lincolnfinancial.com/public/individuals/products/lifeinsurance",
        "content": (
            "A calculated gap is not a bill and not a face amount someone must buy. If the full gap is more than the "
            "household wants to insure, the useful question is which obligations stay covered at a smaller amount: the "
            "mortgage, other debt, a shorter income runway, or education. LincolnLens shows that tradeoff in the stress test. "
            "It does not estimate premiums, underwriting class, or what a household can afford."
        ),
    },
    {
        "slug": "employer-coverage",
        "topic": "existing-coverage",
        "title": "Work coverage and personal coverage are not interchangeable",
        "source_name": "LincolnLens planning note",
        "source_url": "https://www.lincolnfinancial.com/public/individuals/products/lifeinsurance",
        "content": (
            "Group life insurance through an employer can be a real part of today's protection. It may also be tied to "
            "the job. Counting it toward a 20-year family timeline assumes it will still be there, which may be wrong "
            "after a job change. Personal coverage is owned by the individual. LincolnLens subtracts both when the person "
            "reports them, and it asks a professional question about portability rather than assuming the work amount lasts."
        ),
    },
    {
        "slug": "not-advice",
        "topic": "handoff",
        "title": "What this tool will not do",
        "source_name": "Lincoln Financial public getting-started page",
        "source_url": "https://www.lincolnfinancial.com/public/individuals/products/lifeinsurance/readytogetstarted",
        "content": (
            "LincolnLens is an educational needs analysis. It does not underwrite, quote a premium, recommend a Lincoln "
            "product, predict health risk, or give tax or legal advice. Lincoln's public pages direct people who are "
            "ready to act toward a financial professional. The handoff in this product is a one-page summary of the "
            "person's own timeline and a short list of questions, not an application."
        ),
    },
    {
        "slug": "needs-math",
        "topic": "method",
        "title": "How the protection gap is worked out",
        "source_name": "LincolnLens",
        "source_url": "https://www.lincolnfinancial.com/public/individuals/products/lifeinsurance",
        "content": (
            "The gap equals income replacement plus mortgage payoff plus other debt plus education goals plus any other "
            "named need plus a lifelong legacy amount, minus work coverage, personal coverage, and savings the person "
            "earmarked. Income replacement equals annual income times a replacement percent times a number of years. "
            "No inflation rate and no discount rate are applied. Ten years and 70 percent are assumptions until the "
            "person replaces them. Education uses an amount the person enters, or a labeled placeholder of $100,000 per "
            "child. The dollar figures always come from those steps, not from a guess."
        ),
    },
]


def keyword_search(query: str, chunks: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    tokens = set(_tokens(query))
    if not tokens:
        return chunks[:limit]
    scored = []
    for chunk in chunks:
        body = _tokens(f"{chunk['title']} {chunk['topic']} {chunk['content']}")
        overlap = len(tokens & body)
        if overlap:
            scored.append((overlap, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:limit]] or chunks[:1]


def _tokens(text: str) -> set[str]:
    stop = {"the", "and", "for", "with", "that", "this", "from", "your", "what", "how", "does", "are"}
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2 and token not in stop}


class Embedder:
    """CPU embeddings over the local bge model. Optional: keyword search still works."""

    def __init__(self) -> None:
        self._model = None
        self._tokenizer = None
        self.ready = False
        self.error: str | None = None

    def load(self) -> None:
        if self.ready or self.error:
            return
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer

            name = "BAAI/bge-base-en-v1.5"
            self._tokenizer = AutoTokenizer.from_pretrained(name, local_files_only=True)
            self._model = AutoModel.from_pretrained(name, local_files_only=True)
            self._model.eval()
            self._torch = torch
            self.ready = True
        except Exception as exc:  # noqa: BLE001 — embeddings are optional
            self.error = str(exc)

    def embed(self, texts: list[str], query: bool = False) -> list[list[float]] | None:
        self.load()
        if not self.ready or self._model is None or self._tokenizer is None:
            return None
        prepared = [f"Represent this sentence for searching relevant passages: {text}" if query else text for text in texts]
        batch = self._tokenizer(prepared, padding=True, truncation=True, max_length=512, return_tensors="pt")
        with self._torch.no_grad():
            output = self._model(**batch)
            vectors = output.last_hidden_state[:, 0]
            vectors = self._torch.nn.functional.normalize(vectors, p=2, dim=1)
        return vectors.tolist()


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def semantic_search(query: str, chunks: list[dict[str, Any]], embedder: Embedder, limit: int = 3) -> list[dict[str, Any]]:
    if not chunks:
        return []
    missing = [chunk for chunk in chunks if not chunk.get("embedding")]
    if missing:
        vectors = embedder.embed([chunk["content"] for chunk in missing])
        if vectors:
            for chunk, vector in zip(missing, vectors):
                chunk["embedding"] = vector
    query_vector = embedder.embed([query], query=True) if embedder.ready else None
    if not query_vector:
        return keyword_search(query, chunks, limit)
    ranked = []
    for chunk in chunks:
        embedding = chunk.get("embedding")
        if not embedding:
            continue
        ranked.append((cosine(query_vector[0], embedding), chunk))
    if not ranked:
        return keyword_search(query, chunks, limit)
    ranked.sort(key=lambda item: item[0], reverse=True)
    top = [item[1] for item in ranked[:limit] if item[0] > 0.25]
    return top or keyword_search(query, chunks, limit)


def blend_score_is_finite(value: float) -> bool:
    return math.isfinite(value)
