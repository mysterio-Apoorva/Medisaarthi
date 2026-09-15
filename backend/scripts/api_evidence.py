"""Record status and value-free JSON shapes from actual test responses."""
import json
from pathlib import Path
import re


def shape(value):
    if value is None:
        return {'type': 'null'}
    if isinstance(value, dict):
        return {'type': 'object', 'properties': {key: shape(item) for key, item in value.items()}}
    if isinstance(value, list):
        variants = {json.dumps(shape(item), sort_keys=True) for item in value}
        return {'type': 'array', 'items': {'anyOf': [json.loads(item) for item in sorted(variants)]}}
    return {'type': 'boolean' if isinstance(value, bool) else 'number' if isinstance(value, (float, int)) else 'string'}


def observe(response, entries, paths):
    method, path = response.request.method, response.request.url.path
    template = next((template for template, operations in paths.items() if method.lower() in operations and re.fullmatch(re.sub(r'\{[^}]+\}', '[^/]+', template), path)), None)
    if template is None:
        return
    key = method + ' ' + template
    row = entries.setdefault(key, {'statuses': [], 'observed_response_shapes': {}})
    row['statuses'] = sorted(set(row['statuses'] + [response.status_code]))
    media = response.headers.get('content-type', '').split(';')[0]
    result = shape(response.json()) if media == 'application/json' and response.content else {'type': 'binary' if response.content else 'empty', 'content_type': media}
    previous = row['observed_response_shapes'].get(str(response.status_code))
    if previous is None or len(json.dumps(result)) > len(json.dumps(previous)):
        row['observed_response_shapes'][str(response.status_code)] = result


def save(entries, filename):
    destination = Path('.runtime') / filename
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(entries, indent=2), encoding='utf8')
