import ast
import json

from vibeedit.data import data_path


def test_all_catalog_python_examples_are_nonempty_valid_syntax():
    items = json.loads(data_path("catalog", "catalog.json").read_text())["items"]
    for item in items:
        assert item["examples"]["python"].strip(), item["id"]
        ast.parse(item["examples"]["python"], filename=item["id"])
        assert item["examples"]["javascript"].strip(), item["id"]
        assert item["prompts"] and all(prompt.strip() for prompt in item["prompts"]), item["id"]
