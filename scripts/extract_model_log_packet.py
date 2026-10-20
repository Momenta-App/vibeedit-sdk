"""Verify a bounded public model evidence log packet before writing any files."""
import argparse
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--pack", choices=["transnet", "sam21"], required=True)
    parser.add_argument("--packet-sha256", required=True)
    parser.add_argument("--wheel-sha256", required=True)
    parser.add_argument("--fixture-metadata-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for value in (args.packet_sha256, args.wheel_sha256, args.fixture_metadata_sha256):
        if not re.fullmatch(r"[a-f0-9]{64}", value):
            raise ValueError("Pin every expected SHA256 explicitly")
    if args.log.stat().st_size > 64 * 1024 ** 2 or args.output.exists():
        raise ValueError("Bound logs to64MiB and choose a new output directory")
    events = {key: [] for key in ("BEGIN", "CHUNK", "END")}
    for line in args.log.read_text(encoding="utf-8-sig").splitlines():
        for kind in events:
            prefix = "VIBEEDIT_MODEL_PACKET_" + kind + " "
            offset = line.find(prefix)
            if offset < 0:
                continue
            value = line[offset + len(prefix):]
            if not value.startswith("{"):
                continue  # Workflow echoed source is not emitted evidence.
            event = json.loads(value)
            if event.get("pack") == args.pack:
                events[kind].append(event)
    if len(events["BEGIN"]) != 1 or len(events["END"]) != 1:
        raise ValueError("Missing/ambiguous packet; never guess between attempts")
    header, end = events["BEGIN"][0], events["END"][0]
    if (header["sha256"] != args.packet_sha256 or end["sha256"] != args.packet_sha256
            or not 0 < header["bytes"] <= 2 * 1024 ** 2
            or header["chunks"] != end["chunks"] or len(events["CHUNK"]) != header["chunks"]):
        raise ValueError("Packet identity or bound mismatch")
    chunks = sorted(events["CHUNK"], key=lambda event: event["index"])
    if [event["index"] for event in chunks] != list(range(header["chunks"])):
        raise ValueError("Missing/duplicate/reordered packet chunk")
    encoded = "".join(event["base64"] for event in chunks)
    if len(encoded) > 4 * ((2 * 1024 ** 2 + 2) // 3):
        raise ValueError("Encoded packet exceeds bound")
    compressed = base64.b64decode(encoded, validate=True)
    if len(compressed) != header["bytes"] or hashlib.sha256(compressed).hexdigest() != args.packet_sha256:
        raise ValueError("Compressed packet digest mismatch")
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        raw = stream.read(8 * 1024 ** 2 + 1)
    if len(raw) > 8 * 1024 ** 2:
        raise ValueError("Uncompressed packet exceeds bound")
    entries = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        for member in archive:
            path = PurePosixPath(member.name)
            if (not member.isfile() or path.is_absolute() or ".." in path.parts
                    or "\\" in member.name or ":" in member.name
                    or str(path) != member.name or path.suffix not in {".json", ".png", ".lock"}
                    or member.name in entries or member.size > 2 * 1024 ** 2):
                raise ValueError("Unsafe or repeated evidence entry")
            data = archive.extractfile(member).read()
            expected = header["entries"].get(member.name)
            if expected != {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}:
                raise ValueError("Evidence entry digest/length mismatch")
            entries[member.name] = data
    if set(entries) != set(header["entries"]):
        raise ValueError("Packet entry inventory mismatch")
    receipt = json.loads(entries["receipt.json"])
    if (receipt["pack"] != args.pack or receipt["qualified"] is not False
            or receipt.get("canonicalVerification", {}).get("artifacts", {}).get("pythonWheel", {}).get("sha256") != args.wheel_sha256
            or hashlib.sha256(entries["fixture.json"]).hexdigest() != args.fixture_metadata_sha256):
        raise ValueError("Candidate provenance differs from expected public archive/fixture")
    args.output.mkdir(parents=True, exist_ok=False)
    for name, data in entries.items():
        path = args.output.joinpath(*PurePosixPath(name).parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
    print(json.dumps({"status": "verified-extracted-needs-review", "pack": args.pack,
        "packetSha256": args.packet_sha256, "logSha256": hashlib.sha256(args.log.read_bytes()).hexdigest(),
        "files": len(entries), "qualified": False, "source": receipt.get("canonicalSourceRevision"),
        "state": receipt["state"]}, sort_keys=True))


if __name__ == "__main__":
    main()
