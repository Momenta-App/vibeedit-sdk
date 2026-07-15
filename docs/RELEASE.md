# Artifact workflow

`.github/workflows/vibeedit-package.yml` is a build-only workflow. It runs the
Python and JavaScript validation suites, builds the npm tarball plus Python
wheel/source distribution, emits flat GitHub-release and artifact-relative
SHA-256 checksums, creates
GitHub build-provenance attestations for public workflow dispatches, and
uploads workflow artifacts for review.

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
