from __future__ import annotations

import argparse
import json
from pathlib import Path

from vibeedit.catalog import compact_catalog_result, search_catalog


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", default="benchmarks/routing-requests.json")
    parser.add_argument("--output")
    args = parser.parse_args()
    requests = json.loads(Path(args.requests).read_text(encoding="utf-8"))
    results = []
    for request in requests:
        matches = search_catalog(request["query"], category=request.get("category"), capability=request.get("capability"), platform=request.get("platform"))
        selected = matches[0]["id"] if matches else None
        expected_in_top_three = request["expectedId"] in [item["id"] for item in matches[:3]] if request["expectedId"] else selected is None
        compact = [compact_catalog_result(item, request["query"]) for item in matches[:5]]
        results.append({**request, "selectedId": selected, "correct": selected == request["expectedId"], "expectedInTopThree": expected_in_top_three, "resultCount": len(matches), "compactTopFiveBytes": len(json.dumps(compact, separators=(",", ":")).encode()), "skillResultsInTopFive": sum(item["category"] == "skill" for item in matches[:5])})
    report = {
        "requests": len(results),
        "correctFirstChoice": sum(item["correct"] for item in results),
        "accuracy": round(sum(item["correct"] for item in results) / max(1, len(results)), 6),
        "topThreeRecall": round(sum(item["expectedInTopThree"] for item in results) / max(1, len(results)), 6),
        "meanCompactTopFiveBytes": round(sum(item["compactTopFiveBytes"] for item in results) / max(1, len(results)), 3),
        "skillBodiesLoaded": 0,
        "searchToolCallsPerRequest": 1,
        "finalTaskSuccess": "not-measured-by-routing-only-benchmark",
        "results": results,
    }
    payload = json.dumps(report, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
