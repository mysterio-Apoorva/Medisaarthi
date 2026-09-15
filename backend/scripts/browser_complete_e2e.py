"""Fresh synthetic patient through real UI, AI, audio, OCR, prescribing, PDF and follow-up.

Only the physical microphone source is replaced by synthetic spoken WAV audio.
No HTTP responses, model outputs, transcripts, extracted records or database rows are injected.
Run against the isolated acceptance servers documented in docs/END_TO_END_AUDIT.md.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta

import pymupdf
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright, expect

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.scripts.browser_handsfree_e2e import wav_parts


def main():
    base = os.getenv('E2E_BASE_URL', 'http://127.0.0.1:3000')
    output = Path('.runtime/full-e2e')
    output.mkdir(parents=True, exist_ok=True)
    name = 'Synthetic Complete ' + str(time.time_ns())
    email = f'complete.{time.time_ns()}@medikiosk.test'
    password = 'SyntheticPassword!2026'
    spoken = [wav_parts(parts) for parts in [
        ['My knee is sore since yesterday.', 2, 'The soreness is three out of ten.'],
        ['No medical conditions. No medicines. No known allergies.'],
        ['None.'], ['None.'], ['Nothing else.'],
    ]]
    report = output / 'synthetic-laboratory.pdf'
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((45, 60), 'SYNTHETIC LABORATORY REPORT\nHemoglobin: 11.2 g/dL (12.0-15.0)\nTest date: 2026-09-14')
        document.save(report)
    scan = output / 'synthetic-scan.png'
    picture = Image.new('RGB', (1100, 250), 'white')
    draw = ImageDraw.Draw(picture)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 36)
    draw.text((25, 25), 'SYNTHETIC historical prescription', font=font, fill='black')
    draw.text((25, 95), 'Tablet Aspirin 75 mg', font=font, fill='black')
    picture.save(scan)
    errors, requests, mouths, states = [], [], [], []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True, args=['--autoplay-policy=no-user-gesture-required', '--use-fake-ui-for-media-stream'])
        patient = browser.new_context(permissions=['microphone'], viewport={'width': 1280, 'height': 1000})
        patient.expose_binding('patientAudio', lambda source, index: spoken[min(index, len(spoken) - 1)])
        patient.add_init_script('''
            window.__captureCount = 0;
            navigator.mediaDevices.getUserMedia = async () => {
                const encoded = await window.patientAudio(window.__captureCount++);
                const ctx = new AudioContext(); await ctx.resume();
                const destination = ctx.createMediaStreamDestination();
                const raw = Uint8Array.from(atob(encoded), c => c.charCodeAt(0));
                const audio = await ctx.decodeAudioData(raw.buffer);
                const source = ctx.createBufferSource(); source.buffer = audio; source.connect(destination);
                source.start(ctx.currentTime + .5);
                const track = destination.stream.getAudioTracks()[0]; const stop = track.stop.bind(track);
                track.stop = () => { stop(); try { source.stop(); } catch {} void ctx.close(); };
                return destination.stream;
            };
        ''')

        def observe(page):
            page.set_default_timeout(60000)
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('response', lambda r: requests.append({'method': r.request.method, 'path': r.url.split('/api')[-1], 'status': r.status}) if '/api/' in r.url else None)

        page = patient.new_page(); observe(page)
        page.goto(base + '/patient/identify')
        page.get_by_role('button', name='Create account', exact=True).click()
        page.get_by_label('Full name').fill(name)
        page.get_by_label('Age', exact=True).fill('30')
        page.get_by_role('combobox').select_option('Other')
        page.get_by_label('Email', exact=True).fill(email)
        page.get_by_label('Password', exact=True).fill(password)
        with page.expect_response(lambda r: r.url.endswith('/auth/register')) as registered:
            page.get_by_role('button', name='Create account and continue').click()
        assert registered.value.status == 201, registered.value.text()
        patient_id = registered.value.json()['patient_id']
        page.wait_for_url('**/patient/language')
        page.get_by_role('button', name=re.compile('Continue interview in English')).click()
        page.locator('#continue-button').click()
        page.wait_for_url('**/patient/consent')
        page.get_by_role('checkbox').check()
        page.locator('#agree-continue-button').click()
        page.wait_for_url('**/patient/interview')
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            root = page.get_by_test_id('hands-free-interview')
            if '/patient/review' in page.url:
                break
            state = root.get_attribute('data-state') if root.count() else None
            if state and (not states or states[-1] != state):
                states.append(state); print('Interview:', state, flush=True)
            if state in {'AI_ERROR', 'TTS_ERROR', 'MICROPHONE_ERROR'}:
                raise AssertionError(page.locator('main').inner_text())
            mouth = page.get_by_test_id('avatar-mouth')
            if mouth.count():
                mouths.append(float(mouth.get_attribute('ry')))
            if state == 'COMPLETED':
                page.locator('#view-completed-button').click()
                break
            page.wait_for_timeout(200)
        page.wait_for_url('**/patient/review')
        identifier = page.evaluate("localStorage.getItem('medisaarthi_current_interview_id')")
        def snapshot():
            response = patient.request.get(base + '/api/interviews/' + identifier)
            assert response.ok, response.text()
            return response.json()
        record = snapshot()
        assert 5 <= len(record['answers']) <= 10
        assert record['encounter']['ai_provider'] == 'ollama'
        assert max(mouths) - min(mouths) > .5
        assert any(r['path'].endswith('/transcribe') and r['status'] == 200 for r in requests)
        assert any(r['path'].endswith('/speech/synthesize') and r['status'] == 200 for r in requests)
        page.reload()
        expect(page.get_by_role('heading', name='Review your information')).to_be_visible()
        assert len(snapshot()['answers']) == len(record['answers'])
        # ASR is intentionally reviewable. Correct the actual recognized draft using the UI.
        page.get_by_role('textbox', name='chief complaint', exact=True).fill('Knee soreness since yesterday')
        expect(page.get_by_test_id('clinical-record').get_by_label('Type', exact=True)).to_be_visible()
        patient.set_offline(True)
        page.get_by_role('button', name='Save chief complaint', exact=True).click()
        expect(page.locator('main').get_by_role('alert').filter(has_text='Unable to reach the MediKiosk service').first).to_be_visible()
        expect(page.get_by_role('textbox', name='chief complaint', exact=True)).to_have_value('Knee soreness since yesterday')
        patient.set_offline(False)
        with page.expect_response(lambda r: r.url.endswith('/corrections')) as corrected:
            page.get_by_role('button', name='Save chief complaint', exact=True).click()
        assert corrected.value.ok, corrected.value.text()
        assert corrected.value.request.post_data_json['value'] == 'Knee soreness since yesterday'
        assert snapshot()['clinical_state']['chief_complaint'] == 'Knee soreness since yesterday'
        print('PASS disconnected network: visible error, retained draft, successful retry', flush=True)
        print('PASS fresh registration, consent, AI avatar, speech, transcription and refresh', flush=True)
        page.locator('#document-upload').set_input_files([str(report), str(scan)])
        expect(page.get_by_role('button', name='Review extracted text')).to_have_count(2, timeout=120000)
        page.get_by_role('button', name='Review extracted text').first.click()
        expect(page.locator('pre')).not_to_be_empty()
        clinical = page.get_by_test_id('clinical-record')
        measurement_time = (datetime.now() - timedelta(minutes=2)).strftime('%Y-%m-%dT%H:%M')
        for kind, label, value, unit in [('VITAL', 'Pulse', '72', 'beats/min'), ('VITAL', 'Systolic blood pressure', '120', 'mmHg'), ('VITAL', 'Diastolic blood pressure', '80', 'mmHg'), ('VITAL', 'Temperature', '37', 'C'), ('VITAL', 'SpO2', '98', '%'), ('VITAL', 'Weight', '72', 'kg'), ('VITAL', 'Height', '180', 'cm'), ('TEST', 'Synthetic glucose test', '5.4', 'mmol/L')]:
            clinical.get_by_label('Type', exact=True).select_option(kind)
            clinical.get_by_label('Name', exact=True).fill(label)
            clinical.get_by_label('Measured value').fill(value)
            clinical.get_by_label('Unit', exact=True).fill(unit)
            clinical.get_by_label('Measurement time').fill(measurement_time)
            with page.expect_response(lambda r: r.url.endswith('/observations') and r.request.method == 'POST') as measured:
                clinical.get_by_role('button', name='Save measurement', exact=True).click()
            assert measured.value.status == 201, measured.value.text()
            expect(clinical.get_by_role('button', name='Save measurement', exact=True)).to_be_enabled()
        page.reload()
        expect(page.get_by_test_id('clinical-record')).to_contain_text('72 beats/min')
        expect(page.get_by_test_id('clinical-record')).to_contain_text('5.4 mmol/L')
        expect(page.get_by_test_id('clinical-record')).to_contain_text('22.22 kg/m2')
        expect(page.get_by_role('button', name='Review extracted text')).to_have_count(2)
        page.get_by_role('checkbox').check()
        page.locator('#submit-reviewed-intake').click()
        page.wait_for_url('**/patient/completed')
        print('PASS multiple documents, real OCR/extraction, measurements and submission', flush=True)

        def staff_login(context, role):
            view = context.new_page(); observe(view)
            view.goto(base + '/doctor/login')
            view.get_by_label('Hospital email').fill(role + '.demo@medikiosk.local')
            view.get_by_label('Password', exact=True).fill(os.getenv('DEMO_PASSWORD', 'DemoPass!2026'))
            view.get_by_role('button', name='Sign in securely').click()
            view.wait_for_url('**/' + ('admin' if role == 'admin' else 'doctor'))
            return view

        admin = browser.new_context(); administrator = staff_login(admin, 'admin')
        administrator.get_by_label('Assigned doctor').select_option('USR_DOCTOR_DEMO')
        administrator.get_by_label('Assigned patient').select_option(patient_id)
        with administrator.expect_response(lambda r: r.url.endswith('/admin/assignments')) as assignment:
            administrator.get_by_role('button', name='Assign doctor').click()
        assert assignment.value.ok, assignment.value.text()
        doctor = browser.new_context(); chart = staff_login(doctor, 'doctor')
        chart.goto(base + '/doctor/patients/' + patient_id)
        expect(chart.locator('#patient-name-header')).to_contain_text(name)
        expect(chart.get_by_test_id('clinical-record')).to_contain_text('72 beats/min')
        chart.locator('#edit-summary-btn').click()
        chart.locator('#edit-duration').fill('one day, confirmed during clinician review')
        with chart.expect_response(lambda r: r.url.endswith('/facts')) as clinician_correction:
            chart.locator('#save-edit-btn').click()
        assert clinician_correction.value.ok, clinician_correction.value.text()
        expect(chart.locator('#save-edit-btn')).not_to_be_visible()
        expect(chart.get_by_test_id('unified-clinical-record')).to_contain_text('one day, confirmed during clinician review')
        with chart.expect_response(lambda r: r.url.endswith('/ai-summary'), timeout=120000) as summary:
            chart.get_by_role('button', name='Generate grounded AI summary').click()
        assert summary.value.ok, summary.value.text()
        expect(chart.get_by_test_id('grounded-ai-summary')).to_be_visible()
        while chart.get_by_test_id('reconciliation-item').count():
            with chart.expect_response(lambda r: '/doctor/reconciliation/' in r.url and r.request.method == 'POST') as decision:
                chart.get_by_test_id('reconciliation-item').first.get_by_role('button', name='Reject incoming').click()
            assert decision.value.ok, decision.value.text()
            expect(chart.get_by_role('button', name='Generate grounded AI summary')).to_be_enabled()
        clinical = chart.get_by_test_id('clinical-record')
        clinical.get_by_role('button', name='Add medicine', exact=True).click()
        medicine = {'name': 'Synthetic study medicine', 'strength': '10 test units', 'dose': 'one test unit', 'frequency': 'once daily', 'duration': 'three days', 'route': 'oral', 'instructions': 'Synthetic medicine-specific instructions.'}
        for field, value in medicine.items():
            clinical.get_by_label('Medicine 1 ' + field, exact=True).fill(value)
        advice = 'Synthetic clinician advice entered during the complete workflow test.'
        clinical.get_by_label('Doctor advice / remedies').fill(advice)
        clinical.get_by_label('Follow-up date (optional)').fill('2026-09-22')
        clinical.get_by_label('I reviewed the recorded allergy information against every prescribed medicine.').check()
        with chart.expect_response(lambda r: r.url.endswith('/prescription')) as prescribed:
            clinical.get_by_role('button', name='Save prescription', exact=True).click()
        assert prescribed.value.ok, prescribed.value.text()
        chart.reload()
        expect(chart.get_by_label('Medicine 1 name', exact=True)).to_have_value(medicine['name'])
        chart.locator('#verify-summary-btn').click()
        with chart.expect_response(lambda r: r.url.endswith('/finalize')) as finalized:
            chart.locator('#confirm-verify-btn').click()
        assert finalized.value.ok, finalized.value.text()
        expect(chart.get_by_role('button', name='Download finalized medical PDF')).to_be_visible()
        expect(chart.get_by_role('button', name='Save prescription', exact=True)).not_to_be_visible()
        chart.reload()
        expect(chart.get_by_role('button', name='Review extracted text')).to_have_count(2)
        expect(chart.get_by_role('button', name='Retry', exact=True)).to_have_count(0)
        with chart.expect_download() as pdf_download:
            chart.get_by_role('button', name='Download finalized medical PDF').click()
        pdf_path = output / 'finalized-record.pdf'
        pdf_download.value.save_as(pdf_path)
        with pymupdf.open(pdf_path) as pdf:
            text = unicodedata.normalize('NFKC', ''.join(pdf[i].get_text() for i in range(len(pdf))))
            for expected in [name, *medicine.values(), advice, 'Knee soreness since yesterday', '72', '5.4', '22.22', 'BMI', 'Aspirin', 'Hemoglobin', '2026-09-22']:
                assert expected in text, (expected, text)
            assert all(abs(pdf[i].rect.width - 595) < 1 for i in range(len(pdf)))
            pdf[0].get_pixmap().save(output / 'opened-pdf-page.png')
        print('PASS clinician assignment/review, stored prescription, finalization, opened A4 PDF and contents', flush=True)
        page.goto(base + '/patient/follow-up')
        with page.expect_response(lambda r: r.url.endswith('/sessions'), timeout=120000) as started:
            page.get_by_role('button', name='Start check-in', exact=True).click()
        assert started.value.ok, started.value.text()
        expect(page.get_by_text('Stored treatment plan')).to_be_visible()
        expect(page.locator('main')).to_contain_text(medicine['name'])
        assert started.value.json()['next_question']['generation_method'] == 'ollama'
        follow_up_answer = 'My symptoms are getting worse since the consultation.'
        page.get_by_label('Follow-up response').fill(follow_up_answer)
        with page.expect_response(lambda r: r.url.endswith('/answers'), timeout=120000) as followed:
            page.get_by_role('button', name='Save response').click()
        assert followed.value.ok, followed.value.text()
        assert followed.value.json()['alerts']
        page.reload()
        expect(page.locator('main')).to_contain_text(follow_up_answer, timeout=120000)
        chart.reload()
        expect(chart.locator('main')).to_contain_text(follow_up_answer)
        with chart.expect_response(lambda r: r.url.endswith('/acknowledge')) as acknowledged:
            chart.get_by_role('button', name='Acknowledge').click()
        assert acknowledged.value.ok, acknowledged.value.text()
        assert not errors, errors
        assert not [r for r in requests if r['status'] >= 500], requests
        result = {'result': 'PASS', 'patient_id': patient_id, 'encounter_id': identifier, 'questions': len(record['answers']), 'states': states, 'mouth_range': [min(mouths), max(mouths)], 'pdf': str(pdf_path), 'browser_errors': errors, 'requests': requests}
        (output / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf8')
        chart.screenshot(path=str(output / 'doctor-finalized.png'), full_page=True)
        page.screenshot(path=str(output / 'follow-up.png'), full_page=True)
        print('PASS follow-up model question, patient response, refresh, timeline and clinician alert acknowledgement', flush=True)
        print(json.dumps({k: v for k, v in result.items() if k != 'requests'}, indent=2), flush=True)
        browser.close()


if __name__ == '__main__':
    main()
