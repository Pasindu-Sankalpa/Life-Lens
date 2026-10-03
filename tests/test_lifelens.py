"""The coverage engine and the interview must agree, with no model in the loop."""

from __future__ import annotations

import os
import tempfile
import unittest

os.environ["LIFELENS_DB"] = "sqlite:///" + tempfile.mkstemp(suffix=".db")[1]
os.environ["LIFELENS_LLM_BASE_URL"] = "http://127.0.0.1:9"

from fastapi.testclient import TestClient

from app.engine.coverage import DependentIn, Inputs, calculate, life_event_patch
from app.engine.parse import extract_message
from app.main import app


DEMO = (
    "I'm 35, married, have two kids aged 3 and 7, make $100k, owe $320k on my house, "
    "have $25k other debt, $150k coverage through work, and I'd like to help pay for college."
)


class EngineTests(unittest.TestCase):
    def test_demo_sentence_and_gap(self) -> None:
        parsed = extract_message(DEMO)
        self.assertEqual(parsed["updates"]["age"], 35)
        self.assertTrue(parsed["updates"]["partner"])
        self.assertEqual(parsed["updates"]["annual_income"], 100_000)
        self.assertEqual(parsed["updates"]["mortgage_balance"], 320_000)
        self.assertEqual(parsed["updates"]["other_debt"], 25_000)
        self.assertEqual(parsed["updates"]["existing_employer_coverage"], 150_000)
        self.assertTrue(parsed["updates"]["include_education"])
        self.assertEqual([item["age"] for item in parsed["dependents"]], [3, 7])

        result = calculate(
            Inputs(
                age=35,
                partner=True,
                annual_income=100_000,
                mortgage_balance=320_000,
                other_debt=25_000,
                existing_employer_coverage=150_000,
                include_education=True,
                dependents_confirmed=True,
                dependents=[
                    DependentIn(age=3, label="Child 1"),
                    DependentIn(age=7, label="Child 2"),
                ],
                sources={
                    "annual_income": "user",
                    "mortgage_balance": "user",
                    "other_debt": "user",
                    "existing_employer_coverage": "user",
                    "include_education": "user",
                },
            )
        )
        self.assertEqual(result["components"][0]["amount"], 700_000)
        self.assertEqual(result["gross_need"], 1_245_000)
        self.assertEqual(result["gap"], 1_095_000)
        self.assertEqual(sum(item["amount"] for item in result["gap_allocation"]), result["gap"])
        self.assertGreater(result["timeline"]["points"][0]["need"], result["timeline"]["points"][20]["need"])
        self.assertEqual(result["need_profile"]["headline"], "Your need is mostly time-bound")
        self.assertTrue(result["comparison"]["term"]["points"])
        self.assertTrue(result["comparison"]["permanent"]["points"])
        self.assertTrue(result["stress_samples"])
        self.assertTrue(result["professional_questions"])

    def test_what_ifs(self) -> None:
        five = extract_message("What if I only want to replace my salary for 5 years?")
        self.assertEqual(five["scenario_patch"]["profile"]["income_replacement_years"], 5)
        gone = extract_message("What if my employer coverage disappears?")
        self.assertEqual(gone["scenario_patch"]["profile"]["existing_employer_coverage"], 0)
        self.assertIsNone(gone["life_event"])
        college = extract_message("What if we decide not to include college?")
        self.assertTrue(college["scenario_patch"]["clear_education"])
        paid = extract_message("What if my mortgage was already paid off?")
        self.assertEqual(paid["scenario_patch"]["profile"]["mortgage_balance"], 0)

    def test_messy_sentence_and_events(self) -> None:
        parsed = extract_message(
            "I'm 38, married, two kids, make about 95 grand and we owe around 280k on the house. I think work gives me 100k."
        )
        self.assertEqual(parsed["updates"]["annual_income"], 95_000)
        self.assertEqual(parsed["updates"]["mortgage_balance"], 280_000)
        self.assertEqual(parsed["updates"]["existing_employer_coverage"], 100_000)
        self.assertEqual(len(parsed["dependents"]), 2)
        event = life_event_patch(
            "another_child",
            Inputs(include_education=True, annual_income=100_000, dependents_confirmed=True, dependents=[DependentIn(age=4)]),
        )
        self.assertEqual(event["patch"]["add_dependents"][0]["age"], 0)

    def test_guided_short_answers(self) -> None:
        self.assertEqual(extract_message("35", "age")["updates"]["age"], 35)
        self.assertEqual(extract_message("$110k", "annual_income")["updates"]["annual_income"], 110_000)
        self.assertEqual(extract_message("none", "mortgage_balance")["updates"]["mortgage_balance"], 0)
        unknown = extract_message("I don't know", "include_education")
        self.assertEqual(unknown["education_choice"], "unknown")


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_full_story(self) -> None:
        created = self.client.post("/api/sessions", json={"mode": "quick"})
        self.assertEqual(created.status_code, 200)
        session_id = created.json()["session"]["id"]
        turned = self.client.post(f"/api/sessions/{session_id}/messages", json={"content": DEMO})
        self.assertEqual(turned.status_code, 200)
        body = turned.json()
        self.assertEqual(body["calculation"]["gap"], 1_095_000)
        self.assertEqual(body["profile"]["annual_income"], 100_000)
        self.assertEqual(len(body["profile"]["dependents"]), 2)
        self.assertTrue(any(tool["name"] == "calculate_coverage_need" for tool in body["messages"][-1]["payload"]["tools"]))

        what_if = self.client.post(
            f"/api/sessions/{session_id}/messages",
            json={"content": "What if I only want to replace my salary for 5 years?"},
        )
        preview = what_if.json()
        self.assertEqual(preview["base_calculation"]["gap"], 1_095_000)
        self.assertEqual(preview["calculation"]["gap"], 745_000)
        self.assertIsNotNone(preview["active_scenario"])

        kept = self.client.post(f"/api/sessions/{session_id}/scenarios/{preview['active_scenario']['id']}/apply")
        self.assertEqual(kept.json()["calculation"]["gap"], 745_000)
        self.assertIsNone(kept.json()["active_scenario"])

        event = self.client.post(f"/api/sessions/{session_id}/events", json={"event": "change_jobs"})
        self.assertGreater(event.json()["calculation"]["gap"], 745_000)

        stress = self.client.post(f"/api/sessions/{session_id}/stress", json={"coverage": 500000})
        self.assertEqual(stress.status_code, 200)
        self.assertIsNotNone(stress.json()["sample"])
        timeline = self.client.get(f"/api/sessions/{session_id}/timeline", params={"year_offset": 0})
        self.assertEqual(timeline.status_code, 200)
        compare = self.client.get(f"/api/sessions/{session_id}/compare")
        self.assertIn("term", compare.json())
        summary = self.client.get(f"/api/sessions/{session_id}/summary")
        self.assertIn("professional_questions", summary.json())
        knowledge = self.client.get("/api/knowledge", params={"q": "what is term life versus whole life"})
        self.assertGreaterEqual(len(knowledge.json()["notes"]), 1)

        edited = self.client.patch(
            f"/api/sessions/{session_id}/profile",
            json={"income_replacement_years": 10, "existing_personal_coverage": 0, "lifelong_legacy_goal": 0},
        )
        self.assertEqual(edited.status_code, 200)
        health = self.client.get("/api/health")
        self.assertTrue(health.json()["ok"])
        self.assertFalse(health.json()["llm"]["reachable"])


if __name__ == "__main__":
    unittest.main()
