"""Local FHIR R4 collection export. No remote server or ABDM connectivity implied."""
import json
from typing import Any


def fid(value: str) -> str:
    return value.replace('_','-')


def export_bundle(db, encounter: dict[str, Any]):
    patient = dict(db.execute('SELECT * FROM patients WHERE patient_id=?', (encounter['patient_id'],)).fetchone())
    patient_ref = {'reference':f"Patient/{fid(patient['patient_id'])}"}
    encounter_ref = {'reference':f"Encounter/{fid(encounter['encounter_id'])}"}
    resources = [
        {'resourceType':'Patient','id':fid(patient['patient_id']),'identifier':[{'system':'urn:medikiosk:patient-id','value':patient['patient_id']}],'name':[{'text':patient['name']}],'gender':patient['gender'].lower()},
        {'resourceType':'Encounter','id':fid(encounter['encounter_id']),'status':'finished' if encounter['status']=='FINALIZED' else 'in-progress','class':{'system':'http://terminology.hl7.org/CodeSystem/v3-ActCode','code':'AMB'},'subject':patient_ref,'period':{'start':encounter['started_at'], **({'end':encounter['finalized_at']} if encounter['finalized_at'] else {})}},
    ]
    for row in db.execute("SELECT * FROM clinical_facts WHERE encounter_id=? AND superseded_at IS NULL AND status IN ('REPORTED','VERIFIED')", (encounter['encounter_id'],)):
        value = json.loads(row['value_json'])
        observation = {'resourceType':'Observation','id':fid(row['fact_id']),'status':'final' if row['status']=='VERIFIED' else 'preliminary','subject':patient_ref,'encounter':encounter_ref,'code':{'text':row['field_name'].replace('_',' ')},'effectiveDateTime':row['created_at'],'note':[{'text':f"Source: {row['source']}; evidence: {row['evidence'] or 'not recorded'}"}]}
        if type(value) is bool:
            observation['valueBoolean'] = value
        elif type(value) is int:
            observation['valueInteger'] = value
        else:
            observation['valueString'] = '; '.join(value) if isinstance(value,list) else str(value)
            if not observation['valueString']:
                observation['valueString'] = 'None reported'
        resources.append(observation)
        if row['field_name'] in {'medications','allergies','past_medical_history'} and isinstance(value,list):
            for index, item in enumerate(value):
                identifier = f"{fid(row['fact_id'])}-{index}"
                if row['field_name']=='medications':
                    resources.append({'resourceType':'Medication','id':identifier,'code':{'text':item}})
                    resources.append({'resourceType':'MedicationStatement','id':identifier,'status':'active','subject':patient_ref,'context':encounter_ref,'medicationReference':{'reference':f'Medication/{identifier}'},'dateAsserted':row['created_at'],'note':[{'text':f"Reported medication text; dosing has not been independently normalized. Source: {row['source']}"}]})
                elif row['field_name']=='allergies' and item.lower() not in {'none','none known','no known allergies'}:
                    resources.append({'resourceType':'AllergyIntolerance','id':identifier,'patient':patient_ref,'code':{'text':item},'verificationStatus':{'coding':[{'system':'http://terminology.hl7.org/CodeSystem/allergyintolerance-verification','code':'confirmed' if row['status']=='VERIFIED' else 'unconfirmed'}]}})
                elif row['field_name']=='past_medical_history':
                    resources.append({'resourceType':'Condition','id':identifier,'subject':patient_ref,'code':{'text':item},'verificationStatus':{'coding':[{'system':'http://terminology.hl7.org/CodeSystem/condition-ver-status','code':'confirmed' if row['status']=='VERIFIED' else 'unconfirmed'}]},'note':[{'text':'Historical condition reported during intake; not a new diagnosis.'}]})
    for doc in db.execute('SELECT * FROM documents WHERE encounter_id=?',(encounter['encounter_id'],)):
        resources.append({'resourceType':'DocumentReference','id':fid(doc['document_id']),'status':'current','subject':patient_ref,'date':doc['uploaded_at'],'content':[{'attachment':{'contentType':doc['mime_type'],'title':doc['original_name'],'size':doc['size_bytes'],'url':f"/api/documents/{doc['document_id']}/file"}}]})
    for consent in db.execute('SELECT * FROM consents WHERE encounter_id=?',(encounter['encounter_id'],)):
        resources.append({'resourceType':'Consent','id':fid(consent['consent_id']),'status':'active' if consent['status']=='GRANTED' else 'inactive','scope':{'coding':[{'system':'http://terminology.hl7.org/CodeSystem/consentscope','code':'patient-privacy'}]},'category':[{'text':consent['consent_type']}],'patient':patient_ref,'dateTime':consent['recorded_at'],'policyRule':{'text':f"{consent['purpose']} (version {consent['version']})"}})
    return {'resourceType':'Bundle','type':'collection','entry':[{'resource':resource} for resource in resources]}
