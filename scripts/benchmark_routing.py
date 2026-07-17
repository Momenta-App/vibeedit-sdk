from __future__ import annotations

import argparse
import json
from pathlib import Path

from vibeedit.catalog import search_catalog


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", default="benchmarks/routing-requests.json")
    parser.add_argument("--output")
    args = parser.parse_args()
    requests = json.loads(Path(args.requests).read_text(encoding="utf-8"))
    results = []
    for request in requests:
        matches = search_catalog(request["query"])
        selected = matches[0]["id"] if matches else None
        results.append({**request, "selectedId": selected, "correct": selected == request["expectedId"], "resultCount": len(matches)})
    report = {
        "requests": len(results),
        "correctFirstChoice": sum(item["correct"] for item in results),
        "accuracy": round(sum(item["correct"] for item in results) / max(1, len(results)), 6),
        "results": results,
    }
    payload = json.dumps(report, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
