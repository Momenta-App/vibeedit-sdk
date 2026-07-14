from __future__ import annotations

import argparse
import json
import shutil
import sys
import webbrowser
from pathlib import Path

from vibeedit.cache import cache_root
from vibeedit.capabilities import doctor
from vibeedit.data import data_path
from vibeedit.ffmpeg import probe
from vibeedit.examples import create_example
from vibeedit.render import render
from vibeedit.spec import Canvas, Composition, FrameRate
from vibeedit.validation import validate_composition
from vibeedit.verify import verify_output
from vibeedit.catalog import list_catalog, search_catalog
from vibeedit.skills import check_skill, install_skill, list_skills, remove_skill, update_skill
from vibeedit.version import VERSION


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (OSError, ValueError, RuntimeError, NotImplementedError) as error:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": str(error)}))
        else:
            print(f"vibeedit: {error}", file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vibeedit", description="VibeEdit video production CLI")
    parser.add_argument("--version", action="version", version=f"vibeedit {VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="create a validated CompositionSpec")
    init.add_argument("path", nargs="?", default="composition.json")
    init.add_argument("--width", type=int, default=1920)
    init.add_argument("--height", type=int, default=1080)
    init.add_argument("--fps", default="30/1")
    init.add_argument("--frames", type=int, default=150)
    init.add_argument("--id", default="composition")
    init.add_argument("--json", action="store_true")
    init.set_defaults(handler=_init)

    setup = sub.add_parser("setup", help="prepare optional pinned runtimes without hidden downloads")
    setup.add_argument("--all", action="store_true")
    setup.add_argument("--browser", action="store_true")
    setup.add_argument("--effects", action="store_true")
    setup.add_argument("--vision", action="store_true")
    setup.add_argument("--sam", action="store_true")
    setup.add_argument("--json", action="store_true")
    setup.set_defaults(handler=_setup)

    doctor_parser = sub.add_parser("doctor", help="report exact local capabilities")
    doctor_parser.add_argument("--json", action="store_true")
    doctor_parser.set_defaults(handler=_doctor)

    inspect = sub.add_parser("inspect", help="inspect a CompositionSpec or media file")
    inspect.add_argument("path")
    inspect.add_argument("--json", action="store_true")
    inspect.set_defaults(handler=_inspect)

    catalog = sub.add_parser("catalog", help="search or open the canonical catalog")
    catalog_sub = catalog.add_subparsers(dest="catalog_command", required=True)
    catalog_list = catalog_sub.add_parser("list", help="list catalog items")
    catalog_list.add_argument("--json", action="store_true")
    catalog_list.set_defaults(handler=_catalog_list)
    catalog_search = catalog_sub.add_parser("search", help="search catalog items")
    catalog_search.add_argument("query")
    catalog_search.add_argument("--json", action="store_true")
    catalog_search.set_defaults(handler=_catalog_search)
    catalog_open = catalog_sub.add_parser("open", help="open the generated local catalog")
    catalog_open.add_argument("--no-browser", action="store_true")
    catalog_open.add_argument("--json", action="store_true")
    catalog_open.set_defaults(handler=_catalog_open)

    examples = sub.add_parser("examples", help="list or create executable examples")
    examples_sub = examples.add_subparsers(dest="examples_command", required=True)
    examples_list = examples_sub.add_parser("list")
    examples_list.add_argument("--json", action="store_true")
    examples_list.set_defaults(handler=_examples_list)
    examples_create = examples_sub.add_parser("create")
    examples_create.add_argument("id")
    examples_create.add_argument("destination", nargs="?", default=".")
    examples_create.add_argument("--json", action="store_true")
    examples_create.set_defaults(handler=_examples_create)

    skills = sub.add_parser("skills", help="manage harness-compatible skills")
    skills_sub = skills.add_subparsers(dest="skills_command", required=True)
    skills_list = skills_sub.add_parser("list")
    skills_list.add_argument("--json", action="store_true")
    skills_list.set_defaults(handler=_skills_list)
    skills_install = skills_sub.add_parser("install")
    skills_install.add_argument("id")
    skills_install.add_argument("--harness", choices=["agents", "codex", "claude", "opencode"], required=True)
    skills_install.add_argument("--scope", choices=["project", "user"], default="project")
    skills_install.add_argument("--json", action="store_true")
    skills_install.set_defaults(handler=_skills_install)
    for command, handler in (("check", _skills_check), ("update", _skills_update), ("remove", _skills_remove)):
        action = skills_sub.add_parser(command)
        action.add_argument("id")
        action.add_argument("--harness", choices=["agents", "codex", "claude", "opencode"], required=True)
        action.add_argument("--scope", choices=["project", "user"], default="project")
        action.add_argument("--json", action="store_true")
        action.set_defaults(handler=handler)

    validate = sub.add_parser("validate", help="validate a CompositionSpec")
    validate.add_argument("path")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(handler=_validate)

    preview = sub.add_parser("preview", help="render a deterministic preview")
    preview.add_argument("path")
    preview.add_argument("--output", default="preview.mp4")
    preview.add_argument("--json", action="store_true")
    preview.set_defaults(handler=_render)

    render_parser = sub.add_parser("render", help="render a CompositionSpec")
    render_parser.add_argument("path")
    render_parser.add_argument("--output")
    render_parser.add_argument("--json", action="store_true")
    render_parser.set_defaults(handler=_render)

    verify = sub.add_parser("verify", help="verify a rendered output")
    verify.add_argument("output")
    verify.add_argument("--spec")
    verify.add_argument("--json", action="store_true")
    verify.set_defaults(handler=_verify)

    clean = sub.add_parser("clean", help="remove VibeEdit caches")
    clean.add_argument("--dry-run", action="store_true")
    clean.add_argument("--json", action="store_true")
    clean.set_defaults(handler=_clean)
    mcp = sub.add_parser("mcp", help="run the local JSON-RPC typed tool adapter")
    mcp.set_defaults(handler=_mcp)
    return parser


def _emit(value, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, indent=2))
        return
    if isinstance(value, str):
        print(value)
        return
    print(json.dumps(value, indent=2))


def _init(args) -> int:
    numerator, denominator = (int(value) for value in args.fps.split("/", 1)) if "/" in args.fps else (int(args.fps), 1)
    composition = Composition(args.id, Canvas(args.width, args.height, FrameRate(numerator, denominator)), args.frames)
    path = composition.write(args.path)
    _emit({"ok": True, "path": str(path)}, as_json=args.json)
    return 0


def _setup(args) -> int:
    from vibeedit.setup import install_setup_dependencies, setup_capabilities

    dependencies = install_setup_dependencies(browser=args.all or args.browser, effects=args.all or args.effects, vision=args.all or args.vision, sam=args.all or args.sam)
    result = setup_capabilities(browser=args.all or args.browser, effects=args.all or args.effects, vision=args.all or args.vision, sam=args.all or args.sam)
    result["dependencies"] = dependencies
    result["ok"] = True
    result["complete"] = all(item.get("available", False) for item in result["results"] if item.get("required", False))
    result["cache"] = str(cache_root())
    _emit(result, as_json=args.json)
    return 0


def _doctor(args) -> int:
    result = doctor()
    _emit(result, as_json=args.json)
    return 0 if result["ready"] else 1


def _inspect(args) -> int:
    path = Path(args.path)
    if path.suffix.lower() == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        validate_composition(value)
        result = {"kind": "composition", "valid": True, "id": value["id"], "durationFrames": value["durationFrames"]}
    else:
        result = probe(path)
    _emit(result, as_json=args.json)
    return 0


def _catalog_list(args) -> int:
    _emit(list_catalog(), as_json=args.json)
    return 0


def _catalog_search(args) -> int:
    query = args.query.casefold()
    items = search_catalog(query)
    _emit(items, as_json=args.json)
    return 0 if items else 2


def _catalog_open(args) -> int:
    path = data_path("site", "index.html")
    if not path.is_file():
        raise RuntimeError("catalog site has not been generated")
    opened = False if args.no_browser else webbrowser.open(path.resolve().as_uri())
    _emit({"ok": True, "path": str(path), "opened": opened}, as_json=args.json)
    return 0


def _examples_list(args) -> int:
    root = data_path("examples")
    items = sorted(path.name for path in root.iterdir() if path.is_dir()) if root.is_dir() else []
    _emit(items, as_json=args.json)
    return 0


def _examples_create(args) -> int:
    destination = create_example(args.id, args.destination)
    _emit({"ok": True, "path": str(destination)}, as_json=args.json)
    return 0


def _skills_list(args) -> int:
    _emit(list_skills(), as_json=args.json)
    return 0


def _skills_install(args) -> int:
    _emit(install_skill(args.id, harness=args.harness, scope=args.scope), as_json=args.json)
    return 0


def _skills_check(args) -> int:
    _emit(check_skill(args.id, harness=args.harness, scope=args.scope), as_json=args.json)
    return 0


def _skills_update(args) -> int:
    _emit(update_skill(args.id, harness=args.harness, scope=args.scope), as_json=args.json)
    return 0


def _skills_remove(args) -> int:
    _emit(remove_skill(args.id, harness=args.harness, scope=args.scope), as_json=args.json)
    return 0


def _validate(args) -> int:
    value = json.loads(Path(args.path).read_text(encoding="utf-8"))
    validate_composition(value)
    _emit({"ok": True, "path": args.path, "schemaVersion": value["schemaVersion"]}, as_json=args.json)
    return 0


def _render(args) -> int:
    output = render(args.path, args.output)
    _emit({"ok": True, "output": str(output), "bytes": output.stat().st_size}, as_json=args.json)
    return 0


def _verify(args) -> int:
    expectations = None
    if args.spec:
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        validate_composition(spec)
        expectations = spec.get("verification")
    report = verify_output(args.output, expectations)
    _emit(report.to_spec(), as_json=args.json)
    return 0 if report.passed else 1


def _clean(args) -> int:
    root = cache_root()
    existed = root.exists()
    if existed and not args.dry_run:
        shutil.rmtree(root)
    _emit({"ok": True, "path": str(root), "existed": existed, "removed": existed and not args.dry_run}, as_json=args.json)
    return 0


def _mcp(args) -> int:
    from vibeedit.mcp import main as mcp_main

    return mcp_main()


if __name__ == "__main__":
    raise SystemExit(main())
