"""Read-only chart persistence and responsive checks against the synthetic demo."""
import os
from playwright.sync_api import sync_playwright, expect

base = os.getenv('E2E_BASE_URL', 'http://127.0.0.1:3000')
with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    page = browser.new_page(viewport={'width': 1280, 'height': 1000})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(base + '/doctor/login')
    page.get_by_label('Hospital email').fill('doctor.demo@medikiosk.local')
    page.get_by_label('Password', exact=True).fill(os.getenv('DEMO_PASSWORD', 'DemoPass!2026'))
    page.get_by_role('button', name='Sign in securely').click()
    page.wait_for_url(base + '/doctor')
    page.goto(base + '/doctor/patients/P1001')
    expect(page.get_by_role('button', name='Finalized', exact=True)).to_be_disabled(timeout=45000)
    page.screenshot(path='backend/data/browser-e2e/doctor-finalized.png', full_page=True)
    page.set_viewport_size({'width': 390, 'height': 844})
    expect(page.locator('#patient-name-header')).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 2'), 'Chart overflows mobile viewport'
    page.screenshot(path='backend/data/browser-e2e/doctor-mobile.png', full_page=True)
    assert not errors, errors
    print('PASS: finalized chart survives fresh login/reload; mobile chart fits; no browser runtime errors')
    browser.close()
