"""Declarative collection graph, deliberately separate from language understanding.

Order sets priority among currently eligible nodes. Conditions create branches;
facts collected ahead of time skip their nodes. These are demo collection prompts,
not a clinically validated triage protocol.
"""

from dataclasses import dataclass

from app.interview.schemas import ClinicalField, ClinicalState, Language, NextQuestion


@dataclass(frozen=True)
class Node:
    field: ClinicalField
    en: str
    hi: str
    when_true: ClinicalField | None = None

    def eligible(self, state: ClinicalState) -> bool:
        return self.when_true is None or getattr(state, self.when_true) is True


OPENING = Node(
    "chief_complaint",
    "What brings you to the hospital today?",
    "आज आपको किस परेशानी के कारण अस्पताल आना पड़ा?",
)
DURATION = Node("duration", "How long have you had this problem?", "यह परेशानी कब से है?")
SEVERITY = Node("severity", "How severe is it from 0 to 10?", "० से १० में तकलीफ़ कितनी है?")
LOCATION = Node("location", "Where do you feel the pain?", "दर्द कहाँ हो रहा है?")
HPI = Node(
    "hpi",
    "Please describe how this problem started and changed.",
    "यह परेशानी कैसे शुरू हुई और कैसे बदली, बताइए।",
)
BREATH = Node("breathlessness", "Are you having difficulty breathing?", "क्या साँस लेने में दिक्कत है?")
BREATH_ONSET = Node(
    "breathlessness_onset",
    "When did the breathing difficulty start?",
    "साँस लेने की दिक्कत कब शुरू हुई?",
    "breathlessness",
)
COMMON = (
    Node(
        "past_medical_history",
        "Do you have any past medical conditions?",
        "क्या आपको पहले से कोई बीमारी है?",
    ),
    Node(
        "medications",
        "What medicines are you currently taking, if any?",
        "आप अभी कौन सी दवाएँ ले रहे हैं, अगर कोई हैं?",
    ),
    Node("allergies", "Do you have any known allergies?", "क्या आपको कोई ज्ञात एलर्जी है?"),
    Node(
        "family_history",
        "Is there any relevant illness in your family?",
        "क्या आपके परिवार में कोई संबंधित बीमारी है?",
    ),
    Node(
        "personal_history",
        "Is there anything about your habits or daily life to tell the doctor?",
        "क्या अपनी आदतों या दिनचर्या के बारे में डॉक्टर को कुछ बताना चाहेंगे?",
    ),
)
PATHWAYS: dict[str, tuple[Node, ...]] = {
    "chest pain": (BREATH, BREATH_ONSET, DURATION, SEVERITY, LOCATION, HPI),
    "fever": (
        DURATION,
        Node(
            "temperature",
            "Have you measured your temperature? Include the unit.",
            "क्या आपने तापमान मापा है? इकाई भी बताइए।",
        ),
        Node("cough", "Do you also have a cough?", "क्या खाँसी भी है?"),
        HPI,
    ),
    "headache": (
        Node("sudden_onset", "Did the headache start suddenly?", "क्या सिरदर्द अचानक शुरू हुआ?"),
        DURATION,
        SEVERITY,
        LOCATION,
        HPI,
    ),
    "abdominal pain": (
        LOCATION,
        DURATION,
        SEVERITY,
        Node("vomiting", "Have you been vomiting?", "क्या उल्टी हो रही है?"),
        HPI,
    ),
}


class QuestionGraph:
    def __init__(self, pathways: dict[str, tuple[Node, ...]] | None = None):
        self.pathways = dict(PATHWAYS if pathways is None else pathways)

    def nodes(self, state: ClinicalState) -> list[Node]:
        if not state.chief_complaint:
            return [OPENING]
        pathway = self.pathways.get(state.chief_complaint.casefold(), (DURATION, HPI))
        return [node for node in (*pathway, *COMMON) if node.eligible(state)]

    def missing(self, state: ClinicalState, answered: set[str]) -> list[Node]:
        return [node for node in self.nodes(state) if node.field not in answered]

    @staticmethod
    def question(node: Node, language: Language, clarification: bool = False) -> NextQuestion:
        text = node.hi if language == "hi" else node.en
        if clarification:
            prefix = "मैं समझ नहीं पाया। " if language == "hi" else "I couldn't understand that. "
            text = prefix + text
        return NextQuestion(
            id=node.field, text=text, language=language, clarification=clarification
        )
