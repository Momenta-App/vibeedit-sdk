"""Browser-owned source acquisition with durable page intent and byte-bound receipts.

No cookies, signed final URLs or provider media are distributed in the package.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import sqlite3
import time
import urllib.parse
from pathlib import Path

from vibeedit.data import data_path
from vibeedit.project import Project, atomic_json, canonical, file_digest, within

SCHEMA = "vibeedit.acquisition.v1"


def providers(query=""):
    catalog = json.loads(data_path("catalog", "providers.json").read_text())
    words = query.lower().split()
    pages = [p for p in catalog["pages"] if all(w in canonical(p).lower() for w in words)]
    entries = [{**p, "searchUrl": p["searchUrl"].replace("{query}", urllib.parse.quote(query, safe=""))} for p in catalog["providers"]]
    return {"schemaVersion": SCHEMA, "ok": True, "checkedOn": catalog["checkedOn"], "providers": entries, "pages": pages}


def _page(provider_id, page_url):
    provider = next((p for p in providers()["providers"] if p["id"] == provider_id), None)
    if provider is None:
        raise ValueError("unknown page provider; browse the maintained source catalog")
    parsed = urllib.parse.urlsplit(page_url)
    if parsed.scheme != "https" or parsed.hostname not in provider["pageHosts"] or parsed.username or parsed.password or parsed.port not in {None, 443}:
        raise ValueError("source page must be HTTPS on the selected provider's page host")
    if parsed.query or parsed.fragment:
        raise ValueError("use a stable item page without query/fragment credentials; search URLs are discovery only")
    if not parsed.path or any(ord(c) < 32 for c in page_url):
        raise ValueError("invalid source page URL")
    return provider, urllib.parse.urlunsplit(("https", parsed.netloc.lower(), parsed.path, "", ""))


@contextlib.contextmanager
def _database(project):
    path = project.database.parent / "acquisition.sqlite3"
    if path.is_symlink():
        raise ValueError("acquisition database must not be symlinked")
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.execute("CREATE TABLE IF NOT EXISTS acquisitions (id TEXT PRIMARY KEY,intent TEXT NOT NULL,state TEXT NOT NULL,download TEXT,receipt TEXT,created REAL NOT NULL,updated REAL NOT NULL)")
    if os.name != "nt":
        path.chmod(0o600)
    try:
        yield db
    finally:
        db.close()


def start(project, identity, provider_id, page_url, title):
    project = Project(project)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", identity):
        raise ValueError("acquisition ID must use ASCII letters, digits, underscore or hyphen")
    if not title.strip() or len(title) > 1024:
        raise ValueError("a bounded source item title is required")
    provider, page = _page(provider_id, page_url)
    intent = {"providerId": provider_id, "pageUrl": page, "title": title, "termsUrl": provider["termsUrl"]}
    with _database(project) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM acquisitions WHERE id=?", (identity,)).fetchone()
        if row and row["intent"] != canonical(intent):
            raise ValueError("acquisition ID reused with conflicting source page")
        if not row:
            db.execute("INSERT INTO acquisitions VALUES(?,?,?,NULL,NULL,?,?)", (identity, canonical(intent), "awaiting_browser", time.time(), time.time()))
        db.commit()
    return status(project.root, identity)


def status(project, identity):
    project = Project(project)
    with _database(project) as db:
        row = db.execute("SELECT * FROM acquisitions WHERE id=?", (identity,)).fetchone()
        if row is None:
            raise ValueError("unknown acquisition handle")
        intent = json.loads(row["intent"])
        return {"schemaVersion": SCHEMA, "ok": True, "id": identity, "state": row["state"], "page": intent, "receipt": json.loads(row["receipt"]) if row["receipt"] else None, "nextAction": "Source verified and registered; reuse its content identity" if row["state"] == "complete" else "Open the saved item page using available browser tools; complete login/download there, then finish with the actual downloaded file and rights metadata. Missing browser/login preserves this handle.", "continuation": ["vibeedit", "acquire", "status", "--project", str(project.root), "--id", identity, "--json"]}


def finish(project, identity, media, rights, *, expected_revision, expected_sha256=None, final_url=None, harness="manual"):
    project = Project(project)
    media = Path(media).resolve(strict=True)
    if not media.is_file() or media.stat().st_size == 0 or media.suffix.lower() in {".part", ".partial", ".crdownload", ".download", ".tmp"}:
        raise ValueError("a completed nonempty browser download is required")
    if not isinstance(rights, dict) or not all(isinstance(rights.get(k), str) and rights[k].strip() and len(rights[k]) <= 4096 for k in ("license", "attribution", "verifiedBy")):
        raise ValueError("record the selected file's license, attribution and verification author")
    if set(rights)-{"license","attribution","verifiedBy","notes","licenseUrl"} or len(canonical(rights).encode()) > 16384:
        raise ValueError("rights metadata must contain only bounded public license/attribution fields")
    if harness not in {"codex", "claude-code", "pi", "manual", "other"}:
        raise ValueError("unknown parent harness label")
    digest = file_digest(media)
    if expected_sha256 is not None and expected_sha256 != digest:
        raise ValueError("download digest differs from expected original bytes")
    # Final URLs are capabilities with shorter lifetimes than their source page.
    # Keep only non-secret origin and a digest, never a reusable signed URL.
    download = {"sha256": digest, "byteLength": media.stat().st_size, "rights": rights, "harness": harness}
    if final_url:
        parsed = urllib.parse.urlsplit(final_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("download URL metadata must be HTTPS without userinfo")
        download["transport"] = {"origin": "https://"+parsed.hostname, "urlSha256": hashlib.sha256(final_url.encode()).hexdigest(), "finalUrlStored": False}
    with _database(project) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM acquisitions WHERE id=?", (identity,)).fetchone()
        if row is None:
            raise ValueError("start the source-page acquisition before accepting a download")
        if row["download"] and json.loads(row["download"]) != download:
            raise ValueError("download retry conflicts with the original bytes/rights/transport receipt")
        if row["state"] == "complete":
            receipt = json.loads(row["receipt"])
            source = project.source(receipt["sourceId"])
            if source["sha256"] != digest or file_digest(within(project.root, source["path"])) != digest:
                raise ValueError("completed source has changed; relink by original content identity")
            return {"schemaVersion": SCHEMA, "ok": True, "id": identity, "state": "complete", "receipt": receipt, "reused": True}
        # Durable acceptance before source copies/project mutation. A crash can
        # resume the same download and reconcile its already-attached receipt.
        db.execute("UPDATE acquisitions SET state='accepting',download=?,updated=? WHERE id=?", (canonical(download), time.time(), identity))
        db.commit()
        receipt = {"schemaVersion": SCHEMA, "operationId": identity, "page": json.loads(row["intent"]), "download": download, "startedAtUnix": row["created"]}
        receipt_path = within(project.root, f"acquisition/{identity}.json")
        if receipt_path.is_file():
            if json.loads(receipt_path.read_text()) != receipt:
                raise ValueError("immutable source receipt conflict")
        else:
            atomic_json(receipt_path, receipt)
        reference = {"operationId": identity, "path": receipt_path.relative_to(project.root).as_posix(), "sha256": file_digest(receipt_path)}
        value = project.read()
        source = next((s for s in value["sources"] if s["sha256"] == digest), None)
        if source is None:
            value = project.register_source(media, expected_revision=expected_revision, receipt={"schemaVersion": SCHEMA, "receipts": [reference]})
            source = next(s for s in value["sources"] if s["sha256"] == digest)
        else:
            linked = source.get("acquisition", {}).get("receipts", [])
            if not any(r["operationId"] == identity and r == reference for r in linked):
                def attach(document):
                    item = next(s for s in document["sources"] if s["sha256"] == digest)
                    old = item.get("acquisition")
                    item["acquisition"] = {"schemaVersion": SCHEMA, "receipts": [*(old or {}).get("receipts", []), reference], **({"previous": old} if old and old.get("schemaVersion") != SCHEMA else {})}
                value = project.update(expected_revision, attach)
                source = next(s for s in value["sources"] if s["sha256"] == digest)
        completed = {**receipt, "sourceId": source["id"], "sourcePath": source["path"], "nativeClock": source["clock"], "receiptPath": reference["path"], "receiptSha256": reference["sha256"]}
        db.execute("BEGIN IMMEDIATE")
        current = db.execute("SELECT * FROM acquisitions WHERE id=?", (identity,)).fetchone()
        if current["download"] != canonical(download):
            raise ValueError("concurrent acquisition identity conflict")
        db.execute("UPDATE acquisitions SET state='complete',receipt=?,updated=? WHERE id=?", (canonical(completed), time.time(), identity))
        db.commit()
        return {"schemaVersion": SCHEMA, "ok": True, "id": identity, "state": "complete", "projectRevision": value["revision"], "receipt": completed}


def register_commands(subparsers):
    command = subparsers.add_parser("acquire", help="provider pages and browser-owned source receipts")
    sub = command.add_subparsers(dest="acquire_command", required=True)
    search = sub.add_parser("search")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--json", action="store_true")
    search.set_defaults(handler=_command)
    for action in ("start", "status", "finish", "export"):
        parser = sub.add_parser(action)
        parser.add_argument("--project", required=True)
        parser.add_argument("--id", required=True)
        parser.add_argument("--json", action="store_true")
        if action == "start":
            parser.add_argument("--provider", required=True)
            parser.add_argument("--page", required=True)
            parser.add_argument("--title", required=True)
        if action == "finish":
            parser.add_argument("--file", required=True)
            parser.add_argument("--rights", required=True, help="JSON with license, attribution, verifiedBy")
            parser.add_argument("--expected-revision", type=int, required=True)
            parser.add_argument("--sha256")
            parser.add_argument("--transport-metadata", help="private JSON containing optional finalUrl; no signed URL in argv/logs")
            parser.add_argument("--harness", choices=["codex", "claude-code", "pi", "manual", "other"], default="manual")
        parser.set_defaults(handler=_command)


def _command(args):
    if args.acquire_command == "search":
        result = providers(args.query)
    elif args.acquire_command == "start":
        result = start(args.project, args.id, args.provider, args.page, args.title)
    elif args.acquire_command == "finish":
        metadata = json.loads(Path(args.transport_metadata).read_text()) if args.transport_metadata else {}
        result = finish(args.project, args.id, args.file, json.loads(Path(args.rights).read_text()), expected_revision=args.expected_revision, expected_sha256=args.sha256, final_url=metadata.get("finalUrl"), harness=args.harness)
    else:
        result = status(args.project, args.id)
    print(json.dumps(result, ensure_ascii=False))
    return 0
