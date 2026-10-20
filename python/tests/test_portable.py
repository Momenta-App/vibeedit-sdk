import json
import zipfile

import pytest

from vibeedit.portable import bundle_project, restore_project
from vibeedit.project import Project, file_digest
from test_project import project, correction


def test_transfer_keeps_exact_identity_clock_history_and_retry(project, tmp_path):
    command = correction(project)
    event = project.correct(command)
    state = project.read()
    archive = tmp_path / "back up ü.vibeedit.zip"
    receipt = bundle_project(project.root, archive)
    restored = tmp_path / "restored ü"
    result = restore_project(archive, restored, expected_sha256=receipt["sha256"])
    reopened = Project(restored)
    assert reopened.read() == state
    assert reopened.correct(command) == event
    assert reopened.corrections() == project.corrections()
    for source in state["sources"]:
        assert file_digest(restored / source["path"]) == source["sha256"]
        assert file_digest(restored / source["clock"]) == source["clockSha256"]
    assert result["execution"] == "explicit-resume-required"
    assert not (restored / ".vibeedit/review.json").exists()
    with pytest.raises(ValueError, match="new destination"):
        restore_project(archive, restored)


def test_media_omission_requires_exact_relink(project, tmp_path):
    source = project.read()["sources"][0]
    archive = tmp_path / "small.zip"
    bundle_project(project.root, archive, include_media=False)
    root = tmp_path / "offline"
    restore_project(archive, root)
    restored = Project(root)
    assert not (root/source["path"]).exists()
    restored.relink(source["id"], project.root/source["path"], expected_revision=project.read()["revision"])
    assert file_digest(root/source["path"]) == source["sha256"]


def test_malformed_bundle_never_publishes_partial_project(project, tmp_path):
    original = tmp_path / "original.zip"
    bundle_project(project.root, original)
    for attack in ("digest", "traversal", "duplicate", "private-state"):
        broken = tmp_path / f"{attack}.zip"
        with zipfile.ZipFile(original) as source, zipfile.ZipFile(broken,"w") as target:
            for name in source.namelist():
                raw = source.read(name)
                if attack == "digest" and name.startswith("project/sources/"):
                    raw = raw[:-1]+bytes([raw[-1] ^ 1])
                target.writestr(name, raw)
            if attack == "traversal":
                target.writestr("project/../../escaped", b"no")
            if attack == "duplicate":
                target.writestr("vibeedit.bundle.json",source.read("vibeedit.bundle.json"))
            if attack == "private-state":
                target.writestr("project/.vibeedit/credentials.json",b"{}")
        destination = tmp_path / f"restore-{attack}"
        with pytest.raises(ValueError):
            restore_project(broken,destination)
        assert not destination.exists()
    assert not (tmp_path/"escaped").exists()


def test_source_mutation_and_restore_ceiling_reject(project, tmp_path):
    archive = tmp_path / "bound.zip"
    bundle_project(project.root, archive)
    with pytest.raises(ValueError, match="ceiling"):
        restore_project(archive,tmp_path/"too-big",max_bytes=1)
    with pytest.raises(ValueError, match="checksum"):
        restore_project(archive,tmp_path/"bad-hash",expected_sha256="0"*64)
    source=project.root/project.read()["sources"][0]["path"]
    source.write_bytes(b"altered")
    with pytest.raises(ValueError,match="changed"):
        bundle_project(project.root,tmp_path/"altered.zip")


def test_registered_mask_tree_and_render_report_survive_transfer(project, tmp_path):
    directory = project.root/"masks/review ü"
    directory.mkdir(parents=True)
    (directory/"mask.rle.json").write_text('{"runs":[0,4,1,2]}', encoding="utf-8")
    source = project.read()["sources"][0]
    record = project.register_artifact("masks", "masks/review ü", expected_revision=1, source_id=source["id"])
    archive = tmp_path/"mask-tree.zip"
    bundle_project(project.root, archive)
    destination = tmp_path/"with-masks"
    restore_project(archive,destination)
    assert Project(destination).read()["masks"] == [record]
    assert file_digest(destination/record["files"][0]["path"]) == record["files"][0]["sha256"]
    with pytest.raises(ValueError,match="Private"):
        project.register_artifact("reviews",".vibeedit",expected_revision=2)


def test_transfer_pauses_worker_and_preserves_unknown_paid_hold(project, tmp_path):
    from vibeedit.goals import Store
    store=Store(project.root)
    store.create("worker","original-worker",{"funding":"managed","maxRetailMicrousd":200})
    store.intent("original-worker","original-send","inference",{"requestSha256":"a"*64},reserve=100,cap=200)
    store.settle("original-send","unknown",{"remoteOperationId":"original-remote-handle"})
    store.close()
    archive=tmp_path/"worker-recovery.zip"
    bundle_project(project.root,archive)
    root=tmp_path/"resumed-work"
    restore_project(archive,root)
    restored=Store(root)
    assert restored.get("original-worker")["status"]=="paused"
    operation=restored.operations("original-worker")[0]
    assert operation["id"]=="original-send"
    assert operation["reserved_microusd"]==100 and operation["settled_microusd"] is None
    assert operation["receipt"]["remoteOperationId"]=="original-remote-handle"
    assert operation["state"]=="unknown"
    restored.close()
