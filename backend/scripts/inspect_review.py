from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    context=browser.new_context()
    base='http://127.0.0.1:3000'
    context.request.post(base+'/api/auth/login',data={'email':'doctor.demo@medikiosk.local','password':'DemoPass!2026'})
    record=context.request.get(base+'/api/doctor/patients/P1001/summary').json()
    identifier=record['encounter']['encounter_id']
    context.request.post(base+'/api/auth/login',data={'email':'patient.demo@medikiosk.local','password':'DemoPass!2026'})
    page=context.new_page()
    page.on('pageerror',lambda error:print('BROWSER ERROR:',error))
    page.goto(base)
    page.evaluate("id => {localStorage.setItem('medisaarthi_current_interview_id',id);localStorage.setItem('medisaarthi_current_patient_id','P1001')}",identifier)
    page.goto(base+'/patient/review')
    page.wait_for_timeout(4000)
    print(page.locator('main').inner_text()[:5000])
    print(page.locator('main').aria_snapshot()[:7000])
    browser.close()
