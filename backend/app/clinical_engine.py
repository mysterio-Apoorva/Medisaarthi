"""Deterministic clinical backbone. It never diagnoses and never invents facts."""

from __future__ import annotations

import re
import json
from functools import lru_cache
from dataclasses import dataclass
from typing import Any, Iterable, Literal


STAGES = (
    "INITIAL", "CHIEF_COMPLAINT", "HPI", "ASSOCIATED_SYMPTOMS", "RED_FLAG_SCREEN",
    "PAST_HISTORY", "SURGICAL_HISTORY", "MEDICATIONS", "ALLERGIES", "FAMILY_HISTORY",
    "SOCIAL_HISTORY", "PERSONAL_HISTORY", "REVIEW_OF_SYSTEMS", "DOCUMENT_REVIEW",
    "RECONCILIATION", "COMPLETENESS_CHECK", "PATIENT_REVIEW", "CONSENT", "FINALIZED",
)

ONTOLOGY: dict[str, dict[str, Any]] = {
    "chest pain": {
        "synonyms": ("chest pain", "chest tightness", "chest pressure", "chest discomfort", "seene mein dard", "seene me dard", "chhati mein dard", "chhati me dard"),
        "body_system": "cardiovascular", "required": ("duration", "location", "severity", "character", "radiation", "exertion", "breathlessness", "sweating", "nausea"),
    },
    "headache": {"synonyms": ("headache", "head pain", "sir dard", "sar dard", "migraine"), "body_system": "neurological", "required": ("onset", "duration", "severity", "location", "sudden_onset", "vomiting")},
    "fever": {"synonyms": ("fever", "bukhar", "high temperature", "chills"), "body_system": "infectious", "required": ("duration", "temperature", "cough", "vomiting")},
    "cough": {"synonyms": ("cough", "khansi", "coughing"), "body_system": "respiratory", "required": ("duration", "breathlessness", "fever")},
    "abdominal pain": {"synonyms": ("abdominal pain", "stomach pain", "belly pain", "tummy ache", "pet dard"), "body_system": "gastrointestinal", "required": ("onset", "duration", "severity", "location", "vomiting", "fever")},
    "vomiting": {"synonyms": ("vomiting", "vomit", "ulti", "nausea"), "body_system": "gastrointestinal", "required": ("onset", "frequency", "abdominal_pain", "fever")},
    "diarrhea": {"synonyms": ("diarrhea", "loose motion", "dysentery", "dast"), "body_system": "gastrointestinal", "required": ("onset", "frequency", "vomiting", "fever")},
    "breathlessness": {"synonyms": ("breathlessness", "shortness of breath", "difficulty breathing", "saans phool", "saans lene mein dikkat", "saans lene me dikkat"), "body_system": "respiratory", "required": ("onset", "severity", "chest_pain", "cough")},
    "dizziness": {"synonyms": ("dizziness", "vertigo", "chakkar", "fainting"), "body_system": "neurological", "required": ("onset", "duration", "fainting", "chest_pain")},
    "fatigue": {"synonyms": ("fatigue", "tiredness", "weakness", "thakan"), "body_system": "general", "required": ("onset", "duration", "fever", "breathlessness")},
}

COMMON_FIELDS = ("past_medical_history", "past_surgical_history", "medications", "allergies", "family_history", "social_history", "personal_history", "review_of_systems")

# Multilingual aliases are terminology, not fabricated patient facts.
for _concept, _aliases in {
    'chest pain':('सीने में दर्द','छाती में दर्द'), 'headache':('सिर दर्द','सिर में दर्द'),
    'fever':('बुखार',), 'cough':('खांसी','खाँसी'), 'abdominal pain':('पेट दर्द','पेट में दर्द'),
    'vomiting':('उल्टी',), 'diarrhea':('दस्त',), 'breathlessness':('साँस फूल','सांस फूल','सांस लेने में दिक्कत'),
    'dizziness':('चक्कर',), 'fatigue':('थकान','कमजोरी'),
}.items():
    ONTOLOGY[_concept]['synonyms'] += _aliases
FIELD_STAGE = {
    "chief_complaint": "CHIEF_COMPLAINT", "duration": "HPI", "onset": "HPI", "severity": "HPI",
    "location": "HPI", "character": "HPI", "radiation": "HPI", "exertion": "HPI", "frequency": "HPI",
    "breathlessness": "ASSOCIATED_SYMPTOMS", "sweating": "ASSOCIATED_SYMPTOMS", "nausea": "ASSOCIATED_SYMPTOMS",
    "vomiting": "ASSOCIATED_SYMPTOMS", "cough": "ASSOCIATED_SYMPTOMS", "fever": "ASSOCIATED_SYMPTOMS",
    "sudden_onset": "RED_FLAG_SCREEN", "chest_pain": "RED_FLAG_SCREEN", "abdominal_pain": "RED_FLAG_SCREEN", "fainting": "RED_FLAG_SCREEN",
    "past_medical_history": "PAST_HISTORY", "medications": "MEDICATIONS", "allergies": "ALLERGIES",
}

QUESTIONS = {
    "chief_complaint": ("What is bothering you today? Please describe it in your own words.", "आज आपको किस तकलीफ़ के लिए मदद चाहिए? अपने शब्दों में बताइए।"),
    "duration": ("How long has this been happening?", "यह तकलीफ़ कब से है?"),
    "onset": ("When did it start, and was the start sudden or gradual?", "यह कब शुरू हुआ और अचानक हुआ या धीरे-धीरे?"),
    "severity": ("On a scale from 0 to 10, how severe is it right now?", "अभी यह 0 से 10 में कितना तेज़ है?"),
    "location": ("Where exactly do you feel it?", "यह ठीक कहाँ महसूस हो रहा है?"),
    "character": ("How would you describe the feeling: pressure, burning, sharp, or something else?", "दर्द कैसा है—दबाव, जलन, चुभन, या कुछ और?"),
    "radiation": ("Does the discomfort move to your arm, jaw, back, or elsewhere?", "क्या तकलीफ़ हाथ, जबड़े, पीठ या कहीं और फैलती है?"),
    "exertion": ("Does walking or exertion make it worse or better?", "चलने या मेहनत करने से यह बढ़ता या कम होता है?"),
    "breathlessness": ("Are you having trouble breathing or feeling short of breath?", "क्या साँस लेने में तकलीफ़ या साँस फूल रही है?"),
    "sweating": ("Have you noticed unusual sweating with this problem?", "क्या इस तकलीफ़ के साथ असामान्य पसीना आ रहा है?"),
    "nausea": ("Do you feel nauseated or have you vomited?", "क्या मितली या उल्टी हो रही है?"),
    "sudden_onset": ("Did this start suddenly, reaching maximum intensity quickly?", "क्या यह अचानक शुरू हुआ और जल्दी बहुत तेज़ हो गया?"),
    "temperature": ("Have you measured your temperature? If yes, what was it?", "क्या आपने तापमान नापा है? अगर हाँ, कितना था?"),
    "cough": ("Do you have a cough?", "क्या आपको खाँसी है?"),
    "vomiting": ("Have you been vomiting?", "क्या उल्टी हो रही है?"),
    "fever": ("Do you currently have fever or chills?", "क्या अभी बुखार या ठंड लग रही है?"),
    "frequency": ("How often has this happened today?", "आज यह कितनी बार हुआ है?"),
    "past_medical_history": ("Do you have any long-term health conditions, such as diabetes, high blood pressure, heart disease, asthma, or none?", "क्या आपको मधुमेह, बीपी, दिल की बीमारी, अस्थमा या कोई पुरानी बीमारी है? नहीं है तो बताइए।"),
    "medications": ("Do you take any regular medicines? Please name them, or say none.", "क्या आप कोई नियमित दवा लेते हैं? नाम बताइए, या 'कोई नहीं' कहें।"),
    "allergies": ("Are you allergic to any medicine, food, or substance? Please name it, or say no known allergies.", "क्या आपको किसी दवा, भोजन या चीज़ से एलर्जी है? नाम बताइए, या 'कोई ज्ञात एलर्जी नहीं' कहें।"),
}

BOOL_FIELDS = {"breathlessness", "sweating", "nausea", "sudden_onset", "cough", "vomiting", "fever", "chest_pain", "abdominal_pain", "fainting"}
LIST_FIELDS = {"past_medical_history", "medications", "allergies"}
LIST_FIELDS.update({'past_surgical_history','family_history','social_history','personal_history','review_of_systems'})
QUESTIONS.update({
    'past_surgical_history':('Have you had any operations or hospital stays? Say none if not.', 'क्या कोई ऑपरेशन हुआ है या अस्पताल में भर्ती हुए हैं? नहीं तो बताइए।'),
    'family_history':('Are there important health conditions in your close family?', 'क्या आपके निकट परिवार में कोई महत्वपूर्ण बीमारी है?'),
    'social_history':('Do you use tobacco or alcohol, and what work do you do?', 'क्या आप तंबाकू या शराब लेते हैं, और क्या काम करते हैं?'),
    'personal_history':('Have your sleep, appetite, or usual daily activities changed?', 'क्या नींद, भूख या रोज़ के काम में बदलाव हुआ है?'),
    'review_of_systems':('Is there any other symptom or concern you want your doctor to know about?', 'क्या कोई और लक्षण या चिंता है जो डॉक्टर को बताना चाहते हैं?'),
})
FIELD_STAGE.update({'past_surgical_history':'SURGICAL_HISTORY','family_history':'FAMILY_HISTORY','social_history':'SOCIAL_HISTORY','personal_history':'PERSONAL_HISTORY','review_of_systems':'REVIEW_OF_SYSTEMS'})
# AYUSH fields record patient-reported Dashavidha Pariksha and lifestyle context.
# They are clearly kept separate from a practitioner assessment or diagnosis.
AYUSH_FIELDS = (
    'prakriti', 'vikriti', 'sara', 'samhanana', 'pramana', 'satmya', 'sattva',
    'ahara_shakti', 'vyayama_shakti', 'vaya', 'ahara_vihara', 'nidana', 'samprapti',
)
AYUSH_QUESTIONS = {
    'prakriti': ('How would you describe your usual body and temperament? This is your own description, not a diagnosis.', 'अपने सामान्य शरीर और स्वभाव का वर्णन करें। यह आपका अनुभव है, निदान नहीं।'),
    'vikriti': ('What change from your usual health or balance are you noticing now?', 'अपने सामान्य स्वास्थ्य या संतुलन में आप अभी क्या बदलाव महसूस कर रहे हैं?'),
    'sara': ('How would you describe your usual strength, skin, hair, and teeth?', 'अपनी सामान्य शक्ति, त्वचा, बाल और दांतों की स्थिति कैसे बताएंगे?'),
    'samhanana': ('How would you describe your body build and physical endurance?', 'अपने शरीर की बनावट और शारीरिक सहनशक्ति कैसे बताएंगे?'),
    'pramana': ('Are there body measurements or weight changes you want to share?', 'क्या कोई शारीरिक माप या वजन में बदलाव है जो आप बताना चाहते हैं?'),
    'satmya': ('Which foods, habits, or environments usually suit you or do not suit you?', 'कौन से भोजन, आदतें या वातावरण आपको अनुकूल या प्रतिकूल लगते हैं?'),
    'sattva': ('How are stress, mood, and coping affecting you currently?', 'तनाव, मनोदशा और सामना करने की क्षमता आपको अभी कैसे प्रभावित कर रही है?'),
    'ahara_shakti': ('How is your appetite and digestion compared with usual?', 'सामान्य की तुलना में आपकी भूख और पाचन कैसा है?'),
    'vyayama_shakti': ('How much physical activity can you comfortably do compared with usual?', 'सामान्य की तुलना में आप आराम से कितना शारीरिक कार्य कर पाते हैं?'),
    'vaya': ('Is there any age-related change important for the practitioner to know?', 'क्या उम्र से संबंधित कोई बदलाव है जो चिकित्सक को जानना चाहिए?'),
    'ahara_vihara': ('Please describe your usual food, sleep, work, and daily routine.', 'कृपया अपने सामान्य भोजन, नींद, काम और दिनचर्या के बारे में बताएं।'),
    'nidana': ('What do you think triggers or worsens this problem?', 'आपको क्या लगता है कि इस समस्या को क्या शुरू या बढ़ाता है?'),
    'samprapti': ('Please describe how this problem developed or changed over time in your own words.', 'कृपया अपने शब्दों में बताएं कि समस्या समय के साथ कैसे शुरू हुई या बदली।'),
}
FIELD_STAGE.update({field: 'AYUSH_HISTORY' for field in AYUSH_FIELDS})
ADDITIONAL_DOCUMENT_FIELDS = {'document_vitals', 'document_investigations'}
UNKNOWN_WORDS = ("don't know", "do not know", "not sure", "pata nahi", "मालूम नहीं")
DECLINED_WORDS = ("prefer not", "skip", "नहीं बताना")
NEGATIVE_WORDS = ("no", "not", "none", "without", "nahi", "nahin", "नहीं", "कोई नहीं")


def clean_text(value: str) -> str:
    return " ".join(value.strip().split())


@lru_cache(maxsize=1)
def runtime_ontology():
    definitions = {name:dict(value) for name,value in ONTOLOGY.items()}
    from backend.app.store import store
    import sqlite3
    try:
        with store.connection() as db:
            rows = db.execute('SELECT concept,payload_json FROM ontology_rules WHERE enabled=1').fetchall()
        for row in rows:
            payload=json.loads(row['payload_json'])
            base=definitions.get(row['concept'],{'synonyms':(),'required':(),'body_system':'general'})
            definitions[row['concept']] = {'synonyms':tuple(dict.fromkeys((*base['synonyms'],*payload.get('synonyms',[])))), 'required':tuple(dict.fromkeys((*base['required'],*payload.get('required',[])))), 'body_system':payload.get('body_system',base['body_system'])}
    except sqlite3.OperationalError:
        pass  # Pure clinical tests may run before the database is initialized.
    return definitions


def detect_complaint(text: str) -> str | None:
    lowered = text.casefold()
    for concept, definition in runtime_ontology().items():
        if any(alias.casefold() in lowered for alias in definition["synonyms"]):
            return concept
    return None


def _boolean(text: str) -> bool | None:
    lowered = text.casefold()
    if any(word in lowered for word in UNKNOWN_WORDS + DECLINED_WORDS):
        return None
    if any(re.search(rf"(?<!\w){re.escape(word)}(?!\w)", lowered) for word in NEGATIVE_WORDS):
        return False
    if re.search(r"\b(yes|yeah|yep|haan|han)\b|हाँ|हां", lowered):
        return True
    return None


def _duration(text: str) -> str | None:
    lowered = text.casefold()
    match = re.search(r"\b(\d{1,3})\s*(minutes?|mins?|hours?|hrs?|days?|weeks?|months?)\b", lowered)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    if "yesterday" in lowered or "कल" in text:
        return "since yesterday"
    if "today" in lowered or "आज" in text:
        return "since today"
    return None


def _severity(text: str, direct_answer: bool = False) -> int | None:
    match = re.search(r"\b(10|[0-9])\s*(?:/\s*10|out of 10)\b", text.casefold())
    if not match and direct_answer:
        match = re.fullmatch(r"\s*(10|[0-9])(?:\s*(?:please|thanks))?[.!]?\s*", text.casefold())
    if match:
        value = int(match.group(1))
        return value if 0 <= value <= 10 else None
    return None


def extract_rule_based(statement: str, question_id: str, state: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract only a fact evidenced by the submitted statement; no defaults."""
    text = clean_text(statement)
    if not text:
        return []
    result: dict[str, Any] = {}
    # A later answer can contain another symptom (for example "no nausea").
    # It must never silently replace the already established chief complaint.
    complaint = detect_complaint(text) if question_id == "chief_complaint" or not state.get("chief_complaint") else None
    if complaint:
        result["chief_complaint"] = complaint
    duration = _duration(text)
    if duration:
        result["duration"] = duration
    severity = _severity(text, question_id == "severity")
    if severity is not None:
        result["severity"] = severity

    explicit_symptoms = {
        "breathlessness": ("shortness of breath", "short of breath", "difficulty breathing", "breathless", "saans", "साँस"),
        "sweating": ("sweat", "sweating", "pasina", "पसीना"),
        "nausea": ("nausea", "nauseated", "vomiting", "vomit", "ulti", "मितली", "उल्टी"),
        "cough": ("cough", "khansi", "खाँसी"),
        "vomiting": ("vomiting", "vomit", "ulti", "उल्टी"),
        "fever": ("fever", "chills", "bukhar", "बुखार"),
        "fainting": ("faint", "fainted", "passed out", "बेहोश"),
    }
    lowered = text.casefold()
    for field, aliases in explicit_symptoms.items():
        clauses = re.split(r"[.;!?]|\bbut\b|\bhowever\b|लेकिन|परंतु", lowered)
        matching = [clause for clause in clauses if any(alias.casefold() in clause for alias in aliases)]
        if matching:
            interpretations = [_boolean(clause) if _boolean(clause) is not None else (None if any(word in clause for word in UNKNOWN_WORDS + DECLINED_WORDS) else True) for clause in matching]
            if len(set(interpretations)) == 1 and interpretations[0] is not None:
                result[field] = interpretations[0]
    if question_id in BOOL_FIELDS and question_id not in result:
        answer = _boolean(text)
        if answer is not None:
            result[question_id] = answer
    if question_id == "sudden_onset" and any(word in lowered for word in ("sudden", "suddenly", "अचानक")):
        result["sudden_onset"] = _boolean(text)
    if question_id == "temperature":
        temperature = re.search(r"\b(\d{2,3}(?:\.\d+)?)\s*°?\s*([cf])?\b", lowered)
        if temperature:
            result["temperature"] = f"{temperature.group(1)}{(temperature.group(2) or '').upper()}"
    if question_id in {"location", "character", "radiation", "exertion", "onset", "frequency"}:
        if not any(word in lowered for word in UNKNOWN_WORDS + DECLINED_WORDS):
            result[question_id] = text[:240]
    if question_id in LIST_FIELDS:
        if re.fullmatch(r"(?:no|none|none known|no known allergies|no medications|no medicines|no allergies|no conditions|nothing|nil|कोई नहीं|नहीं)[.!]?", lowered):
            result[question_id] = []
        else:
            result[question_id] = [item.strip() for item in re.split(r"[,;]", text) if item.strip()]
    if question_id == "chief_complaint" and not complaint:
        # Preserve the patient wording instead of assigning an unsupported diagnosis/symptom.
        result["chief_complaint"] = text[:240]
    if question_id == "onset" and "onset" not in result:
        result["onset"] = text[:240]
    if question_id in AYUSH_FIELDS and not any(word in lowered for word in UNKNOWN_WORDS + DECLINED_WORDS):
        result[question_id] = text[:1000]
    return [
        {"field_name": field, "value": value, "evidence": text, "confidence": 0.88, "source": "AI_EXTRACTION"}
        for field, value in result.items()
    ]


def required_fields(state: dict[str, Any], care_mode: str = 'MODERN') -> list[str]:
    complaint = state.get("chief_complaint")
    ontology = runtime_ontology()
    recognized = complaint if complaint in ontology else None
    complaint_fields = ontology[recognized]["required"] if recognized else ("duration", "severity")
    safety_order = {'chest pain':('breathlessness','severity'), 'headache':('sudden_onset','severity'), 'abdominal pain':('severity','vomiting')}.get(recognized, ())
    return list(dict.fromkeys(("chief_complaint", *safety_order, *complaint_fields, *COMMON_FIELDS, *(AYUSH_FIELDS if care_mode == 'AYUSH' else ()))))


def stage_for(state: dict[str, Any], care_mode: str = 'MODERN') -> str:
    missing = [field for field in required_fields(state, care_mode) if field not in state]
    if not missing:
        return "COMPLETENESS_CHECK"
    return FIELD_STAGE.get(missing[0], "HPI")


def next_question(state: dict[str, Any], language: Literal["en", "hi"], care_mode: str = 'MODERN') -> dict[str, Any] | None:
    for field in required_fields(state, care_mode):
        if field not in state:
            english, hindi = (QUESTIONS | AYUSH_QUESTIONS).get(field, (f"Please provide {field.replace('_', ' ')}.", f"कृपया {field.replace('_', ' ')} बताएँ।"))
            return {"id": field, "text": hindi if language == "hi" else english, "type": "text", "language": language, "stage": FIELD_STAGE.get(field, "HPI")}
    return None


def completeness(state: dict[str, Any], care_mode: str = 'MODERN') -> dict[str, Any]:
    required = required_fields(state, care_mode)
    missing = [field for field in required if field not in state]
    critical = [field for field in missing if field in {"chief_complaint", "duration", "severity", "breathlessness", "sudden_onset", "vomiting"}]
    answered = len(required) - len(missing)
    return {
        "completion_percentage": round((answered / len(required)) * 100) if required else 0,
        "missing": missing,
        "critical_missing": critical,
        "contradictions": [],
    }


def red_flags(state: dict[str, Any]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    complaint = state.get("chief_complaint")
    severity = state.get("severity")
    if type(severity) is not int or not 0 <= severity <= 10:
        severity = None
    if complaint == "chest pain" and state.get("breathlessness") is True:
        flags.append({"code": "CHEST_PAIN_BREATHLESSNESS", "severity": "EMERGENCY", "message": "Chest discomfort with breathing difficulty needs immediate clinician assessment.", "evidence": ["chief_complaint", "breathlessness"]})
    if complaint == "chest pain" and severity is not None and severity >= 7 and (state.get("sweating") is True or state.get("nausea") is True):
        flags.append({"code": "CHEST_PAIN_SYSTEMIC_SYMPTOMS", "severity": "HIGH", "message": "Severe chest discomfort with associated symptoms needs prompt clinician assessment.", "evidence": ["chief_complaint", "severity", "sweating", "nausea"]})
    if complaint == "headache" and state.get("sudden_onset") is True and severity is not None and severity >= 7:
        flags.append({"code": "SUDDEN_SEVERE_HEADACHE", "severity": "EMERGENCY", "message": "Sudden severe headache needs urgent clinician assessment.", "evidence": ["chief_complaint", "sudden_onset", "severity"]})
    if complaint == "abdominal pain" and severity is not None and severity >= 7 and state.get("vomiting") is True:
        flags.append({"code": "SEVERE_ABDOMINAL_PAIN_VOMITING", "severity": "HIGH", "message": "Severe abdominal pain with vomiting needs prompt clinician assessment.", "evidence": ["chief_complaint", "severity", "vomiting"]})
    if state.get("fainting") is True:
        flags.append({"code": "FAINTING_REPORTED", "severity": "HIGH", "message": "Reported fainting needs prompt clinician assessment.", "evidence": ["fainting"]})
    return flags


def factual_summary(state: dict[str, Any], status: dict[str, Any], flags: list[dict[str, Any]]) -> str:
    """A conservative record narrative, deliberately assembled from known values only."""
    complaint = state.get("chief_complaint")
    if not complaint:
        return "No chief complaint has been recorded."
    pieces = [f"Patient-reported concern: {complaint}."]
    for field, label in (("duration", "Duration"), ("onset", "Onset"), ("severity", "Severity"), ("location", "Location"), ("character", "Character")):
        if field in state:
            suffix = "/10" if field == "severity" else ""
            pieces.append(f"{label}: {state[field]}{suffix}.")
    positives = [name.replace("_", " ") for name, value in state.items() if name in BOOL_FIELDS and value is True]
    negatives = [name.replace("_", " ") for name, value in state.items() if name in BOOL_FIELDS and value is False]
    if positives:
        pieces.append("Reported associated findings: " + ", ".join(positives) + ".")
    if negatives:
        pieces.append("Explicitly denied: " + ", ".join(negatives) + ".")
    ayush_items = [f"{field.replace('_', ' ')}: {state[field]}" for field in AYUSH_FIELDS if field in state]
    if ayush_items:
        pieces.append("Patient-reported AYUSH history (not a practitioner assessment): " + "; ".join(ayush_items) + ".")
    if status["missing"]:
        pieces.append("Still missing: " + ", ".join(field.replace("_", " ") for field in status["missing"]) + ".")
    if flags:
        pieces.append("Safety rules triggered: " + "; ".join(flag["code"] for flag in flags) + ".")
    return " ".join(pieces)
