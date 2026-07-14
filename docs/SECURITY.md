# Security and Trust Boundaries

VibeEdit reads local CompositionSpecs and media, invokes local executables, and
writes user-selected outputs and cache artifacts. It does not require a cloud
service. Network access occurs only during an explicit setup command for
approved pinned browser/vision packages and runtimes. SAM model downloads occur
only when the user explicitly requests `setup --sam` or `setup --all`.

- Subprocesses receive argument arrays; user values are not interpolated into a
  shell command.
- Local paths are validated as files before media execution.
- Catalog entries are JSON data and never executed.
- Built-in HTML components escape text/attributes. Arbitrary third-party HTML
  is not loaded by the release runtime.
- Browser rendering runs locally and does not fetch network assets.
- Browser setup delegates archive verification to the pinned Playwright
  downloader, records the resolved executable SHA-256, and rejects a changed
  executable for the same Playwright version on subsequent setup runs.
- Skill updates/removals stop when installed files differ from their recorded
  checksum.
- Model manifests require a version, source, license decision, file checksum,
  and provider validation before setup can download them.
- SAM setup checks the declared byte size and SHA-256 while streaming both the
  official source archive and checkpoint. Extraction rejects links, parent
  traversal, and paths outside the VibeEdit cache. A partial or mismatched
  download is deleted and never promoted into the runtime directory.
- Package validation scans text release contents for common secret/private-key
  patterns and absolute developer paths.

Untrusted CompositionSpecs can request local file reads and expensive renders.
Run them with ordinary user permissions in a restricted working directory.
Treat optional browser components, plugins, model files, and external FFmpeg
builds as separate supply-chain inputs. The portable object checkpoint is about
29.5 MB; SAM source and weights are about 211.7 MB before Python runtime
dependencies and execute local model code with access
to the selected media and output path.
