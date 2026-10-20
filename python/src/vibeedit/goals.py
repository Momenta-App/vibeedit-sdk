"""Project-local durable scheduling. Pi conversations and remote money remain separate."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path

SCHEMA = "vibeedit.companion.v1"
TERMINAL = {"complete", "failed", "canceled", "budget_limited"}
STATUSES = {"active", "waiting", "paused", "blocked", *TERMINAL}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def project_path(project):
    root = Path(project).resolve(strict=True)
    if not root.is_dir() or not (root / "project.vibeedit.json").is_file():
        raise ValueError("project must contain project.vibeedit.json")
    if (root / ".vibeedit").is_symlink():
        raise ValueError("project state directory must not be a symlink")
    return root


class Store:
    """SQLite transactions serialize admission; monotonically increasing fences reject old owners."""
    def __init__(self, project):
        self.root = project_path(project)
        state = self.root / ".vibeedit"
        state.mkdir(mode=0o700, exist_ok=True)
        path = state / "companion.sqlite3"
        if path.is_symlink():
            raise ValueError("companion database must not be a symlink")
        self.db = sqlite3.connect(path, timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        if os.name != "nt":
            path.chmod(0o600)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS records (
            id TEXT PRIMARY KEY, kind TEXT NOT NULL, spec TEXT NOT NULL, digest TEXT NOT NULL,
            status TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0, result TEXT,
            owner TEXT, fence INTEGER NOT NULL DEFAULT 0, lease_until REAL NOT NULL DEFAULT 0,
            created REAL NOT NULL, updated REAL NOT NULL);
          CREATE TABLE IF NOT EXISTS events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT, record_id TEXT NOT NULL,
            kind TEXT NOT NULL, data TEXT NOT NULL, created REAL NOT NULL);
          CREATE TABLE IF NOT EXISTS operations (
            id TEXT PRIMARY KEY, record_id TEXT NOT NULL, kind TEXT NOT NULL,
            digest TEXT NOT NULL, state TEXT NOT NULL, intent TEXT NOT NULL, receipt TEXT,
            reserved_microusd INTEGER NOT NULL DEFAULT 0, settled_microusd INTEGER,
            created REAL NOT NULL, updated REAL NOT NULL);
          CREATE TABLE IF NOT EXISTS controls (
            id TEXT PRIMARY KEY, record_id TEXT NOT NULL, kind TEXT NOT NULL,
            payload TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending');
        """)

    def close(self):
        self.db.close()

    @contextlib.contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def event(self, identity, kind, data):
        self.db.execute("INSERT INTO events(record_id,kind,data,created) VALUES(?,?,?,?)", (identity, kind, canonical(data), time.time()))

    def create(self, kind, identity, spec):
        if not identity or len(identity) > 120 or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in identity):
            raise ValueError("record ID must be 1–120 ASCII letters, digits, hyphen or underscore")
        encoded = canonical(spec)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with self.transaction():
            row = self.db.execute("SELECT digest,kind FROM records WHERE id=?", (identity,)).fetchone()
            if row and (row["digest"] != digest or row["kind"] != kind):
                raise ValueError("conflicting reuse of durable ID")
            if not row:
                self.db.execute("INSERT INTO records(id,kind,spec,digest,status,created,updated) VALUES(?,?,?,?,?,?,?)", (identity, kind, encoded, digest, "active", time.time(), time.time()))
                self.event(identity, "admitted", {"kind": kind, "digest": digest})
        return self.get(identity)

    def get(self, identity):
        row = self.db.execute("SELECT * FROM records WHERE id=?", (identity,)).fetchone()
        if not row:
            raise ValueError(f"unknown durable handle: {identity}")
        return {**dict(row), "spec": json.loads(row["spec"]), "result": json.loads(row["result"]) if row["result"] else None}

    def events(self, identity, after=0):
        self.get(identity)
        return [{**dict(r), "data": json.loads(r["data"])} for r in self.db.execute("SELECT * FROM events WHERE record_id=? AND seq>? ORDER BY seq LIMIT 1000", (identity, after))]

    def claim(self, identity, owner, seconds=20):
        with self.transaction():
            row = self.get(identity)
            if row["status"] != "active" or row["lease_until"] > time.time():
                return None
            concurrent = self.db.execute("SELECT COUNT(*) FROM records WHERE kind=? AND status='active' AND lease_until>? AND id!=?", (row["kind"], time.time(), identity)).fetchone()[0]
            if concurrent >= 2:
                self.db.execute("UPDATE records SET status='blocked',result=?,revision=revision+1,updated=? WHERE id=?", (canonical({"reason": "project concurrency limit reached (two goals / two workers); explicitly resume after a slot is free"}), time.time(), identity))
                self.event(identity, "resource_limit", {"kind": row["kind"], "limit": 2, "resumeRequired": True})
                return None
            self.db.execute("UPDATE records SET owner=?,fence=fence+1,lease_until=?,updated=? WHERE id=?", (owner, time.time()+seconds, time.time(), identity))
            self.event(identity, "lease", {"owner": owner, "fence": row["fence"]+1})
            return row["fence"]+1

    def heartbeat(self, identity, owner, fence):
        updated = self.db.execute("UPDATE records SET lease_until=? WHERE id=? AND owner=? AND fence=? AND lease_until>?", (time.time()+20, identity, owner, fence, time.time()))
        if updated.rowcount != 1:
            raise RuntimeError("scheduler lease lost; stale owner cannot continue")

    def update(self, identity, status, result=None, *, expected_revision=None, owner=None, fence=None):
        if status not in STATUSES:
            raise ValueError("invalid lifecycle status")
        with self.transaction():
            row = self.get(identity)
            if expected_revision is not None and row["revision"] != expected_revision:
                raise ValueError("stale goal revision")
            if owner is not None and (row["owner"] != owner or row["fence"] != fence or row["lease_until"] <= time.time()):
                raise RuntimeError("scheduler lease lost")
            self.db.execute("UPDATE records SET status=?,result=?,revision=revision+1,updated=?,fence=fence+?,owner=CASE WHEN ? THEN NULL ELSE owner END,lease_until=CASE WHEN ? THEN 0 ELSE lease_until END WHERE id=?", (status, canonical(result) if result is not None else row["result"] and canonical(row["result"]), time.time(), int(owner is None and expected_revision is not None), int(owner is None and expected_revision is not None), int(owner is None and expected_revision is not None), identity))
            self.event(identity, "status", {"status": status, "result": result})
        return self.get(identity)

    def intent(self, identity, op_id, kind, payload, *, reserve=0, cap=None, owner=None, fence=None):
        """Returns False for an exact retry. Caller must reconcile, never resend that operation."""
        encoded = canonical(payload)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with self.transaction():
            record = self.get(identity)
            if owner is not None and (record["owner"] != owner or record["fence"] != fence or record["lease_until"] <= time.time()):
                raise RuntimeError("scheduler lease lost before intent")
            existing = self.db.execute("SELECT * FROM operations WHERE id=?", (op_id,)).fetchone()
            if existing:
                if existing["digest"] != digest or existing["record_id"] != identity or existing["kind"] != kind:
                    raise ValueError("conflicting operation retry")
                return False
            if kind in {"inference", "analysis"}:
                if record["status"] != "active" or self.db.execute("SELECT 1 FROM controls WHERE record_id=? AND kind='cancel' AND state IN ('pending','sending')", (identity,)).fetchone():
                    raise ValueError("durable cancellation/stop precedes inference admission")
                parent_id = record["spec"].get("parentGoalId")
                if parent_id and self.get(parent_id)["status"] != "active":
                    raise ValueError("parent goal stopped before inference intent")
            used = self.db.execute("SELECT COALESCE(SUM(COALESCE(settled_microusd,reserved_microusd)),0) FROM operations WHERE record_id=?", (identity,)).fetchone()[0]
            if reserve < 0 or (cap is not None and used + reserve > cap):
                raise ValueError("retail ceiling exceeded; outstanding holds count toward the cap")
            self.db.execute("INSERT INTO operations(id,record_id,kind,digest,state,intent,reserved_microusd,created,updated) VALUES(?,?,?,?,?,?,?,?,?)", (op_id, identity, kind, digest, "intent", encoded, reserve, time.time(), time.time()))
            self.event(identity, "intent", {"operationId": op_id, "kind": kind, "reservedMicrousd": reserve})
        return True

    def settle(self, op_id, state, receipt, cost=None):
        with self.transaction():
            row = self.db.execute("SELECT * FROM operations WHERE id=?", (op_id,)).fetchone()
            if not row:
                raise ValueError("receipt has no durable intent")
            if row["state"] == "settled":
                if row["receipt"] != canonical(receipt) or row["settled_microusd"] != cost:
                    raise ValueError("conflicting settlement")
                return
            if cost is not None and (cost < 0 or cost > row["reserved_microusd"]):
                raise ValueError("settlement exceeds conservative reservation; retain hold and investigate")
            self.db.execute("UPDATE operations SET state=?,receipt=?,settled_microusd=?,updated=? WHERE id=?", (state, canonical(receipt), cost, time.time(), op_id))
            self.event(row["record_id"], "receipt", {"operationId": op_id, "state": state, "receipt": receipt})

    def operations(self, identity):
        return [{**dict(r), "intent": json.loads(r["intent"]), "receipt": json.loads(r["receipt"]) if r["receipt"] else None} for r in self.db.execute("SELECT * FROM operations WHERE record_id=? ORDER BY created", (identity,))]

    def control(self, identity, kind, payload, control_id=None):
        self.get(identity)
        control_id = control_id or str(uuid.uuid4())
        with self.transaction():
            row = self.db.execute("SELECT * FROM controls WHERE id=?", (control_id,)).fetchone()
            if row and (row["record_id"] != identity or row["kind"] != kind or row["payload"] != canonical(payload)):
                raise ValueError("conflicting control ID")
            self.db.execute("INSERT OR IGNORE INTO controls(id,record_id,kind,payload) VALUES(?,?,?,?)", (control_id, identity, kind, canonical(payload)))
            if not row:
                self.event(identity, "control", {"id": control_id, "kind": kind})
        return control_id


SNAPSHOT_COLUMNS = {
    "records": ("id", "kind", "spec", "digest", "status", "revision", "result", "owner", "fence", "lease_until", "created", "updated"),
    "events": ("seq", "record_id", "kind", "data", "created"),
    "operations": ("id", "record_id", "kind", "digest", "state", "intent", "receipt", "reserved_microusd", "settled_microusd", "created", "updated"),
    "controls": ("id", "record_id", "kind", "payload", "state"),
}


def export_snapshot(project):
    """Passive bundle data only: no SQLite code, Pi chats, provider configs or process capabilities."""
    store = Store(project)
    try:
        with store.transaction():
            tables = {name: [dict(row) for row in store.db.execute("SELECT " + ",".join(columns) + " FROM " + name + (" WHERE kind != 'pi'" if name == "events" else "") + (" ORDER BY seq" if name == "events" else " ORDER BY id"))] for name, columns in SNAPSHOT_COLUMNS.items()}
        for row in tables["records"]:
            row["owner"] = None
            row["lease_until"] = 0
        for row in tables["events"]:
            if row["kind"] in {"lease", "worker_started", "supervisor_started"}:
                value = json.loads(row["data"])
                row["data"] = canonical({key: item for key, item in value.items() if key not in {"owner", "pid", "supervisorPid", "startIdentity"}})
        payload = {"schemaVersion": SCHEMA + ".snapshot.1", "tables": tables, "excluded": ["pi-chat-events", "pi-session-files", "provider-config", "credentials", "loopback-capabilities"]}
        _snapshot_private_guard(payload)
        return {**payload, "sha256": hashlib.sha256(canonical(payload).encode()).hexdigest()}
    finally:
        store.close()


def restore_snapshot(project, snapshot):
    """Restore into an empty SDK schema; never execute SQL from an archive or auto-resume work."""
    if not isinstance(snapshot, dict) or snapshot.get("schemaVersion") != SCHEMA + ".snapshot.1":
        raise ValueError("unsupported companion snapshot")
    payload = {key: value for key, value in snapshot.items() if key != "sha256"}
    if hashlib.sha256(canonical(payload).encode()).hexdigest() != snapshot.get("sha256"):
        raise ValueError("companion snapshot digest mismatch")
    _snapshot_private_guard(payload)
    tables = snapshot.get("tables")
    if not isinstance(tables, dict) or set(tables) != set(SNAPSHOT_COLUMNS):
        raise ValueError("companion snapshot table whitelist mismatch")
    for name, columns in SNAPSHOT_COLUMNS.items():
        if not isinstance(tables[name], list) or len(tables[name]) > 1000000:
            raise ValueError("invalid companion snapshot table size")
        if any(not isinstance(row, dict) or set(row) != set(columns) for row in tables[name]):
            raise ValueError("companion snapshot column whitelist mismatch")
    ids = {row["id"] for row in tables["records"]}
    for row in tables["records"]:
        if row["status"] not in STATUSES or row["kind"] not in {"worker", "goal"}:
            raise ValueError("invalid restored record lifecycle")
        if hashlib.sha256(row["spec"].encode()).hexdigest() != row["digest"]:
            raise ValueError("restored spec identity mismatch")
        json.loads(row["spec"])
        if row["result"] is not None:
            json.loads(row["result"])
    for name in ["operations", "events", "controls"]:
        for row in tables[name]:
            if row["record_id"] not in ids:
                raise ValueError("restored row references a missing record")
    for row in tables["operations"]:
        if hashlib.sha256(row["intent"].encode()).hexdigest() != row["digest"]:
            raise ValueError("restored operation identity mismatch")
        if not isinstance(row["reserved_microusd"], int) or row["reserved_microusd"] < 0 or (row["settled_microusd"] is not None and (not isinstance(row["settled_microusd"], int) or not 0 <= row["settled_microusd"] <= row["reserved_microusd"])):
            raise ValueError("invalid restored financial hold")
    store = Store(project)
    try:
        with store.transaction():
            if any(store.db.execute("SELECT 1 FROM " + name + " LIMIT 1").fetchone() for name in SNAPSHOT_COLUMNS):
                raise ValueError("companion restore requires an empty project state; merging native handles is unsafe")
            for name, columns in SNAPSHOT_COLUMNS.items():
                for original in tables[name]:
                    row = dict(original)
                    if name == "records":
                        row.update(owner=None, lease_until=0, fence=row["fence"] + 1, revision=row["revision"] + 1)
                        if row["status"] in {"active", "waiting"}:
                            row["status"] = "paused"
                    store.db.execute("INSERT INTO " + name + "(" + ",".join(columns) + ") VALUES(" + ",".join("?" for _ in columns) + ")", [row[column] for column in columns])
            for identity in sorted(ids):
                store.event(identity, "bundle_restored", {"snapshotSha256": snapshot["sha256"], "resumeRequired": True, "unknownOperationsMustReconcile": True})
        return {"schemaVersion": SCHEMA, "records": len(ids), "operations": len(tables["operations"]), "resumeRequired": True, "snapshotSha256": snapshot["sha256"]}
    finally:
        store.close()


def _snapshot_private_guard(value):
    # Opaque text values are user project data; operational configs never enter these tables.
    # Reject explicit credential objects even if a caller accidentally inserted one into a spec.
    if isinstance(value, str):
        if value.startswith("{") or value.startswith("["):
            with contextlib.suppress(json.JSONDecodeError):
                _snapshot_private_guard(json.loads(value))
        return
    if isinstance(value, list):
        for item in value:
            _snapshot_private_guard(item)
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = key.lower().replace("_", "").replace("-", "")
            if normalized in {"apikey", "apikeydpapi", "authorization", "password", "secret", "accesstoken", "refreshtoken", "loopbacktoken"}:
                raise ValueError("companion snapshot must not contain credential objects")
            _snapshot_private_guard(item)


def detach(module, project, identity):
    # No shell, system service or inherited user credentials. Only this child gets a new group.
    options = {"start_new_session": True} if os.name != "nt" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS}
    process = subprocess.Popen([sys.executable, "-m", module, "--project", str(project), "--handle", identity], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **options)
    return {"pid": process.pid, "startedAt": time.time(), "ownership": "detached project supervisor; never signal a PID from a stale receipt"}


def validate_goal(spec):
    from vibeedit.worker import validate_task
    if not isinstance(spec, dict) or not str(spec.get("objective", "")).strip():
        raise ValueError("goal objective required")
    if not isinstance(spec.get("acceptance"), list) or not spec["acceptance"]:
        raise ValueError("explicit acceptance criteria required")
    if not isinstance(spec.get("steps"), list) or not spec["steps"]:
        raise ValueError("goal requires ordered bounded worker steps")
    if len(spec["steps"]) > 100:
        raise ValueError("goal step count exceeds local limit")
    for index, step in enumerate(spec["steps"]):
        validate_task(step)
        bindings = step.get("derivedReferences", [])
        if not isinstance(bindings, list) or len(bindings) > 100:
            raise ValueError("derivedReferences must be a bounded earlier-step artifact list")
        for binding in bindings:
            if not isinstance(binding, dict) or set(binding) != {"step", "path"} or type(binding["step"]) is not int or not 0 <= binding["step"] < index or binding["path"] not in {artifact["path"] for artifact in spec["steps"][binding["step"]]["artifacts"]}:
                raise ValueError("derived reference must name an earlier step's declared artifact")
    if type(spec.get("maxRetailMicrousd")) is not int or spec["maxRetailMicrousd"] < 0:
        raise ValueError("goal requires integer maximum retail micro-USD")
    if type(spec.get("platformBudgetMicros", 0)) is not int or not 0 <= spec.get("platformBudgetMicros", 0) <= spec["maxRetailMicrousd"] // 2:
        raise ValueError("goal platformBudgetMicros must explicitly allocate real infrastructure within the retail ceiling")
    if sum(step.get("platformBudgetMicros", 0) for step in spec["steps"]) > spec.get("platformBudgetMicros", 0):
        raise ValueError("child platform allocations exceed the goal platform allowance")
    if sum(s["maxRetailMicrousd"] for s in spec["steps"]) > spec["maxRetailMicrousd"]:
        raise ValueError("child allowances exceed goal retail ceiling")
    if not isinstance(spec.get("deadlineUnix"), (float, int)) or spec["deadlineUnix"] <= time.time():
        raise ValueError("goal requires a future deadlineUnix")
    if not isinstance(spec.get("completionArtifacts"), list) or not spec["completionArtifacts"]:
        raise ValueError("goal completion requires artifact contracts")
    if not {"composition", "render", "review"}.issubset({a.get("kind") for a in spec["completionArtifacts"]}):
        raise ValueError("edit goal completion requires editable composition, playable render and source-linked review contracts")
    return spec


def step_worker_id(identity, index):
    candidate = f"{identity}-step-{index+1}"
    return candidate if len(candidate) <= 120 else "goal-" + hashlib.sha256(identity.encode()).hexdigest() + f"-step-{index+1}"


def bind_step_references(store, identity, index):
    """Pin earlier verified bytes at child admission; original goal bindings stay immutable."""
    from vibeedit.worker import validate_task, confined
    goal = store.get(identity)
    task = json.loads(canonical(goal["spec"]["steps"][index]))
    task["parentGoalId"] = identity
    bindings = task.pop("derivedReferences", [])
    lineage = []
    for binding in bindings:
        previous = store.get(step_worker_id(identity, binding["step"]))
        from vibeedit.worker import execution_checkpoint
        checkpoint = execution_checkpoint(store, previous["id"])
        if checkpoint is None:
            raise ValueError("earlier worker must have a verified execution checkpoint before its artifact becomes a child reference")
        receipt = next((artifact for artifact in checkpoint.get("artifacts", []) if artifact["path"] == binding["path"]), None)
        if not receipt:
            raise ValueError("earlier checkpoint does not verify the declared artifact")
        path = confined(store.root, binding["path"])
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        if digest != receipt["sha256"]:
            raise ValueError("earlier verified artifact changed before child admission")
        references = task.setdefault("references", [])
        digests = task.setdefault("referenceDigests", {})
        if binding["path"] in references and digests.get(binding["path"]) != digest:
            raise ValueError("derived artifact conflicts with the explicit source fingerprint")
        if binding["path"] not in references:
            references.append(binding["path"])
        digests[binding["path"]] = digest
        lineage.append({"workerId": previous["id"], "path": binding["path"], "sha256": digest})
    if lineage:
        task["derivedFrom"] = lineage
    return validate_task(task)


def stop_child(store, identity):
    from vibeedit.worker import cancel_managed_operations, cancel_analysis_operations
    store.control(identity, "cancel", {})
    try:
        cancel_managed_operations(store, identity)
        cancel_analysis_operations(store, identity)
    except (OSError, RuntimeError, ValueError):
        store.event(identity, "managed_cancel_pending", {"reason": "stop requested; original remote handles and financial holds retained"})


def supervise(project, identity):
    """A fixed bounded plan advances only after validated worker evidence, never after polls."""
    from vibeedit.worker import verify_artifacts, close_managed_allowance, execution_checkpoint, analysis_status, recover_artifacts
    store = Store(project)
    owner = str(uuid.uuid4())
    fence = store.claim(identity, owner)
    if fence is None:
        return
    row = store.get(identity)
    spec = row["spec"]
    store.event(identity, "supervisor_started", {"pid": os.getpid(), "startIdentity": owner, "fence": fence, "awakeOnly": True})
    try:
        for index, task in enumerate(spec["steps"]):
            store.heartbeat(identity, owner, fence)
            row = store.get(identity)
            if row["status"] != "active":
                return
            if time.time() >= spec["deadlineUnix"]:
                store.update(identity, "budget_limited", {"reason": "goal wall-time deadline reached"}, owner=owner, fence=fence)
                return
            worker_id = step_worker_id(identity, index)
            admitted_task = bind_step_references(store, identity, index)
            store.create("worker", worker_id, admitted_task)
            op_id = f"{identity}:child:{index+1}"
            store.intent(identity, op_id, "child_allowance", {"workerId": worker_id, "taskDigest": store.get(worker_id)["digest"]}, reserve=task["maxRetailMicrousd"], cap=spec["maxRetailMicrousd"], owner=owner, fence=fence)
            worker = store.get(worker_id)
            if worker["status"] == "active" and worker["lease_until"] <= time.time():
                detach("vibeedit.worker", store.root, worker_id)
            while True:
                time.sleep(.2)
                store.heartbeat(identity, owner, fence)
                goal = store.get(identity)
                worker = store.get(worker_id)
                if goal["status"] != "active" or time.time() >= spec["deadlineUnix"]:
                    stop_child(store, worker_id)
                    if goal["status"] == "active":
                        store.update(identity, "budget_limited", {"workerId": worker_id, "reason": "goal deadline reached; settlement remains observable"}, owner=owner, fence=fence)
                    return
                if worker["status"] != "active":
                    break
                if worker["lease_until"] < time.time()-20:
                    # A crash may have occurred after the durable intent and before acknowledgement.
                    store.update(identity, "waiting", {"workerId": worker_id, "reason": "worker unavailable; explicit recovery must reconcile original inference intents"}, owner=owner, fence=fence)
                    return
            if worker["status"] != "complete":
                checkpoint = execution_checkpoint(store, worker_id, refresh_analysis=True)
                if checkpoint is None:
                    store.update(identity, "waiting" if worker["status"] == "waiting" else "blocked", {"workerId": worker_id, "reason": worker["result"]}, owner=owner, fence=fence)
                    return
                worker = store.get(worker_id)
                if worker["status"] != "complete":
                    checkpoint_id = f"{identity}:execution:{index+1}"
                    if store.intent(identity, checkpoint_id, "execution_checkpoint", {"workerId": worker_id, "evidence": checkpoint}, owner=owner, fence=fence):
                        store.settle(checkpoint_id, "settled", {"financialHoldsRetained": True}, 0)
                        store.event(identity, "execution_checkpoint", {"step": index+1, "workerId": worker_id, "evidence": checkpoint, "financialHoldsRetained": True})
                    continue
            operations = store.operations(worker_id)
            cost = sum(o["settled_microusd"] or 0 for o in operations if o["kind"] in {"inference", "analysis"})
            if any(o["kind"] in {"inference", "analysis"} and o["state"] != "settled" for o in operations):
                store.update(identity, "waiting", {"workerId": worker_id, "reason": "inference settlement indeterminate; allowance retained"}, owner=owner, fence=fence)
                return
            store.settle(op_id, "settled", {"workerId": worker_id, "result": worker["result"]}, cost)
            store.event(identity, "checkpoint", {"step": index+1, "workerId": worker_id, "evidence": worker["result"]})
        artifacts = verify_artifacts(store.root, spec["completionArtifacts"])
        try:
            close_managed_allowance(store, identity)
        except (OSError, RuntimeError, ValueError):
            store.update(identity, "waiting", {"reason": "all execution checkpoints verified; original parent settlement/unknown platform holds still pending"}, owner=owner, fence=fence)
            return
        for index, _task in enumerate(spec["steps"]):
            worker_id = step_worker_id(identity, index)
            worker = store.get(worker_id)
            if worker["status"] == "complete":
                continue
            for operation in store.operations(worker_id):
                if operation["kind"] == "analysis" and operation["state"] != "settled":
                    analysis_status(store, worker_id, operation["intent"]["operationId"])
            operations = store.operations(worker_id)
            if any(operation["state"] != "settled" for operation in operations):
                store.update(identity, "waiting", {"workerId": worker_id, "reason": "original parent close observed; original native cost acknowledgement still pending, caps retained"}, owner=owner, fence=fence)
                return
            worker = recover_artifacts(store, worker_id)
            cost = sum(operation["settled_microusd"] or 0 for operation in operations if operation["kind"] in {"inference", "analysis"})
            store.settle(f"{identity}:child:{index+1}", "settled", {"workerId": worker_id, "result": worker["result"]}, cost)
            store.event(identity, "checkpoint", {"step": index+1, "workerId": worker_id, "evidence": worker["result"]})
        store.update(identity, "complete", {"artifacts": artifacts, "acceptance": spec["acceptance"], "validation": "contract and artifact checks; editorial acceptance remains separately attributed"}, owner=owner, fence=fence)
    except (OSError, RuntimeError, ValueError) as error:
        row = store.get(identity)
        if row["owner"] == owner and row["fence"] == fence and row["lease_until"] > time.time():
            store.update(identity, "blocked", {"reason": str(error)}, owner=owner, fence=fence)
    finally:
        store.db.execute("UPDATE records SET lease_until=0 WHERE id=? AND owner=? AND fence=?", (identity, owner, fence))
        store.close()


def recover_goal_children(store, identity):
    """Explicit resume adopts committed artifacts or leaves original unknown sends held."""
    from vibeedit.worker import recover_artifacts, execution_checkpoint
    for op in store.operations(identity):
        if op["kind"] != "child_allowance":
            continue
        child = store.get(op["intent"]["workerId"])
        if child["status"] == "complete" or child["lease_until"] > time.time():
            continue
        operations = store.operations(child["id"])
        pending = [operation for operation in operations if operation["state"] != "settled"]
        committed = any(operation["kind"] == "tool" and operation["state"] == "settled" and operation["intent"].get("name") == "submit_result" for operation in operations)
        if not pending and committed and child["status"] != "failed":
            recover_artifacts(store, child["id"])
            continue
        if pending:
            if all(operation["kind"] == "analysis" for operation in pending) and execution_checkpoint(store, child["id"], refresh_analysis=True) is not None:
                continue
            if committed and all(operation["kind"] == "rpc_prompt" for operation in pending):
                recover_artifacts(store, child["id"])
                continue
            raise ValueError("reconcile original worker provider/tool/RPC operation before goal resume; no replacement inference allowed")
        if child["status"] == "failed":
            raise ValueError("failed worker is terminal; create an explicit successor goal with original receipts")
        if child["status"] != "active":
            store.update(child["id"], "active", {"reason": "explicit goal resume; same worker/session and settled original receipts"}, expected_revision=child["revision"])


def register_commands(subparsers):
    group = subparsers.add_parser("goal", help="durable project-local edit goals")
    sub = group.add_subparsers(dest="goal_command", required=True)
    for action in ("start", "status", "edit", "pause", "resume", "cancel", "export"):
        parser = sub.add_parser(action)
        parser.add_argument("--project", required=True)
        parser.add_argument("--id", required=True)
        parser.add_argument("--json", action="store_true")
        if action in {"start", "edit"}:
            parser.add_argument("--spec", required=True)
        if action in {"edit", "pause", "resume", "cancel"}:
            parser.add_argument("--expected-revision", type=int, required=True)
        if action == "start":
            parser.add_argument("--no-detach", action="store_true")
        parser.set_defaults(handler=_command)


def _command(args):
    with contextlib.closing(Store(args.project)) as store:
        action = args.goal_command
        if action == "start":
            record = store.create("goal", args.id, validate_goal(json.loads(Path(args.spec).read_text())))
            if not args.no_detach and record["status"] == "active":
                detach(__name__, store.root, args.id)
        elif action in {"status", "export"}:
            record = store.get(args.id)
        elif action == "edit":
            row = store.get(args.id)
            if row["revision"] != args.expected_revision or row["status"] != "paused":
                raise ValueError("edit requires current revision and paused goal")
            if store.operations(args.id):
                raise ValueError("admitted steps are immutable; create a successor goal with explicit original handles")
            spec = validate_goal(json.loads(Path(args.spec).read_text()))
            with store.transaction():
                store.db.execute("UPDATE records SET spec=?,digest=?,revision=revision+1 WHERE id=? AND revision=?", (canonical(spec), hashlib.sha256(canonical(spec).encode()).hexdigest(), args.id, args.expected_revision))
                store.event(args.id, "edited", {"spec": spec})
            record = store.get(args.id)
        else:
            row = store.get(args.id)
            if row["kind"] != "goal":
                raise ValueError("handle is not a goal")
            if row["status"] in TERMINAL:
                if action == "resume":
                    raise ValueError("terminal goals cannot be resumed; completed replay is read-only")
                record = row
            else:
                if action == "resume":
                    recover_goal_children(store, args.id)
                record = store.update(args.id, {"pause": "paused", "resume": "active", "cancel": "canceled"}[action], expected_revision=args.expected_revision)
                if action in {"pause", "cancel"}:
                    for op in store.operations(args.id):
                        if op["kind"] == "child_allowance" and op["state"] != "settled":
                            stop_child(store, op["intent"]["workerId"])
                if action == "resume":
                    detach(__name__, store.root, args.id)
        if action == "cancel":
            from vibeedit.worker import close_managed_allowance
            try:
                close_managed_allowance(store, args.id)
            except (OSError, RuntimeError, ValueError):
                store.event(args.id, "managed_close_pending", {"reason": "goal canceled; original prepaid holds/close remain observable"})
        result = {"schemaVersion": SCHEMA, "ok": True, "goal": record, "continuation": f"vibeedit goal status --project {json.dumps(str(store.root))} --id {args.id} --json"}
        if action == "export":
            result.update({"events": store.events(args.id), "operations": store.operations(args.id)})
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--handle", required=True)
    arguments = parser.parse_args()
    supervise(arguments.project, arguments.handle)

# Project bundle integration names. Passive recovery never starts a supervisor.
export_recovery = export_snapshot
import_recovery = restore_snapshot
