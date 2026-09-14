"""Adaptive, bounded interview planning. Only persisted clinical answers spend turns."""
from __future__ import annotations

import json
from collections import Counter
from typing import Any

from backend.app.clinical_engine import (
    AYUSH_FIELDS, AYUSH_QUESTIONS, BOOL_FIELDS, COMMON_FIELDS, QUESTIONS,
    FIELD_STAGE, required_fields, red_flags,
)

MIN_QUESTIONS = 5
MAX_QUESTIONS = 10
HISTORY = ('past_medical_history', 'medications', 'allergies')
GROUPS = (
    ('breathlessness', 'sweating', 'nausea', 'fainting'),
    ('sudden_onset', 'vomiting', 'chest_pain', 'cough', 'fever', 'abdominal_pain'),
    ('duration', 'onset', 'severity', 'temperature', 'frequency'),
    ('location', 'character', 'radiation'),
    ('exertion',), HISTORY,
    ('past_surgical_history', 'family_history'),
    ('social_history', 'personal_history'), ('review_of_systems',),
    ('prakriti', 'sara', 'samhanana', 'pramana', 'vaya'),
    ('ahara_vihara', 'ahara_shakti', 'satmya'),
    ('vikriti', 'sattva', 'vyayama_shakti', 'nidana', 'samprapti'),
)

# Short field phrases let the planner group only what is actually missing.
PHRASES = {
    'duration': ('when it started', 'यह कब शुरू हुआ'),
    'onset': ('whether it started suddenly or gradually', 'यह अचानक शुरू हुआ या धीरे-धीरे'),
    'severity': ('how severe it is from zero to ten', 'शून्य से दस तक यह कितना तेज है'),
    'location': ('where you feel it', 'यह कहाँ महसूस होता है'),
    'character': ('what it feels like', 'यह कैसा महसूस होता है'),
    'radiation': ('whether it spreads anywhere else', 'क्या यह कहीं और फैलता है'),
    'exertion': ('what makes it worse or better', 'यह किससे बढ़ता या कम होता है'),
    'temperature': ('your measured temperature, if known', 'अगर नापा है तो अपना तापमान'),
    'frequency': ('how often it happens', 'यह कितनी बार होता है'),
    'past_medical_history': ('any long-term health conditions', 'कोई पुरानी बीमारी'),
    'medications': ('medicines you currently take', 'आपकी वर्तमान दवाएँ'),
    'allergies': ('any known allergies', 'कोई ज्ञात एलर्जी'),
    'breathlessness': ('difficulty breathing', 'साँस लेने में तकलीफ'),
    'sweating': ('unusual sweating', 'असामान्य पसीना'),
    'nausea': ('nausea', 'मितली'), 'fainting': ('fainting', 'बेहोशी'),
    'sudden_onset': ('a sudden start reaching maximum intensity quickly', 'अचानक बहुत तेज शुरुआत'),
    'vomiting': ('vomiting', 'उल्टी'), 'chest_pain': ('chest pain', 'सीने में दर्द'),
    'cough': ('cough', 'खाँसी'), 'fever': ('fever', 'बुखार'),
    'abdominal_pain': ('abdominal pain', 'पेट में दर्द'),
}


def core_fields(state, care_mode='MODERN'):
    fields = [f for f in required_fields(state, care_mode) if f not in COMMON_FIELDS and f not in AYUSH_FIELDS]
    return fields + list(HISTORY) + (['ahara_vihara', 'vikriti'] if care_mode == 'AYUSH' else [])


def budget(state, answers, care_mode='MODERN'):
    count = len(answers)
    missing = [f for f in core_fields(state, care_mode) if f not in state]
    sufficient = not missing and not red_flags(state) and not state.get('_unresolved_safety')
    done = count >= MAX_QUESTIONS or (count >= MIN_QUESTIONS and sufficient)
    return {'minimum': MIN_QUESTIONS, 'maximum': MAX_QUESTIONS, 'answered': count,
            'complete': done, 'reason': 'question_limit' if count >= MAX_QUESTIONS else 'sufficient_information' if done else None,
            'unresolved_fields': missing, 'needs_clinician_review': bool(missing or red_flags(state) or state.get('_unresolved_safety'))}


def record_candidates(db, patient_id, encounter_id):
    """Prior reports remain candidates until confirmed. Never silently import historical meds."""
    result = {}
    rows = db.execute("""SELECT e.field_name,e.value_json,e.evidence,e.document_id,e.page_number
        FROM document_entities e JOIN documents d ON d.document_id=e.document_id
        WHERE d.patient_id=? AND e.verification_status!='REJECTED' AND e.confidence>=0.8
        AND e.field_name IN ('medications','allergies','past_medical_history','past_surgical_history')
        AND NOT EXISTS (SELECT 1 FROM reconciliation_items r WHERE r.document_id=e.document_id
            AND r.field_name=e.field_name AND r.status='REJECTED')
        ORDER BY d.uploaded_at DESC,e.created_at DESC""", (patient_id,)).fetchall()
    for row in rows:
        if row['field_name'] not in result:
            value = json.loads(row['value_json'])
            if isinstance(value, str): value = [value]
            if isinstance(value, list) and value and all(isinstance(v, str) and len(v) <= 500 for v in value):
                result[row['field_name']] = {**dict(row), 'value': value, 'source': 'document'}
    rows = db.execute("""SELECT field_name,value_json,fact_id FROM clinical_facts WHERE patient_id=?
        AND encounter_id!=? AND status='VERIFIED' AND superseded_at IS NULL
        AND field_name IN ('medications','allergies','past_medical_history','past_surgical_history')
        ORDER BY created_at DESC""", (patient_id, encounter_id)).fetchall()
    for row in rows:
        result.setdefault(row['field_name'], {**dict(row), 'value': json.loads(row['value_json']), 'source': 'record'})
    return result


def plan_question(state: dict[str, Any], language, care_mode, answers, candidates=None):
    if budget(state, answers, care_mode)['complete']:
        return None
    hi = language == 'hi'
    counts = Counter(a['question_id'] for a in answers)
    if not state.get('chief_complaint'):
        fields = ['chief_complaint']
    else:
        required = required_fields(state, care_mode)
        missing = [f for f in required if f not in state]
        # Reserve core history and AYUSH context before spending repeated turns on unknowns.
        ordered = sorted(missing, key=lambda f: (counts[f], 0 if f in core_fields(state, care_mode) else 1, required.index(f)))
        primary = ordered[0] if ordered else 'review_of_systems'
        group = next((g for g in GROUPS if primary in g), (primary,))
        fields = [primary] + [f for f in group if f != primary and f in missing][:2]
    primary = fields[0]
    candidate = (candidates or {}).get(primary)
    prefix = '' if not answers else ('धन्यवाद। ' if hi else 'Thank you. ')
    if candidate and not counts[primary]:
        values = ', '.join(str(v) for v in candidate['value'])[:400]
        label = PHRASES.get(primary, (primary.replace('_', ' '), 'स्वास्थ्य जानकारी'))[int(hi)]
        text = (f'आपके पिछले रिकॉर्ड में {label}: {values} लिखा है। क्या यह अभी भी सही है? अगर बदला है तो बताइए।' if hi else
                f'Your previous {candidate["source"]} lists {label}: {values}. Is this still correct? Please tell me if it has changed.')
        fields = [primary]
    elif primary == 'chief_complaint':
        text = QUESTIONS[primary][int(hi)]
    elif len(fields) == 1:
        text = (QUESTIONS | AYUSH_QUESTIONS).get(primary, ('Please tell me about this symptom.', 'कृपया इस लक्षण के बारे में बताइए।'))[int(hi)]
    elif all(f in PHRASES for f in fields):
        phrases = (' और ' if hi else ', and ').join(PHRASES[f][int(hi)] for f in fields)
        if all(f in BOOL_FIELDS for f in fields):
            text = f'क्या आपको {phrases} है? जो नहीं है वह भी बताइए।' if hi else f'Have you noticed {phrases}? Please also tell me which you do not have.'
        else:
            text = f'कृपया बताइए: {phrases}।' if hi else f'Could you tell me about {phrases}?'
    else:
        text = ' '.join((QUESTIONS | AYUSH_QUESTIONS)[f][int(hi)] for f in fields)
    return {'id': primary, 'fields': fields, 'text': prefix + text, 'type': 'text', 'language': language,
            'stage': FIELD_STAGE.get(primary, 'HPI'), 'confirmation': candidate if candidate and not counts[primary] else None}
