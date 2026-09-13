"""Real registration and explicit clinician assignment. Creates labelled synthetic data."""
import os
from uuid import uuid4
from playwright.sync_api import sync_playwright, expect

base=os.getenv('E2E_BASE_URL','http://127.0.0.1:3000')
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    context=browser.new_context()
    page=context.new_page()
    page.set_default_timeout(45000)
    page.goto(base+'/patient/identify')
    page.get_by_role('button',name='Create account',exact=True).click()
    page.get_by_label('Full name',exact=True).fill('Browser Registration (Synthetic)')
    page.get_by_label('Age',exact=True).fill('32')
    page.get_by_label('Email',exact=True).fill(f'browser-{uuid4().hex[:10]}@medikiosk.test')
    page.get_by_label('Password',exact=True).fill('SyntheticPass!2026')
    page.get_by_role('button',name='Create account and continue').click()
    page.wait_for_url('**/patient/language')
    patient=context.request.get(base+'/api/auth/me').json()['user']
    assert patient['role']=='PATIENT'
    assert context.request.get(base+'/api/patients/P1001').status==403

    def login(email,destination):
        page.goto(base+'/doctor/login')
        page.get_by_label('Hospital email').fill(email)
        page.get_by_label('Password',exact=True).fill(os.getenv('DEMO_PASSWORD','DemoPass!2026'))
        page.get_by_role('button',name='Sign in securely').click()
        page.wait_for_url(base+destination)

    login('doctor.demo@medikiosk.local','/doctor')
    assert context.request.get(base+f"/api/doctor/patients/{patient['patient_id']}/summary").status==403
    login('admin.demo@medikiosk.local','/admin')
    users=context.request.get(base+'/api/admin/users').json()
    doctor=next(user for user in users if user['email']=='doctor.demo@medikiosk.local')
    page.get_by_role('combobox',name='Assigned doctor',exact=True).select_option(doctor['user_id'])
    page.get_by_role('combobox',name='Assigned patient',exact=True).select_option(patient['patient_id'])
    with page.expect_response(lambda response:response.url.endswith('/admin/assignments')) as assigned:
        page.get_by_role('button',name='Assign doctor').click()
    assert assigned.value.ok,assigned.value.text()
    login('doctor.demo@medikiosk.local','/doctor')
    assert context.request.get(base+f"/api/doctor/patients/{patient['patient_id']}/summary").status==200
    print('PASS: browser registration, cross-patient denial, unassigned-doctor denial, explicit admin assignment, assigned-doctor access')
    browser.close()
