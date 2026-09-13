"""Real browser/audio/API proof. Requires running UI/backend and installed local models.

Chromium's file microphone injects SYNTHETIC Piper speech as PCM into real
getUserMedia/MediaRecorder. No API, Whisper, Ollama, or speech output is mocked.
This cannot certify the user's physical microphone or speakers.
"""
from __future__ import annotations
import io
import json
import os
from pathlib import Path
import sys
import time
import wave
import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app.tts import synthesize
from playwright.sync_api import sync_playwright, expect


def main():
    base = os.getenv('E2E_BASE_URL', 'http://127.0.0.1:3000')
    output = Path('backend/data/browser-e2e').resolve()
    output.mkdir(parents=True, exist_ok=True)
    audio_path = output / 'synthetic-microphone.wav'
    audio = synthesize('I have been having chest pain since yesterday. The pain feels like pressure in the middle of my chest.', 'en')
    with wave.open(io.BytesIO(audio), 'rb') as source:
        with wave.open(str(audio_path), 'wb') as target:
            target.setparams(source.getparams())
            target.writeframes(b'\x00\x00' * source.getframerate())
            target.writeframes(source.readframes(source.getnframes()))
            target.writeframes(b'\x00\x00' * source.getframerate() * 2)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True, args=[
            '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
            f'--use-file-for-fake-audio-capture={audio_path}', '--autoplay-policy=no-user-gesture-required',
        ])
        context = browser.new_context(permissions=['microphone'], viewport={'width':1280,'height':1000})
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.set_default_timeout(45000)
        page.goto(f'{base}/patient/identify')
        page.get_by_label('Email', exact=True).fill('patient.demo@medikiosk.local')
        page.get_by_label('Password', exact=True).fill(os.getenv('DEMO_PASSWORD', 'DemoPass!2026'))
        page.get_by_role('button', name='Securely continue').click()
        page.wait_for_url('**/patient/language')
        page.evaluate("localStorage.setItem('medisaarthi_selected_lang','en')")
        page.goto(f'{base}/patient/consent')
        page.get_by_role('checkbox').check()
        page.locator('#agree-continue-button').click()
        page.wait_for_url('**/patient/interview')
        expect(page.locator('#active-question-text')).not_to_be_empty()
        identifier = page.evaluate("localStorage.getItem('medisaarthi_current_interview_id')")
        def snapshot():
            response = context.request.get(f'{base}/api/interviews/{identifier}')
            assert response.ok, response.text()
            return response.json()
        initial = snapshot()
        assert initial['revision'] == 0
        page.reload()
        expect(page.locator('#active-question-text')).not_to_be_empty()
        assert page.evaluate("localStorage.getItem('medisaarthi_current_interview_id')") == identifier
        assert snapshot()['revision'] == 0

        with page.expect_response(lambda r: '/speech/synthesize' in r.url, timeout=60000) as audio_response:
            page.locator('#listen-question-btn').click()
        assert audio_response.value.ok, audio_response.value.text()
        expect(page.get_by_test_id('talking-avatar')).to_have_attribute('data-state', 'speaking')
        mouth_values = []
        for _ in range(14):
            mouth_values.append(float(page.get_by_test_id('avatar-mouth').get_attribute('ry')))
            page.wait_for_timeout(90)
        assert max(mouth_values) - min(mouth_values) > 0.3, mouth_values
        page.screenshot(path=str(output / 'avatar-speaking.png'), full_page=True)

        page.locator('#voice-record-btn').click()
        expect(page.get_by_test_id('talking-avatar')).to_have_attribute('data-state', 'listening')
        assert float(page.get_by_test_id('avatar-mouth').get_attribute('ry')) == 1.5
        page.wait_for_timeout(10000)
        with page.expect_response(lambda r: '/transcribe' in r.url, timeout=120000) as transcription:
            page.locator('#voice-stop-btn').click()
        assert transcription.value.ok, transcription.value.text()
        expect(page.locator('#patient-answer-input')).not_to_have_value('')
        draft = page.locator('#patient-answer-input').input_value()
        assert 'chest' in draft.lower() and 'yesterday' in draft.lower(), draft
        assert snapshot()['revision'] == 0 and snapshot()['answers'] == []
        # The patient's correction is the only text that may become an answer.
        corrected = 'I have chest pain since yesterday and I am short of breath.'
        page.locator('#patient-answer-input').fill(corrected)
        with page.expect_response(lambda r: r.url.endswith('/answers'), timeout=60000) as answer:
            page.locator('#patient-answer-input').press('Enter')
        assert answer.value.ok, answer.value.text()
        saved = snapshot()
        assert saved['revision'] == 1
        assert saved['answers'][0]['answer_text'] == corrected
        assert saved['clinical_state']['chief_complaint'] == 'chest pain'
        assert saved['clinical_state']['breathlessness'] is True
        expect(page.locator('#clinical-safety-alert')).to_be_visible()
        expect(page.locator('#patient-answer-input')).to_have_value('')
        page.screenshot(path=str(output / 'voice-review-safety.png'), full_page=True)
        # Next typed answer verifies voice-to-text revision continuity.
        page.locator('#patient-answer-input').fill('8 out of 10' if snapshot()['next_question']['id'] == 'severity' else 'central chest')
        with page.expect_response(lambda r: r.url.endswith('/answers'), timeout=60000) as second:
            page.locator('#patient-answer-input').press('Enter')
        assert second.value.ok, second.value.text()
        assert snapshot()['revision'] == 2
        page.reload()
        expect(page.locator('#active-question-text')).not_to_be_empty()
        assert snapshot()['revision'] == 2
        # Complete the actual adaptive interview; fixture answers are synthetic test inputs.
        page.locator('#switch-to-typing-btn').click()
        answers = {'duration':'since yesterday','location':'central chest','severity':'8 out of 10','character':'heavy pressure','radiation':'It does not spread anywhere','exertion':'Walking makes it worse','breathlessness':'yes','sweating':'yes','nausea':'no nausea','past_medical_history':'hypertension','medications':'amlodipine 5 mg','allergies':'no known allergies'}
        for _ in range(25):
            answers.update({'past_surgical_history':'none','family_history':'Father has hypertension','social_history':'I do not smoke. I am a teacher.','personal_history':'Sleep has been disturbed','review_of_systems':'none'})
            state = snapshot()
            if state['status'] == 'PATIENT_REVIEW':
                break
            question = state['next_question']['id']
            assert question in answers, question
            expect(page.locator('#patient-answer-input')).to_be_enabled()
            page.locator('#patient-answer-input').fill(answers[question])
            with page.expect_response(lambda r: r.url.endswith('/answers'), timeout=60000) as turn:
                page.locator('#patient-answer-input').press('Enter')
            assert turn.value.ok, turn.value.text()
        expect(page.locator('#view-completed-button')).to_be_visible()
        page.locator('#view-completed-button').click()
        page.wait_for_url('**/patient/review')
        expect(page.get_by_role('heading', name='Review your information')).to_be_visible()
        page.get_by_role('textbox', name='severity', exact=True).fill('7')
        with page.expect_response(lambda r: r.url.endswith('/corrections')) as correction:
            page.get_by_role('button', name='Save severity', exact=True).click()
        assert correction.value.ok, correction.value.text()
        assert snapshot()['clinical_state']['severity'] == 7
        report = output / 'synthetic-report.pdf'
        pdf = pymupdf.open()
        report_page = pdf.new_page()
        report_page.insert_text((72,72), 'SYNTHETIC TEST REPORT - NOT A REAL PATIENT\nPatient report\nTablet Aspirin 75 mg\nAllergies: penicillin')
        pdf.save(report)
        pdf.close()
        with page.expect_response(lambda r: '/documents/encounters/' in r.url and r.request.method=='POST', timeout=60000) as upload:
            page.locator('input[type=file]').set_input_files(str(report))
        assert upload.value.status == 201, upload.value.text()
        expect(page.get_by_text('synthetic-report.pdf', exact=False).first).to_be_visible()
        page.get_by_role('button', name='Review extracted text').click()
        expect(page.locator('pre')).to_contain_text('Aspirin')
        page.get_by_role('checkbox').check()
        page.locator('#submit-reviewed-intake').click()
        page.wait_for_url('**/patient/completed')
        assert snapshot()['status'] == 'SUBMITTED'
        print('PASS: reviewed correction, PDF extraction, submission consent', flush=True)

        page.goto(f'{base}/doctor/login')
        page.get_by_label('Hospital email').fill('doctor.demo@medikiosk.local')
        page.get_by_label('Password', exact=True).fill(os.getenv('DEMO_PASSWORD','DemoPass!2026'))
        page.get_by_role('button', name='Sign in securely').click()
        page.wait_for_url(f'{base}/doctor')
        page.goto(f'{base}/doctor/patients/P1001')
        expect(page.locator('#patient-name-header')).to_be_visible()
        page.get_by_text('Clinical fact provenance', exact=True).click()
        expect(page.get_by_text('PATIENT_REPORTED · REPORTED', exact=False).first).to_be_visible()
        page.get_by_role('button', name='Generate grounded AI summary').click()
        expect(page.get_by_test_id('grounded-ai-summary')).to_be_visible(timeout=120000)
        assert page.get_by_test_id('reconciliation-item').count() >= 2
        # Reject a conflicting medication and approve the document allergy, with real API persistence.
        first_item = page.get_by_test_id('reconciliation-item').first
        first_item.get_by_role('button', name='Reject incoming').click()
        expect(page.get_by_test_id('reconciliation-item')).to_have_count(1)
        page.get_by_test_id('reconciliation-item').get_by_role('button', name='Approve incoming').click()
        expect(page.get_by_test_id('reconciliation-item')).to_have_count(0)
        with page.expect_download() as download:
            page.get_by_role('link', name='Download local FHIR R4 bundle').click()
        downloaded = Path(download.value.path()).read_text(encoding='utf-8')
        assert json.loads(downloaded)['resourceType'] == 'Bundle'
        page.locator('#verify-summary-btn').click()
        with page.expect_response(lambda r: r.url.endswith('/finalize')) as finalized:
            page.locator('#confirm-verify-btn').click()
        assert finalized.value.ok, finalized.value.text()
        assert snapshot()['status'] == 'FINALIZED'
        page.reload()
        expect(page.get_by_role('button', name='Finalized', exact=True)).to_be_disabled()
        page.screenshot(path=str(output / 'doctor-finalized.png'), full_page=True)
        print('PASS: doctor source review, real model summary, reconciliation, FHIR, finalization', flush=True)
        page.goto(f'{base}/doctor/login')
        page.get_by_label('Hospital email').fill('admin.demo@medikiosk.local')
        page.get_by_label('Password', exact=True).fill(os.getenv('DEMO_PASSWORD','DemoPass!2026'))
        page.get_by_role('button', name='Sign in securely').click()
        page.wait_for_url(f'{base}/admin')
        expect(page.get_by_text('ENCOUNTER_FINALIZED', exact=True).first).to_be_visible()
        print('PASS: admin login and finalization audit visible', flush=True)
        assert not errors, errors
        print(json.dumps({'result':'PASS', 'encounter_id':identifier, 'real_stt_transcript':draft, 'mouth_opening_range':[min(mouth_values),max(mouth_values)], 'tests':['cookie login','consent','idempotent refresh','local TTS WAV','audio-driven mouth','recording interrupts speech','real MediaRecorder to Whisper','draft not stored','corrected answer persisted','safety alert','typed answer after voice','no browser runtime errors']}, indent=2))
        browser.close()


if __name__ == '__main__':
    main()
