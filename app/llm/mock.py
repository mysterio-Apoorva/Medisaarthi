"""Small, transparent demo parser, NOT a general medical NLP model.

Recognizes documented English/Hindi fixtures and conservative contextual answers.
Everything else requests clarification rather than inventing information.
"""

import re

from app.interview.schemas import ClinicalState, Extraction, Fact, NextQuestion

COMPLAINTS = {
    "chest pain": ("chest pain", "seene mein dard", "सीने में दर्द"),
    "fever": ("fever", "bukhar", "बुखार"),
    "headache": ("headache", "sir dard", "सिरदर्द", "सिर में दर्द"),
    "abdominal pain": ("abdominal pain", "stomach pain", "pet mein dard", "पेट में दर्द"),
}
YES = {"yes", "haan", "han", "हाँ", "हां"}
NO = {"no", "nahi", "nahin", "नहीं", "नही"}
UNKNOWN = {"i don't know", "don't know", "not sure", "pata nahi", "पता नहीं"}
DECLINED = {"skip", "prefer not to say", "नहीं बताना"}
LIST_FIELDS = {
    "past_medical_history",
    "medications",
    "allergies",
    "family_history",
    "personal_history",
}
BOOLEAN_FIELDS = {"breathlessness", "cough", "sudden_onset", "vomiting"}


class MockProvider:
    def extract(self, statement: str, question: NextQuestion, state: ClinicalState) -> Extraction:
        text = statement.casefold().strip().rstrip(".!।")
        facts: dict[str, Fact] = {}

        def add(field, value, status="reported"):
            facts[field] = Fact(field=field, value=value, status=status, evidence=statement)

        if text in UNKNOWN | DECLINED:
            add(question.id, None, "unknown" if text in UNKNOWN else "declined")
            return Extraction(facts=list(facts.values()))

        # Negated or hypothetical complaint mentions should not establish a pathway.
        guarded = re.search(r"\b(no|not|without|if)\b|नहीं|nahi", text)
        if not guarded:
            for complaint, aliases in COMPLAINTS.items():
                if any(alias in text for alias in aliases):
                    add("chief_complaint", complaint)
                    break

        duration_text = text.replace("teen", "3").replace("तीन", "3").replace("३", "3")
        match = re.search(r"\b(\d+)\s*(days?|din|दिन|hours?|ghante|घंटे|weeks?)", duration_text)
        if match:
            unit = match[2]
            unit = (
                "days"
                if unit in {"day", "days", "din", "दिन"}
                else ("hours" if unit in {"hour", "hours", "ghante", "घंटे"} else "weeks")
            )
            target = "breathlessness_onset" if question.id == "breathlessness_onset" else "duration"
            add(target, f"{match[1]} {unit}")

        if "no breathlessness" in text or "no difficulty breathing" in text:
            add("breathlessness", False)
        elif not guarded and any(
            term in text
            for term in (
                "breathlessness",
                "difficulty breathing",
                "saans lene mein dikkat",
                "साँस लेने में दिक्कत",
            )
        ):
            add("breathlessness", True)

        severity = re.search(r"\b(10|[0-9])\s*(?:/\s*10|out of 10)", text)
        if severity:
            add("severity", int(severity[1]))
        elif question.id == "severity" and re.fullmatch(r"10|[0-9]", text):
            add("severity", int(text))

        if question.id in BOOLEAN_FIELDS and text in YES | NO:
            add(question.id, text in YES)
        if question.id in LIST_FIELDS:
            explicit_none = {
                "allergies": "no known allergies",
                "medications": "no medicines",
                "past_medical_history": "no medical conditions",
            }
            if text in NO | {"none"} or text == explicit_none.get(question.id):
                add(question.id, [])
            elif text.startswith("list: "):
                add(
                    question.id, [item.strip() for item in statement[6:].split(",") if item.strip()]
                )
        if question.id == "temperature" and re.fullmatch(r"\d{2,3}(?:\.\d+)?\s*°?\s*[cf]", text):
            add("temperature", text.upper())
        if question.id == "location":
            locations = {
                "left side": "left side",
                "center": "center",
                "forehead": "forehead",
                "lower abdomen": "lower abdomen",
                "माथे पर": "forehead",
            }
            if text in locations:
                add("location", locations[text])
        if question.id == "hpi" and text in {
            "it started gradually and comes and goes",
            "it has stayed the same",
        }:
            add("hpi", text)
        return Extraction(
            facts=list(facts.values()), uncertain_fields=[] if facts else [question.id]
        )
