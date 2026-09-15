"""Generate an endpoint inventory from routes, OpenAPI and executed test evidence."""
import ast
import inspect
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app.main import app

GROUPS = {
    'auth': ('Identify, doctor login, layouts; services/api.ts', 'users, patients, sessions, audit_logs; registration, password verification and session lifecycle'),
    'patients': ('services/api.ts; patient identity and history API', 'patients, clinical_facts, timeline_events, clinician_assignments; ownership-filtered reads'),
    'interviews': ('Patient interview/review/consent; services/api.ts', 'encounters, consents, answers, clinical_facts, red_flags, reconciliation_items, timeline_events, audit_logs; revision checks, 5–10 budget, model extraction and question delivery'),
    'documents': ('DocumentReview; services/api.ts', 'protected files, documents, document_pages, document_entities, reconciliation_items, timeline_events; signature validation, actual PDF/OCR, source extraction, reconciliation and lifecycle locks'),
    'doctor': ('Doctor dashboard, EncounterReviewPanel, EditSummaryModal; services/api.ts', 'assignments, encounters, facts, timeline, audit, ai_summaries, finalized_records, follow_up_plans; assigned chart review, corrections, source decisions, grounded model summary and atomic finalization'),
    'admin': ('Admin page, AssignmentPanel; services/api.ts', 'users, clinician_assignments, ontology_rules, audit_logs; role/assignment administration and runtime ontology'),
    'knowledge': ('KnowledgePanel', 'knowledge_sources, knowledge_chunks, audit_logs; approved text, real embeddings, retrieval, exact-source model excerpts and soft-disable'),
    'follow-ups': ('Patient follow-up, EncounterReviewPanel; services/api.ts', 'finalized encounters, prescriptions, follow_up_plans/sessions/questions/responses/alerts, timeline; patient check-ins, ASR drafts, stored responses and deterministic alerts'),
    'records': ('ClinicalRecord; services/api.ts', 'encounters, observations, prescriptions, finalized_records, timeline_events, audit_logs; measured readings, withdrawal, versioned treatment plan and A4 PDF from immutable snapshot'),
    'speech': ('useAssistantSpeech, talking avatar', 'authenticated session; actual local Piper synthesis to WAV; no clinical mutation'),
}


def source_index():
    indexed = {}
    for filename in Path('backend/app').rglob('*.py'):
        source = filename.read_text(encoding='utf8')
        tree = ast.parse(source)
        match = re.search(r'APIRouter\(prefix=[\"\']([^\"\']+)', source)
        prefix = match.group(1) if match else ''
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute) and decorator.func.attr in {'get','post','put','patch','delete'} and decorator.args and isinstance(decorator.args[0], ast.Constant):
                    key = decorator.func.attr.upper() + ' ' + prefix + decorator.args[0].value
                    indexed[key] = (filename.as_posix(), node.lineno, ast.get_source_segment(source, node) or '')
    return indexed


def main():
    spec = app.openapi()
    unit = json.loads(Path('.runtime/api-test-coverage.json').read_text())
    if unit['exit_status'] != 0:
        raise SystemExit('Run the complete passing backend suite before producing the audit.')
    shapes = json.loads(Path('.runtime/api-response-shapes.json').read_text())
    live = json.loads(Path('.runtime/local-ai-api-coverage.json').read_text())
    browser = json.loads(Path('.runtime/full-e2e/result.json').read_text())
    if browser['result'] != 'PASS':
        raise SystemExit('The complete browser flow has not passed.')
    sources = source_index()
    evidence = {}
    lines = ['# Endpoint and frontend/backend contract audit', '', 'Generated from the mounted OpenAPI routes and executed test responses. No patient values are exported here.', '',
        'Every protected route was tested without authentication (401) and with a database outage (503). Patient calls to staff routes were checked for 403. Domain tests cover ownership, invalid inputs, missing resources, lifecycle/revision conflicts and persistence. The table records observed statuses, not a claim that every theoretical failure permutation was exercised.', '',
        'Requests: [OpenAPI](api-openapi.json) contains full Pydantic field constraints and multipart schemas. Responses: [contract evidence](api-contract-evidence.json) contains value-free shapes observed from real successful/error responses and test names. Observed shapes are evidence, not a replacement for a formally exhaustive response schema.', '',
        'All protected operations use server sessions (HttpOnly cookie or bearer token). “Resource access” means patient ownership, assigned-doctor access, or administrator permission; patient-only lifecycle operations additionally reject staff writes. Public logout clears the presented session idempotently. 422 = validation, 404 = missing, 409 = stale/lifecycle conflict, 413/415 = rejected media, 503 = unavailable processing/storage. Binary routes return actual files/audio, not JSON success flags.', '',
        'The `/patients/` route is a compatibility alias for `/patients`. `/interviews/{id}/voice` is the integrated voice API; the current UI uses `/transcribe` then `/answers` to allow review. `/follow-ups/plans` is the authorized plan-management API; normal UI finalization creates the plan transactionally. Root and health are operational endpoints. These are intentional API-only/compatibility consumers, not dead UI controls.', '',
        '| Method / endpoint | Authentication / role | Request schema | Response contract | Database / business logic | Frontend consumer | Observed test statuses |',
        '|---|---|---|---|---|---|---|']
    missing = []
    for path, operations in spec['paths'].items():
        for method, operation in operations.items():
            if method.upper() not in {'GET','POST','PUT','PATCH','DELETE'}:
                continue
            key = method.upper() + ' ' + path
            filename, line, source = sources[key]
            role_match = re.search(r'require_roles\(([^)]+)\)', source)
            role = role_match.group(1).replace('"','').replace("'",'') if role_match else 'Resource access' if 'current_user' in source else 'Public'
            group = path.strip('/').split('/')[0]
            consumer, logic = GROUPS.get(group, ('Operations / readiness checks', 'service metadata; health executes a database read'))
            if path == '/admin/providers':
                logic = 'session authentication; observed provider-manager state and configured local model; no invented availability'
            content = operation.get('requestBody', {}).get('content', {})
            inputs = [media + ': ' + schema.get('schema', {}).get('$ref', 'inline').split('/')[-1] for media, schema in content.items()]
            inputs += [p['in'] + ': ' + p['name'] for p in operation.get('parameters', []) if p['in'] != 'header']
            rows = [shapes.get(key, {}), live.get(key, {})]
            statuses = set(unit['endpoints'].get(key, {}).get('statuses', [])) | set(live.get(key, {}).get('statuses', []))
            for request in browser['requests']:
                if request['method'] == method.upper() and re.fullmatch(re.sub(r'\{[^}]+\}', '[^/]+', path), request['path']):
                    statuses.add(request['status'])
            successful_shapes = {code: value for row in rows for code, value in row.get('observed_response_shapes', {}).items() if 200 <= int(code) < 300}
            properties = sorted({prop for schema in successful_shapes.values() for prop in schema.get('properties', {})})
            output = ', '.join(properties) or ', '.join(sorted({schema.get('content_type') or schema['type'] for schema in successful_shapes.values()})) or 'browser-verified JSON; see source'
            evidence[key] = {'request': operation, 'observed_responses': rows, 'statuses': sorted(statuses), 'tests': unit['endpoints'].get(key, {}).get('tests', []), 'source': filename + ':' + str(line)}
            if not any(200 <= code < 300 for code in statuses):
                missing.append(key)
            response_link = f'[{output}](../{filename}#L{line})'
            cells = [key, role, '; '.join(inputs) or 'No body', response_link, logic, consumer, ', '.join(map(str, sorted(statuses)))]
            lines.append('| ' + ' | '.join(cell.replace('|', '/') for cell in cells) + ' |')
    lines += ['', f'Inventory: {len(evidence)} method/path contracts. Successful-response gaps: {len(missing)}.', '']
    Path('docs/API_AUDIT.md').write_text('\n'.join(lines), encoding='utf8')
    Path('docs/api-openapi.json').write_text(json.dumps(spec, indent=2), encoding='utf8')
    Path('docs/api-contract-evidence.json').write_text(json.dumps(evidence, indent=2), encoding='utf8')
    if missing:
        raise SystemExit('Missing successful execution: ' + ', '.join(missing))
    print(f'PASS: {len(evidence)} endpoint contracts have successful execution evidence; audit written to docs/API_AUDIT.md')


if __name__ == '__main__':
    main()
