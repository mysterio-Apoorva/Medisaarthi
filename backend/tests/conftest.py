"""Isolate every test invocation before application modules resolve the database path."""
import os
from pathlib import Path
import tempfile
import json
import re

import pytest

test_root = Path(tempfile.mkdtemp(prefix='medikiosk-tests-'))
os.environ['DATABASE_URL'] = f'sqlite:///{test_root / "tests.sqlite3"}'
os.environ['DOCUMENT_UPLOAD_DIR'] = str(test_root / 'uploads')
os.environ['AI_PROVIDER'] = 'clinical_rules'
os.environ['SEED_DEMO_DATA'] = 'true'


def pytest_configure(config):
    if not config.option.basetemp:
        config.option.basetemp = str(test_root / 'pytest')


endpoint_results = {}
response_shapes = {}


@pytest.fixture(autouse=True)
def record_endpoint_coverage(monkeypatch, request):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    original = TestClient.request
    routes = [(method.upper(), path) for path, operations in app.openapi()['paths'].items() for method in operations]

    def observed(client, method, url, *args, **kwargs):
        response = original(client, method, url, *args, **kwargs)
        from backend.scripts.api_evidence import observe
        observe(response, response_shapes, app.openapi()['paths'])
        path = response.request.url.path
        for verb, template in routes:
            if verb == method.upper() and re.fullmatch(re.sub(r'\{[^}]+\}', '[^/]+', template), path):
                key = verb + ' ' + template
                item = endpoint_results.setdefault(key, {'statuses': set(), 'tests': set()})
                item['statuses'].add(response.status_code)
                item['tests'].add(request.node.nodeid)
                break
        return response

    monkeypatch.setattr(TestClient, 'request', observed)


def pytest_sessionfinish(session, exitstatus):
    from backend.scripts.api_evidence import save
    save(response_shapes, 'api-response-shapes.json')
    output = Path('.runtime/api-test-coverage.json')
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps({'exit_status': exitstatus, 'endpoints': {key: {field: sorted(values) for field, values in item.items()} for key, item in sorted(endpoint_results.items())}}, indent=2), encoding='utf8')
