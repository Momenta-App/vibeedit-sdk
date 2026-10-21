import json
import posixpath
import re
import tomllib
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).parents[2]
GUIDES = {
    "PROJECTS.md", "MODELS.md", "COMPANION.md", "MYRIOGRAPH.md",
    "OPERATIONS.md", "SECURITY.md", "SKILLS.md", "HTML_MOTION_RUNTIME.md",
    "PYTHON_EFFECTS_TRANSITIONS.md",
}


def test_wheel_customer_docs_are_an_explicit_public_allowlist():
    includes = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    expected = {f"docs/{name}": f"vibeedit/data/docs/{name}" for name in GUIDES}
    actual = {source: target for source, target in includes.items() if source.strip("/") == "docs" or source.strip("/").startswith("docs/") or target.rstrip("/") == "vibeedit/data/docs" or target.startswith("vibeedit/data/docs/")}
    assert actual == expected
    assert includes["README.md"] == "vibeedit/data/README.md"
    resources = wheel_resources(includes)
    assert {name for name in resources if name.startswith("vibeedit/data/docs/")} == set(expected.values())
    assert not any("/docs/launch/" in name or "/docs/evidence/" in name or "/docs/experiments/" in name for name in resources)


def test_bundled_customer_guide_links_resolve_without_the_checkout():
    includes = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
    resources = wheel_resources(includes)
    guides = {f"vibeedit/data/docs/{name}" for name in GUIDES} | {"vibeedit/data/README.md", "vibeedit/data/companion/README.md"}
    for name in sorted(guides):
        for target in markdown_targets(resources[name].read_text(encoding="utf-8")):
            url = urlsplit(target)
            if url.scheme or url.netloc or not url.path:
                continue
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), unquote(url.path)))
            assert resolved in resources, f"bundled guide link needs an included resource or pinned online URL: {name} -> {target}"


def test_installed_skill_references_stay_inside_the_copied_skill():
    for index in ("index.json", "owned.json"):
        for skill in json.loads((ROOT / "skills" / index).read_text(encoding="utf-8"))["skills"]:
            directory = ROOT / "skills" / skill["path"]
            for document in directory.rglob("*.md"):
                text = document.read_text(encoding="utf-8")
                for target in markdown_targets(text):
                    url = urlsplit(target)
                    if url.scheme or url.netloc or not url.path:
                        continue
                    resolved = (document.parent / unquote(url.path)).resolve()
                    assert resolved.is_relative_to(directory.resolve()) and resolved.is_file(), f"installed skill link escapes or is missing: {document.relative_to(ROOT)} -> {target}"
                # These commands/references are explicitly rooted at SKILL_DIR.
                for target in re.findall(r"(?:scripts|references)/[A-Za-z0-9_.\-/]+\.(?:py|json|md|sh)\b", text):
                    assert (directory / target).is_file(), f"installed skill support file is missing: {document.relative_to(ROOT)} -> {target}"


def markdown_targets(text):
    return re.findall(r"(?<!!)\[[^\]]*\]\(([^)]+)\)", text)


def wheel_resources(includes):
    resources = {}
    for source, destination in includes.items():
        path = ROOT / source
        if path.is_file():
            resources[destination] = path
            continue
        for member in path.rglob("*"):
            if member.is_file() and "__pycache__" not in member.parts and member.suffix != ".pyc":
                resources[destination + "/" + member.relative_to(path).as_posix()] = member
    return resources
