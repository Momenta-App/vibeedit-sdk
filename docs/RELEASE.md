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
catalog and skill lifecycle, initializes and calls the MCP adapter, including its bounded `agent_command` tool,
imports the Node API, validates CompositionSpec, and requires a zero-vulnerability
production dependency audit. Source-tree tests cannot substitute for this gate.

The workflow builds reviewable artifacts and does not publish packages or deploy a
backend. The agent-package candidate uses npm `0.2.0-beta.1` and Python `0.2.0b1`;
[LAUNCH_STATUS.md](LAUNCH_STATUS.md) records its open acceptance gates. A source
checkpoint or successful workflow is not launch approval. Publish only the exact
qualified artifacts after their downloaded checksums, archive audit, attestations
and complete customer journeys verify.

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

The protected `registry-beta` GitHub environment retains its required reviewer.
The owner completed account authentication and approved the scoped npm publisher
and PyPI pending publisher on 2026-10-20: project/package `vibeedit`, GitHub owner
`Momenta-App`, repository `vibeedit-sdk`, workflow
`vibeedit-registry-beta.yml`, environment `registry-beta`. npm allows publish;
dist-tag administration remains disabled. A pending PyPI publisher creates the
project only on its first successful publication. These settings do not prove
registry availability; a final protected-workflow dispatch and clean public
install remain required.

1. Verify the environment's reviewer policy and the exact final release manifest.
2. Complete all launch acceptance gates and publish its qualified GitHub
   prerelease archives, checksums, archive audit and attestations.
3. Dispatch the registry workflow separately for `pypi` and `npm`, with
   `publish:<registry>:v0.2.0-beta.1` and the same exact release tag.
4. Retain each workflow's clean public-install proof and independently verify
   installation of those exact versions in fresh environments. Keep npm's stable
   `latest` tag unchanged during beta review.

Platform jobs retain their Python JUnit results and exact-archive smoke receipt
as separate qualification artifacts, including on failure. Both build jobs have
30-minute observation limits. A timeout or failed run supplies no release
attestation and never changes native paid-job recovery rules.
