# Artifact workflow

`.github/workflows/vibeedit-package.yml` is a build-only workflow. It runs the
Python and JavaScript validation suites, builds the npm tarball plus Python
wheel/source distribution, emits SHA-256 checksums, creates GitHub build
provenance attestations, and uploads private workflow artifacts for review.

The workflow has no npm, PyPI, GitHub Release, website deployment, or other
publication step. Publication requires a separate, explicitly approved change
after legal and release-readiness review.

The checked-in action references are immutable commit SHAs. The workflow is
triggered for package pull requests or by an explicit manual dispatch.
