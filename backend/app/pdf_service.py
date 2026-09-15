"""Render escaped database values into an actual paginated A4 PDF."""
import html
import json

import pymupdf


def render_record(record: dict) -> bytes:
    def safe(value):
        return html.escape(str(value))

    def section(title, rows):
        return f'<h2>{safe(title)}</h2>' + ''.join(f'<p>{safe(row)}</p>' for row in rows)

    patient, encounter, prescription = record['patient'], record['encounter'], record['prescription']
    body = '<h1>MediKiosk medical record</h1>'
    body += section('Patient and encounter', [f"{patient['name']} | {patient['patient_id']}", f"Age: {patient['age']} | Gender: {patient['gender']}", encounter['encounter_id'], f"Finalized: {encounter['finalized_at']} by {record['finalized_by']}"])
    body += section('Clinical history', [f"{r['field_name']}: {json.loads(r['value_json'])} | {r['source']} | {r['status']}" for r in record['clinical_facts'] if not r['superseded_at']])
    body += section('Interview', [f"Question: {r['question_text']} Answer: {r['answer_text']}" for r in record['answers']])
    body += section('Tests and vitals', [f"{r['name']}: {r['value']} {r['unit']} | {r['measured_at']} | {r['source']}" + (f" | Calculation sources: {r['metadata_json']}" if r.get('metadata_json') and r['source'] == 'CALCULATED' else '') for r in record['observations'] if not r['voided_at']])
    body += section('Documents', [f"{r['original_name']} | {r['classification']} | {r['processing_status']} | {r['error_code'] or ''}" for r in record['documents']])
    body += section('Document findings', [f"{json.loads(r['value_json'])} | page {r['page_number']} | {r['verification_status']} | evidence: {r['evidence']}" for r in record['document_entities']])
    body += section('Prescription', [f"{m['name']} | Strength: {m.get('strength') or 'Not recorded'} | Dose: {m['dose']} | Frequency: {m['frequency']} | Duration: {m['duration']} | Route: {m['route']} | Instructions: {m.get('instructions') or 'Not recorded'}" for m in prescription['medicines']])
    if prescription.get('allergy_review'):
        review = prescription['allergy_review']
        body += section('Prescription allergy review', [f"Recorded allergy information: {review['allergies'] if review['allergies'] is not None else 'Not recorded'}", f"Reviewed by {prescription['doctor_name']} at {review['reviewed_at']}"])
    body += section('Doctor advice and follow-up', [prescription['advice'], prescription['no_medicines_reason'] or '', f"Follow-up: {prescription['follow_up_at'] or 'Not specified by doctor'}", f"Prescriber: {prescription['doctor_name']}"])
    body += section('Safety flags', [f"{r['severity']}: {r['message']}" for r in record['red_flags']])
    body += section('Timeline at finalization', [f"{r['occurred_at']} | {r['title']} | {r['detail'] or ''} | {r['source']}" for r in record['timeline_events']])
    import io
    stream = io.BytesIO()
    writer = pymupdf.DocumentWriter(stream)
    # MuPDF 1.28 can overflow later pages at a 10pt base size. Its native
    # 12pt layout is covered by the long-record pagination regression.
    story = pymupdf.Story(html=body, em=12, user_css='body { font-family: sans-serif; } h1 { font-size: 19pt; } h2 { font-size: 13pt; } p { overflow-wrap: anywhere; }')
    page = pymupdf.paper_rect('a4')
    region = page + (36, 36, -36, -36)
    try:
        for _ in range(500):
            device = writer.begin_page(page)
            more, filled = story.place(region)
            if filled[3] > page.height or filled[2] > page.width:
                raise ValueError('PDF layout exceeds the page; refusing a clipped record')
            story.draw(device)
            writer.end_page()
            if not more:
                break
        else:
            raise ValueError('Medical record exceeds the PDF page limit')
    finally:
        writer.close()
    content = stream.getvalue()
    with pymupdf.open(stream=content, filetype='pdf') as document:
        if not document.page_count or not document[0].get_text().strip():
            raise ValueError('The generated PDF is empty')
    return content
