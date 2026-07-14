from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request


REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify that a GitHub repository is downloadable without authentication",
    )
    parser.add_argument("--repo", required=True, help="GitHub owner/name")
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args(argv)
    if not REPOSITORY.fullmatch(args.repo):
        parser.error("--repo must use the GitHub owner/name form")

    request = urllib.request.Request(
        f"https://api.github.com/repos/{args.repo}",
        headers={
            "Accept": "application/vnd.github+json",
            "Cache-Control": "no-cache",
            "User-Agent": "vibeedit-release-audit/0.1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        status = "not-public" if error.code == 404 else "unverifiable"
        print(
            json.dumps(
                {
                    "schemaVersion": "1.0.0",
                    "repository": args.repo,
                    "publiclyDownloadable": False,
                    "status": status,
                    "httpStatus": error.code,
                    "authenticationUsed": False,
                },
                indent=2,
            )
        )
        return 1 if error.code == 404 else 2
    except urllib.error.URLError as error:
        print(
            json.dumps(
                {
                    "schemaVersion": "1.0.0",
                    "repository": args.repo,
                    "publiclyDownloadable": False,
                    "status": "unverifiable",
                    "error": str(error.reason),
                    "authenticationUsed": False,
                },
                indent=2,
            )
        )
        return 2

    is_public = payload.get("private") is False and payload.get("visibility") == "public"
    print(
        json.dumps(
            {
                "schemaVersion": "1.0.0",
                "repository": args.repo,
                "publiclyDownloadable": is_public,
                "status": "public" if is_public else "not-public",
                "httpStatus": 200,
                "authenticationUsed": False,
                "visibility": payload.get("visibility"),
                "defaultBranch": payload.get("default_branch"),
                "url": payload.get("html_url"),
            },
            indent=2,
        )
    )
    return 0 if is_public else 1


if __name__ == "__main__":
    raise SystemExit(main())
