# Artifact workflow

`.github/workflows/vibeedit-package.yml` is a build-only workflow. It runs the
Python and JavaScript validation suites, builds the npm tarball plus Python
wheel/source distribution, emits flat GitHub-release and artifact-relative
SHA-256 checksums, creates
GitHub build-provenance attestations for public workflow dispatches, and
uploads workflow artifacts for review.

Each portable matrix job also runs `scripts/smoke_release_artifacts.py` against
the wheel and npm tarball it just built. The script creates new Python and Node
environments, installs the exact archives, performs browser setup, renders and
verifies both generated and mixed HTML/media examples, exercises the packaged
catalog and skill lifecycle, initializes and calls the 10-tool MCP adapter,
imports the Node API, validates CompositionSpec, and requires a zero-vulnerability
production dependency audit. Source-tree tests cannot substitute for this gate.

The workflow has no npm, PyPI, GitHub Release, website deployment, or other
release step. The release owner explicitly approved the `0.1.0-beta.1` public
GitHub prerelease. It is published manually only after the exact workflow run
passes and its downloaded checksums, archive audit, and attestations verify.
Registry publication remains conditional on package-owner credentials.

`dist/SHA256SUMS` uses flat filenames so it verifies files downloaded from a
GitHub release into one directory. `dist/SHA256SUMS.tree` retains `npm/` and
`python/` paths for verification inside the complete workflow artifact. Do not
publish the tree manifest as the release's primary `SHA256SUMS` file.

The checked-in action references are immutable commit SHAs. The workflow is
triggered for package pull requests or by an explicit manual dispatch.

## Registry beta handoff

`.github/workflows/vibeedit-registry-beta.yml` is the only registry publication
path. It is manual, publishes exactly one registry per reviewed dispatch, uses
the protected `registry-beta` GitHub environment, and requires the literal
confirmation `publish:<registry>:<release_tag>`.

The job does not rebuild packages. It downloads the existing GitHub prerelease
wheel, source distribution, and npm tarball; binds their versions to the tag;
checks `SHA256SUMS.release`; checks the archive-audit hashes, byte counts, and
forbidden-entry result; and verifies GitHub build attestations. Only then does
it request a short-lived OIDC publishing identity. No long-lived npm or PyPI
token is accepted by the workflow. After publication, it waits for the exact
version to become publicly resolvable, installs it into a new temporary npm
project or Python virtual environment, and requires the installed CLI to report
the tag-bound version. A successful registry job therefore proves publication
and a clean public install of the exact beta artifact.

The protected `registry-beta` GitHub environment was created on 2026-07-15
with a required reviewer and protected-branch deployment policy. Registry-owner
setup is still required before the workflow's first use:

1. Confirm the `registry-beta` environment and required-reviewer policy remain
   enabled.
2. On PyPI, create a pending trusted publisher for project `vibeedit`, owner
   `Momenta-App`, repository `vibeedit-sdk`, workflow
   `vibeedit-registry-beta.yml`, environment `registry-beta`.
3. In the existing npm `vibeedit` package settings, configure the same GitHub
   organization, repository, workflow filename, and environment, allowing
   `npm publish`.
4. Dispatch the workflow once with registry `pypi` and confirmation
   `publish:pypi:v0.1.0-beta.1`.
5. Dispatch it separately with registry `npm` and confirmation
   `publish:npm:v0.1.0-beta.1`.
6. Retain the workflow's clean public-install proof, then independently verify
   `uv tool install vibeedit` and `npm install vibeedit@beta` before changing
   any documentation to claim registry availability. Keep npm's stable
   `latest` tag unchanged during beta review.

PyPI supports a pending trusted publisher for a first release. npm already has
the legacy `vibeedit` package and requires an authenticated owner to establish
its trusted-publisher relationship. Those two registry-account settings cannot
be created from this unauthenticated checkout.
