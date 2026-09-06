"""Run with python -m examples.demo; never requires an API key."""

import json
from pathlib import Path

from app.interview.engine import InterviewEngine
from app.interview.schemas import Patient
from app.llm.mock import MockProvider

SCENARIOS = {
    "fever": "Mujhe 3 din se fever hai.",
    "chest_pain": "Mujhe teen din se seene mein dard ho raha hai. I have breathlessness, 7/10.",
    "headache": "मुझे तीन दिन से सिरदर्द है।",
    "abdominal_pain": "I have abdominal pain for 2 days, 5/10.",
}
ANSWERS = {
    "duration": "3 days",
    "severity": "5",
    "location": "forehead",
    "temperature": "38 C",
    "breathlessness": "no",
    "breathlessness_onset": "2 hours",
    "cough": "no",
    "sudden_onset": "no",
    "vomiting": "no",
    "hpi": "it started gradually and comes and goes",
    "past_medical_history": "none",
    "medications": "none",
    "allergies": "not sure",
    "family_history": "none",
    "personal_history": "skip",
}


def run_demo() -> dict:
    engine = InterviewEngine(MockProvider())
    results = {}
    for index, (name, opening) in enumerate(SCENARIOS.items(), start=1):
        record = engine.start(Patient(patient_id=f"DEMO{index}", language="hi"), consent=True)
        record = engine.respond(record, opening)
        first_response = engine.present(record).model_dump(mode="json")
        while not record.completed:
            question = engine.present(record).next_question
            answer = ANSWERS[question.id]
            if question.id == "location" and name != "headache":
                answer = "center" if name == "chest_pain" else "lower abdomen"
            record = engine.respond(record, answer)
        results[name] = {
            "first_response": first_response,
            "final_record": record.model_dump(mode="json"),
            "final_response": engine.present(record).model_dump(mode="json"),
        }
    return results


if __name__ == "__main__":
    result = run_demo()
    Path("examples/demo-output.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for name, data in result.items():
        first = data["first_response"]
        print(
            f"{name}: complaint={first['clinical_state']['chief_complaint']}; "
            f"duration={first['clinical_state']['duration']}; "
            f"next={first['next_question']['id']}; completed={data['final_record']['completed']}"
        )
    print("Full evidence and output saved to examples/demo-output.json")
