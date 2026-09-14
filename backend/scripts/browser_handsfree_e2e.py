"""Real browser PCM -> AudioWorklet -> Whisper -> intake -> Piper proof.

Synthetic Piper patient audio replaces the physical microphone source only.
No HTTP response, ASR transcript, TTS result or clinical result is mocked.
Run with --scenario normal|silence|unclear|long|limit|redflag|permission|hindi.
"""
from __future__ import annotations
import argparse
import base64
import io
import json
import os
from pathlib import Path
import sys
import time
import wave
import hashlib
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app.tts import synthesize
from playwright.sync_api import sync_playwright


def wav_parts(parts, language='en'):
    cache = Path('backend/data/handsfree-e2e/audio')
    cache.mkdir(parents=True, exist_ok=True)
    cache_file = cache / (hashlib.sha256(json.dumps([parts, language], ensure_ascii=False).encode()).hexdigest() + '.wav')
    if cache_file.exists(): return base64.b64encode(cache_file.read_bytes()).decode()
    output = io.BytesIO()
    with wave.open(output, 'wb') as target:
        rate = 22050
        initialized = False
        for part in parts:
            if isinstance(part, (int, float)):
                target.writeframes(b'\x00\x00' * int(rate * part))
            else:
                with wave.open(io.BytesIO(synthesize(part, language)), 'rb') as source:
                    rate = source.getframerate()
                    if not initialized:
                        target.setparams(source.getparams()); initialized = True
                    target.writeframes(source.readframes(source.getnframes()))
    cache_file.write_bytes(output.getvalue())
    return base64.b64encode(output.getvalue()).decode()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scenario', default='normal')
    scenario = parser.parse_args().scenario
    if scenario == 'suite':
        for name in ('normal', 'silence', 'unclear', 'long', 'limit', 'redflag', 'permission', 'hindi', 'documents', 'correction', 'correction_error', 'autoplay'):
            subprocess.run([sys.executable, '-u', '-X', 'utf8', __file__, '--scenario', name], check=True)
        return
    base = os.getenv('E2E_BASE_URL', 'http://127.0.0.1:3000')
    output = Path('backend/data/handsfree-e2e'); output.mkdir(parents=True, exist_ok=True)
    language = 'hi' if scenario == 'hindi' else 'en'
    answers = [
        ['My knee is sore since yesterday.', 2, 'The soreness is three out of ten.'],
        ['No medical conditions. No medicines. No known allergies.'],
        ['None.'], ['None.'], ['Nothing else.'],
    ]
    if scenario == 'long':
        answers[0] = ['My knee is sore since yesterday.', 2,
                      'I noticed it in the evening after coming back from work. I walked to the shops and back home. '
                      'It was uncomfortable when I went upstairs. I sat down for a while, and then walked around my room. '
                      'I slept overnight and noticed the same soreness when I woke up. I would like the doctor to know that. '
                      'The soreness is three out of ten.']
    if scenario == 'redflag': answers[0] = ['I have chest pain since yesterday and I am short of breath.']
    if scenario == 'documents': answers[1:3] = [['No medical conditions. No known allergies.'], ['Yes, that is correct.']]
    if scenario == 'hindi':
        answers = [['मेरे घुटने में कल से दर्द है। दर्द तीन है, दस में से।'], ['कोई पुरानी बीमारी नहीं है। कोई दवा नहीं लेता। कोई एलर्जी नहीं है।'], ['नहीं।']]
    fixtures = []
    for i, answer in enumerate(answers):
        print(f'Preparing real patient audio {i + 1}', flush=True)
        fixtures.append(wav_parts(answer, language))
    unknown = wav_parts(['I do not know.'])
    with sync_playwright() as p:
        print('Launching browser', flush=True)
        policy = 'document-user-activation-required' if scenario == 'autoplay' else 'no-user-gesture-required'
        browser = p.chromium.launch(channel='msedge', headless=True, args=['--autoplay-policy=' + policy, '--use-fake-ui-for-media-stream'])
        context = browser.new_context(permissions=[] if scenario == 'autoplay' else ['microphone'], viewport={'width':1280,'height':960})
        if scenario == 'autoplay':
            # Explicit browser-policy fault injection: no audio/ASR/server result is mocked.
            # Headless Edge may exempt localhost from autoplay restrictions even with its flag.
            context.add_init_script(script='''
              window.__audioActivated = false;
              document.addEventListener('pointerdown', () => { window.__audioActivated = true; }, {once:true});
              const NativeAudioContext = window.AudioContext;
              window.AudioContext = class extends NativeAudioContext {
                get state() { return window.__audioActivated ? super.state : 'suspended'; }
                resume() { return window.__audioActivated ? super.resume() : new Promise(() => {}); }
              };
            ''')
        # Isolated synthetic patient per run; existing user encounters are never reused.
        registration = context.request.post(base + '/api/auth/register', data={
            'name':'Synthetic Handsfree ' + scenario, 'age':30, 'gender':'Other', 'language':language,
            'email':f'handsfree.{scenario}.{time.time_ns()}@medikiosk.test', 'password':'SyntheticPass!2026'})
        assert registration.ok, registration.text()
        print('Registered synthetic patient', flush=True)
        patient_id = registration.json()['patient_id']
        consent = context.request.post(base + '/api/interviews/consents', data={'patient_id':patient_id}).json()['consent_id']
        if scenario == 'documents':
            import pymupdf
            started = context.request.post(base + '/api/interviews/start', data={'patient_id':patient_id,'language':language,'consent_id':consent}).json()
            context.request.post(base + '/api/interviews/consents', data={'patient_id':patient_id,'consent_type':'DOCUMENT_PROCESSING'})
            pdf = pymupdf.open(); sheet = pdf.new_page()
            sheet.insert_text((72,72), 'SYNTHETIC PRESCRIPTION\nTablet Metformin 500 mg twice daily')
            upload = context.request.post(base + '/api/documents/encounters/' + started['encounter_id'], multipart={'file':{'name':'synthetic-prescription.pdf','mimeType':'application/pdf','buffer':pdf.tobytes()}})
            pdf.close(); assert upload.status == 201, upload.text()
        context.add_init_script(script='''
          if (location.protocol === 'http:' && window === window.top) {
          localStorage.setItem('medisaarthi_current_patient_id', %s);
          localStorage.setItem('medisaarthi_current_consent_id', %s);
          localStorage.setItem('medisaarthi_selected_lang', %s);
          localStorage.setItem('medisaarthi_care_mode', 'MODERN');
          window.__voiceStates = []; window.__captureCount = 0; window.__overlap = false;
          navigator.mediaDevices.getUserMedia = async () => {
            if (document.querySelector('[data-testid="talking-avatar"]')?.dataset.state === 'speaking') window.__overlap = true;
            const n = window.__captureCount++;
            const data = await window.patientAudio(n);
            if (data === 'denied') throw new DOMException('Synthetic permission-denial test', 'NotAllowedError');
            const ctx = new AudioContext(); await ctx.resume();
            const destination = ctx.createMediaStreamDestination();
            let source;
            if (data === 'tone') {
              source = ctx.createOscillator(); source.frequency.value = 440;
              const gain = ctx.createGain(); gain.gain.value = .15;
              source.connect(gain); gain.connect(destination); source.start(ctx.currentTime + .5); source.stop(ctx.currentTime + 2);
            } else if (data !== 'silence') {
              const raw = Uint8Array.from(atob(data), c => c.charCodeAt(0));
              const audio = await ctx.decodeAudioData(raw.buffer);
              source = ctx.createBufferSource(); source.buffer = audio; source.connect(destination);
              source.start(ctx.currentTime + .5);
            }
            const track = destination.stream.getAudioTracks()[0]; const stop = track.stop.bind(track);
            track.stop = () => { stop(); try { source?.stop(); } catch {} void ctx.close(); };
            return destination.stream;
          };
          new MutationObserver(() => {
            const state = document.querySelector('[data-testid="hands-free-interview"]')?.dataset.state;
            if (state && window.__voiceStates.at(-1) !== state) window.__voiceStates.push(state);
          }).observe(document, {subtree:true, attributes:true, attributeFilter:['data-state']});
          }
        ''' % (json.dumps(patient_id), json.dumps(consent), json.dumps(language)))
        def audio_for(n):
            if scenario == 'permission': return 'denied'
            if scenario == 'silence' and n == 0: return 'silence'
            if scenario == 'unclear' and n == 0: return 'tone'
            if scenario == 'limit': return unknown
            index = n - (1 if scenario in ('silence','unclear') else 0)
            return fixtures[min(index, len(fixtures)-1)]
        context.expose_binding('patientAudio', lambda source, n: audio_for(n))
        page = context.new_page(); errors = []; responses = []; mouths = []
        if scenario == 'correction_error':
            failure = {'sent':False}
            def fail_once(route):
                if not failure['sent']:
                    failure['sent'] = True; route.abort('connectionfailed')
                else: route.continue_()
            page.route('**/answers', fail_once)
        page.on('pageerror', lambda e: (errors.append(str(e)), print('Browser error: ' + str(e), flush=True)))
        def response_received(response):
            if response.url.endswith(('/answers','/transcribe','/speech/synthesize')):
                info = {'path':response.url.split('/api')[-1], 'status':response.status}
                if response.url.endswith(('/answers','/transcribe')):
                    try: data = response.json()
                    except Exception: data = {}
                    info.update({k:data[k] for k in ('transcript','revision','question_budget','clinical_state','ai_warning') if k in data})
                responses.append(info)
                print(json.dumps(info, ensure_ascii=False), flush=True)
        page.on('response', response_received)
        page.goto(base + '/patient/interview')
        print('Interview opened', flush=True)
        deadline = time.monotonic() + (900 if scenario == 'limit' else 600)
        previous_state = None
        corrected = False
        activated = False
        retried = False
        while time.monotonic() < deadline:
            state = page.locator('[data-testid="hands-free-interview"]').get_attribute('data-state') if page.locator('[data-testid="hands-free-interview"]').count() else None
            if state != previous_state: print('State: ' + str(state), flush=True); previous_state = state
            if page.locator('[data-testid="avatar-mouth"]').count(): mouths.append(float(page.locator('[data-testid="avatar-mouth"]').get_attribute('ry')))
            if state in ('MICROPHONE_ERROR', 'SAFETY_PAUSE', 'COMPLETED'): break
            if '/patient/review' in page.url: break
            if state == 'TTS_ERROR' and scenario == 'autoplay' and not activated:
                page.get_by_role('button', name='Start', exact=True).click(); activated = True
            elif state == 'AI_ERROR' and scenario == 'correction_error' and not retried:
                page.get_by_role('button', name='Use this answer', exact=True).click(); retried = True
            elif state in ('AI_ERROR', 'TTS_ERROR'): raise AssertionError(page.locator('main').inner_text())
            if state == 'VALIDATING' and scenario.startswith('correction') and not corrected:
                page.get_by_role('button', name='Correct transcription', exact=True).click()
                page.locator('#patient-answer-input').fill('My knee is sore since yesterday, 2 out of 10.')
                page.get_by_role('button', name='Use this answer', exact=True).click(); corrected = True
            page.wait_for_timeout(150)
        identifier = page.evaluate("localStorage.getItem('medisaarthi_current_interview_id')")
        snapshot = context.request.get(base + '/api/interviews/' + identifier).json()
        states = page.evaluate('window.__voiceStates'); overlap = page.evaluate('window.__overlap')
        page.screenshot(path=str(output / (scenario + '.png')), full_page=True)
        result = {'scenario':scenario,'encounter_id':identifier,'question_budget':snapshot['question_budget'],
                  'answers':[a['answer_text'] for a in snapshot['answers']], 'states':states, 'mouth_range':[min(mouths),max(mouths)],
                  'overlap':overlap, 'browser_errors':errors, 'responses':responses}
        (output / (scenario + '.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2), encoding='utf-8')
        assert not errors and not overlap, result
        if scenario == 'permission':
            assert 'MICROPHONE_ERROR' in states and len(snapshot['answers']) == 0
        elif scenario == 'redflag':
            assert 'SAFETY_PAUSE' in states and snapshot['priority_flags'] and len(snapshot['answers']) == 1
        else:
            assert snapshot['status'] == 'PATIENT_REVIEW', result
            assert 5 <= len(snapshot['answers']) <= 10
            if scenario == 'normal':
                assert len(snapshot['answers']) == 5, result
                assert 'yesterday' in snapshot['answers'][0]['answer_text'].lower()
                assert 'three' in snapshot['answers'][0]['answer_text'].lower() or '3' in snapshot['answers'][0]['answer_text']
            if scenario == 'limit': assert len(snapshot['answers']) == 10
            if scenario == 'documents':
                assert any('Metformin' in a['question_text'] for a in snapshot['answers'])
                assert any('metformin' in value.lower() for value in snapshot['clinical_state']['medications'])
            if scenario.startswith('correction'):
                assert snapshot['answers'][0]['answer_text'] == 'My knee is sore since yesterday, 2 out of 10.'
                assert snapshot['clinical_state']['severity'] == 2
            if scenario == 'correction_error': assert retried and len(snapshot['answers']) == 5
            if scenario == 'autoplay': assert activated and 'TTS_ERROR' in states
            if scenario == 'hindi':
                import re
                assert all(not re.search(r'[\u0600-\u06ff]', answer['answer_text']) for answer in snapshot['answers'])
                assert any(re.search(r'[\u0900-\u097f]', answer['answer_text']) for answer in snapshot['answers'])
                assert snapshot['clinical_state'].get('severity') == 3, result
            if scenario == 'unclear': assert any(r['status'] == 422 for r in responses)
            assert max(mouths) - min(mouths) > .3
        print('PASS ' + scenario, flush=True)
        browser.close()


if __name__ == '__main__': main()
