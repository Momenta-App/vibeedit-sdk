from __future__ import annotations

import json
from functools import lru_cache

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from vibeedit.data import data_path
from vibeedit.spec import JSONObject


class CompositionValidationError(ValueError):
    pass


@lru_cache(maxsize=1)
def composition_validator() -> Draft202012Validator:
    schema = json.loads(data_path("schema", "composition.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_composition(spec: JSONObject) -> None:
    errors = sorted(composition_validator().iter_errors(spec), key=lambda error: tuple(str(part) for part in error.absolute_path))
    if not errors:
        return
    lines = [f"{_path(error)}: {error.message}" for error in errors]
    raise CompositionValidationError("invalid CompositionSpec\n" + "\n".join(lines))


def _path(error: ValidationError | SchemaError) -> str:
    if not error.absolute_path:
        return "$"
    return "$" + "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.absolute_path)


def canonical_json(spec: JSONObject) -> str:
    return json.dumps(spec, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

