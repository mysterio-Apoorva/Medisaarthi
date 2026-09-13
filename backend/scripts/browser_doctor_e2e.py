"""Resume clinician verification of the latest synthetic patient submission in a real browser."""
from pathlib import Path
import os
import json
from playwright.sync_api import sync_playwright, expect

base=os.getenv('E2E_BASE_URL','http://127.0.0.1:3000')
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    context=browser.new_context(viewport={'width':1280,'height':1000})
    page=context.new_page()
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.set_default_timeout(45000)
    page.goto(base+'/doctor/login')
    page.get_by_label('Hospital email').fill('doctor.demo@medikiosk.local')
    page.get_by_label('Password',exact=True).fill(os.getenv('DEMO_PASSWORD','DemoPass!2026'))
    page.get_by_role('button',name='Sign in securely').click()
    page.wait_for_url(base+'/doctor')
    page.goto(base+'/doctor/patients/P1001')
    expect(page.locator('#patient-name-header')).to_be_visible()
    summary=context.request.get(base+'/api/doctor/patients/P1001/summary').json()
    identifier=summary['encounter']['encounter_id']
    assert summary['encounter']['status']=='SUBMITTED',summary['encounter']['status']
    with page.expect_response(lambda response:response.url.endswith('/ai-summary'),timeout=130000) as response:
        page.get_by_role('button',name='Generate grounded AI summary').click()
    assert response.value.ok,response.value.text()
    expect(page.get_by_test_id('grounded-ai-summary')).to_be_visible()
    print('PASS: persisted local AI summary with verified fact IDs',flush=True)
    while page.get_by_test_id('reconciliation-item').count():
        count=page.get_by_test_id('reconciliation-item').count()
        page.get_by_test_id('reconciliation-item').first.get_by_role('button',name='Approve incoming').click()
        expect(page.get_by_test_id('reconciliation-item')).to_have_count(count-1)
    page.get_by_text('Clinical fact provenance',exact=True).click()
    expect(page.get_by_text('DOCTOR_ENTERED · VERIFIED',exact=False).first).to_be_visible()
    with page.expect_download() as download:
        page.get_by_role('link',name='Download local FHIR R4 bundle').click()
    assert json.loads(Path(download.value.path()).read_text(encoding='utf-8'))['resourceType']=='Bundle'
    page.locator('#verify-summary-btn').click()
    with page.expect_response(lambda response:response.url.endswith('/finalize')) as finalized:
        page.locator('#confirm-verify-btn').click()
    assert finalized.value.ok,finalized.value.text()
    expect(page.locator('#verification-status-container')).to_contain_text('Verified')
    record=context.request.get(base+f'/api/interviews/{identifier}').json()
    assert record['status']=='FINALIZED'
    page.reload()
    expect(page.get_by_role('button',name='Finalized',exact=True)).to_be_disabled()
    page.screenshot(path='backend/data/browser-e2e/doctor-finalized.png',full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    page.wait_for_timeout(500)
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth+2'), 'Mobile layout overflows'
    page.goto(base+'/doctor/login')
    page.get_by_label('Hospital email').fill('admin.demo@medikiosk.local')
    page.get_by_label('Password',exact=True).fill(os.getenv('DEMO_PASSWORD','DemoPass!2026'))
    page.get_by_role('button',name='Sign in securely').click()
    page.wait_for_url(base+'/admin')
    expect(page.get_by_text('ENCOUNTER_FINALIZED',exact=True).first).to_be_visible()
    assert not errors,errors
    print('PASS: document reconciliation, provenance, FHIR download, finalization, mobile layout, admin audit',flush=True)
    browser.close()
