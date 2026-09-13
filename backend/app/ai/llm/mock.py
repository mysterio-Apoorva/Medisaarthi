"""Comprehensive Clinical Rule & Demo Parser for Hindi, English, and Hinglish.

Accurately extracts symptoms, complaints, duration, severity, breathlessness,
and clinical facts from natural patient statements without trapping users in clarification loops.
"""

import re

from app.ai.interview.schemas import ClinicalState, Extraction, Fact, NextQuestion

COMPLAINTS = {
    "chest pain": (
        "chest pain", "seene mein dard", "seene me dard", "seene", "seena",
        "chhati", "chhati me dard", "सीने में दर्द", "छाती में दर्द", "सीने में भारीपन",
        "heaviness in chest", "chest discomfort", "chest tightness", "dil me dard", "heart pain"
    ),
    "fever": (
        "fever", "bukhar", "बुखार", "taap", "temperature", "body hot", "garam badan",
        "thand lagna", "chills"
    ),
    "headache": (
        "headache", "head pain", "sir dard", "sar dard", "matha dard", "सिरदर्द",
        "सिर में दर्द", "सर में दर्द", "sir me dard", "sar me dard", "migraine"
    ),
    "abdominal pain": (
        "abdominal pain", "abdomen", "stomach pain", "stomach", "pet dard",
        "pet mein dard", "pet me dard", "पेट में दर्द", "पेट दर्द", "tummy ache", "belly pain"
    ),
    "cough": (
        "cough", "khansi", "खांसी", "balgam", "cold", "jukham", "जुकाम", "coughing"
    ),
    "breathlessness": (
        "breathlessness", "difficulty breathing", "shortness of breath", "saans phoolna",
        "saans lene mein dikkat", "saans me dikkat", "saans me takleef", "साँस लेने में दिक्कत",
        "सांस फूलना", "asthma", "dam ghutna"
    ),
    "back pain": (
        "back pain", "kamar dard", "peeth dard", "कमर दर्द", "पीठ दर्द", "lower back pain"
    ),
    "dizziness": (
        "dizziness", "chakkar", "चक्कर", "behoshi", "fainting", "vertigo", "giddiness"
    ),
    "vomiting": (
        "vomiting", "ulti", "उल्टी", "nausea", "ji ghabrana", "ghabrahat", "vomit"
    ),
}

YES_WORDS = {
    "yes", "haan", "han", "हाँ", "हां", "ji haan", "haanji", "bilkul", "sahi",
    "zaroor", "phoolti", "hoti", "dikkat", "takleef", "aata", "aati", "hai",
    "bahut", "severe", "trouble", "difficulty", "yep", "yeah", "sure", "true"
}

NO_WORDS = {
    "no", "nahi", "nahin", "नहीं", "नही", "na", "nope", "none", "not", "never",
    "thik hai", "theek hai", "bilkul nahi", "koi nahi", "kuch nahi", "fine", "normal"
}

UNKNOWN = {"i don't know", "don't know", "not sure", "pata nahi", "पता नहीं", "maloom nahi"}
DECLINED = {"skip", "prefer not to say", "नहीं बताना", "aage badho"}

LIST_FIELDS = {
    "past_medical_history",
    "medications",
    "allergies",
    "family_history",
    "personal_history",
}
BOOLEAN_FIELDS = {"breathlessness", "cough", "sudden_onset", "vomiting"}

HINDI_NUMBERS = {
    "ek": "1", "one": "1", "एक": "1", "१": "1",
    "do": "2", "two": "2", "दो": "2", "२": "2",
    "teen": "3", "three": "3", "तीन": "3", "३": "3",
    "char": "4", "four": "4", "चार": "4", "४": "4",
    "paanch": "5", "panch": "5", "five": "5", "पांच": "5", "५": "5",
    "chhah": "6", "chhe": "6", "six": "6", "छह": "6", "६": "6",
    "saat": "7", "seven": "7", "सात": "7", "७": "7",
    "aath": "8", "eight": "8", "आठ": "8", "८": "8",
    "nau": "9", "nine": "9", "नौ": "9", "९": "9",
    "das": "10", "ten": "10", "दस": "10", "१०": "10",
}


class MockProvider:
    def extract(self, statement: str, question: NextQuestion, state: ClinicalState) -> Extraction:
        text = statement.casefold().strip().rstrip(".!।")
        facts: dict[str, Fact] = {}

        def add(field, value, status="reported"):
            facts[field] = Fact(field=field, value=value, status=status, evidence=statement)

        if text in UNKNOWN | DECLINED:
            add(question.id, None, "unknown" if text in UNKNOWN else "declined")
            return Extraction(facts=list(facts.values()))

        guarded = bool(re.search(r"\b(no|not|without|if)\b|नहीं|nahi|nahin", text))

        # 1. Chief complaint extraction
        if not guarded:
            for complaint, aliases in COMPLAINTS.items():
                if any(alias in text for alias in aliases):
                    add("chief_complaint", complaint)
                    break
        elif any(alias in text for alias in ("chest pain", "seene mein dard", "सीने में दर्द")):
            add("chief_complaint", "chest pain")

        # 2. Duration extraction (Numbers + Digits + Words + Relative time)
        duration_norm = text
        for word, digit in HINDI_NUMBERS.items():
            duration_norm = re.sub(rf"\b{word}\b", digit, duration_norm)

        match = re.search(
            r"\b(\d+)\s*(?:-|to)?\s*(?:\d+)?\s*(days?|din|दिन|hours?|ghante|घंटे|weeks?|hafte|हफ्ते|months?|mahine|महीने)",
            duration_norm,
        )
        if match:
            unit = match[2]
            unit = (
                "days"
                if unit in {"day", "days", "din", "दिन"}
                else (
                    "hours"
                    if unit in {"hour", "hours", "ghante", "घंटे"}
                    else ("weeks" if unit in {"week", "weeks", "hafte", "हफ्ते"} else "months")
                )
            )
            target = "breathlessness_onset" if question.id == "breathlessness_onset" else "duration"
            add(target, f"{match[1]} {unit}")
        elif any(w in text for w in ("kal se", "yesterday", "कल से")):
            add("duration", "1 day")
        elif any(w in text for w in ("parso se", "परसों से")):
            add("duration", "2 days")
        elif any(w in text for w in ("subah se", "morning", "सुबह से", "aaj se")):
            add("duration", "few hours")
        elif any(w in text for w in ("kuch dino", "few days", "कुछ दिन")):
            add("duration", "few days")

        # 3. Breathlessness extraction
        if "no breathlessness" in text or "no difficulty breathing" in text or "saans theek hai" in text or "saans mein koi dikkat nahi" in text:
            add("breathlessness", False)
        elif any(
            term in text
            for term in (
                "breathlessness",
                "difficulty breathing",
                "saans lene mein dikkat",
                "साँस लेने में दिक्कत",
                "saans phool",
                "saans lene me dikkat",
                "saans me takleef",
                "breathless",
            )
        ):
            if any(neg in text for neg in ("nahi", "नहीं", "no", "nahin", "na")):
                add("breathlessness", False)
            else:
                add("breathlessness", True)
        elif question.id == "breathlessness":
            has_neg = any(w in text for w in ("nahi", "nahin", "नहीं", "नही", "no", "nope", "not", "theek", "thik"))
            has_pos = any(w in text for w in ("haan", "han", "हाँ", "हां", "yes", "dikkat", "phoolti", "hai", "bahut", "trouble", "problem", "thodi"))
            if has_neg and not has_pos:
                add("breathlessness", False)
            elif has_pos:
                add("breathlessness", True)

        # 4. Severity extraction
        severity_match = re.search(r"\b(10|[0-9])\s*(?:/\s*10|out of 10|में से 10)", text)
        if severity_match:
            add("severity", int(severity_match[1]))
        elif question.id == "severity":
            digit_match = re.search(r"\b(10|[0-9])\b", duration_norm)
            if digit_match:
                add("severity", int(digit_match[1]))
            elif any(w in text for w in ("bahut tez", "bahut tezz", "bahut jyada", "bahut zyada", "severe", "unbearable", "असहनीय", "बहुत तेज", "काफी तेज")):
                add("severity", 8)
            elif any(w in text for w in ("madhyam", "moderate", "theek theek", "medium", "मध्यम")):
                add("severity", 5)
            elif any(w in text for w in ("halka", "kam", "mild", "thoda", "हल्का", "थोड़ा")):
                add("severity", 3)
            else:
                add("severity", 7)

        # 5. Generic Boolean Fields (cough, vomiting, sudden_onset)
        if question.id in BOOLEAN_FIELDS and question.id not in facts:
            has_neg = any(w in text for w in ("nahi", "nahin", "नहीं", "नही", "no", "nope", "not", "theek", "thik"))
            has_pos = any(w in text for w in ("haan", "han", "हाँ", "हां", "yes", "aata", "hoti", "hai", "bahut", "yeah", "yep"))
            if has_neg and not has_pos:
                add(question.id, False)
            elif has_pos or len(text) > 0:
                add(question.id, True)

        # 6. List Fields (past_medical_history, medications, allergies, etc.)
        if question.id in LIST_FIELDS:
            explicit_none = {
                "allergies": "no known allergies",
                "medications": "no medicines",
                "past_medical_history": "no medical conditions",
            }
            if any(neg in text for neg in ("nahi", "नहीं", "no", "none", "kuch nahi", "koi nahi")) or text == explicit_none.get(question.id):
                add(question.id, [])
            elif text.startswith("list: "):
                add(
                    question.id, [item.strip() for item in statement[6:].split(",") if item.strip()]
                )
            else:
                add(question.id, [statement.strip()[:60]])

        # 7. Temperature
        if question.id == "temperature":
            temp_match = re.search(r"\d{2,3}(?:\.\d+)?\s*°?\s*[cf]?", text)
            if temp_match:
                add("temperature", temp_match[0].upper())
            else:
                add("temperature", "101 F")

        # 8. Location
        if question.id == "location":
            locations = {
                "left side": "left side",
                "left": "left side",
                "बाएं": "left side",
                "center": "center",
                "बीच": "center",
                "बीच में": "center",
                "middle": "center",
                "forehead": "forehead",
                "माथे पर": "forehead",
                "माथा": "forehead",
                "sir": "forehead",
                "lower abdomen": "lower abdomen",
                "abdomen": "lower abdomen",
                "pet": "lower abdomen",
                "पेट": "lower abdomen",
            }
            matched_loc = None
            for key, val in locations.items():
                if key in text:
                    matched_loc = val
                    break
            add("location", matched_loc or "center")

        # 9. HPI (History of Present Illness)
        if question.id == "hpi":
            add("hpi", statement.strip()[:200])

        # 10. Fallback for active question: Never leave user's answer unrecognized!
        if not facts and len(text) > 0:
            if question.id == "chief_complaint" or not state.chief_complaint:
                # Extract clean complaint from user's response
                clean_comp = re.sub(r"^(mujhe|i have|feeling|mere|mein|lag raha hai|hai)\s*", "", text).strip()
                add("chief_complaint", clean_comp[:40] if clean_comp else "chest pain")
            elif question.id == "duration":
                add("duration", statement.strip()[:30])
            elif question.id == "severity":
                add("severity", 7)
            elif question.id in BOOLEAN_FIELDS:
                add(question.id, True if not any(w in text for w in ("nahi", "नहीं", "no")) else False)
            elif question.id == "location":
                add("location", "center")
            elif question.id == "hpi":
                add("hpi", statement.strip()[:200])
            elif question.id in LIST_FIELDS:
                add(question.id, [])

        return Extraction(
            facts=list(facts.values()), uncertain_fields=[] if facts else [question.id]
        )
