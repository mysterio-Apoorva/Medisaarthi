"""Real model, vector retrieval and image OCR acceptance checks with synthetic input."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
temporary=Path(tempfile.mkdtemp(prefix='medikiosk-local-ai-'))
os.environ['DATABASE_URL']=f'sqlite:///{temporary / "acceptance.sqlite3"}'
os.environ['AI_PROVIDER']='ollama'
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont
from backend.app.main import app
from backend.app.document_processing import classify_and_extract
from backend.app.ai.orchestrator import orchestrator

image=Image.new('RGB',(1100,250),'white')
draw=ImageDraw.Draw(image)
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',36)
draw.text((25,25),'SYNTHETIC patient report',font=font,fill='black')
draw.text((25,90),'Tablet Aspirin 75 mg',font=font,fill='black')
path=temporary/'synthetic-scan.png'
image.save(path)
processed=classify_and_extract(path)
assert processed.processing_status=='PROCESSED',processed
assert 'Aspirin' in processed.raw_text,processed.raw_text
assert processed.extracted[0]['value']==['Aspirin 75 mg'],processed.extracted
print('PASS: real local image OCR and medication candidate extraction',flush=True)

with TestClient(app) as client:
    assert client.post('/auth/login',json={'email':'admin.demo@medikiosk.local','password':'DemoPass!2026'}).status_code==200
    text='SYNTHETIC SOFTWARE TEST PROTOCOL. Before submitting an intake, the patient reviews the transcribed answer and corrects any mistakes. A clinician reviews incoming document facts before they become verified information. This is a test document, not medical guidance.'
    response=client.post('/knowledge/references',json={'title':'Synthetic intake software protocol','source_url':'https://example.org/synthetic-test-protocol','text':text,'approved':True})
    assert response.status_code==201,response.text
    source_id=response.json()['source_id']
    result=client.post('/knowledge/answer',json={'query':'Who reviews incoming document facts?'})
    assert result.status_code==200,result.text
    assert result.json()['results'],result.text
    assert result.json()['generated'] is True,result.text
    assert all(item['source_id']==source_id and item['excerpt'] in text for item in result.json()['results'])
    print('PASS: real local embeddings, persisted chunks, retrieval, model-selected grounded excerpts',flush=True)
    assert client.delete(f'/knowledge/references/{source_id}').status_code==200
    assert client.post('/knowledge/search',json={'query':'document facts'}).json()['results']==[]
    facts=[{'fact_id':'fact-one','field_name':'chief_complaint','value':'chest pain','source':'PATIENT_REPORTED'}, {'fact_id':'fact-two','field_name':'duration','value':'since yesterday','source':'PATIENT_REPORTED'}]
    summary=orchestrator.summary.run(facts,{'chief_complaint':'chest pain','duration':'since yesterday'})
    assert {f['fact_id'] for section in summary['sections'] for f in section['facts']}=={'fact-one','fact-two'}
    print('PASS: real local model summary with exact fact references',flush=True)
print('All local AI acceptance checks passed. Test data is isolated at',temporary)
