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
- Built-in HTML components escape text/attributes. Arbitrary local HTML runs
  only when a composition explicitly selects `vibeedit://motion/html` or
  `vibeedit://motion/web-project`; it is executable code and has the same trust
  level as a local script launched by the user.
- `vibeedit://motion/html-css` is the narrower raw authoring contract. It rejects
  authored scripts, event-handler attributes, `javascript:` URLs, embedded
  documents, and meta refresh; a restrictive content-security policy also
  disables scripts, connections, frames, and plugins inside the layer.
- Browser rendering runs locally and does not fetch network assets.
- Custom project assets are exposed through a traversal-safe loopback server
  rooted at the composition directory. The server has no directory listing and
  Chromium aborts non-loopback network requests. Bundle libraries and licensed
  fonts locally instead of using a CDN.
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
