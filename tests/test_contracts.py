import json
from pathlib import Path

from jsonschema import Draft202012Validator

from examples.demo import run_demo
from examples.export_contracts import MODELS

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"


def test_contracts_match_runtime_models():
    for name, model in MODELS.items():
        schema = json.loads((CONTRACTS / f"{name}.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        schema.pop("$schema")
        assert schema == model.model_json_schema()


def test_examples_validate_against_published_contracts():
    for demo in run_demo().values():
        for contract, key in [
            ("interview", "final_record"),
            ("interview_response", "first_response"),
            ("interview_response", "final_response"),
        ]:
            schema = json.loads((CONTRACTS / f"{contract}.schema.json").read_text(encoding="utf-8"))
            Draft202012Validator(schema).validate(demo[key])
