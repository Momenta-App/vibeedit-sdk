# Third-Party Notices

The lightweight vertical slice invokes user-installed FFmpeg and FFprobe as
external programs. FFmpeg is an independent project and is distributed under
its own LGPL/GPL licensing options; the license of the user's FFmpeg build
governs that binary.

The base JavaScript package uses Ajv and ajv-formats under MIT licenses. The
base Python package uses jsonschema and its declared dependencies under their
respective package licenses.

Optional integrations:

- Playwright 1.61.0 — Apache License 2.0.
- Chromium revision 1228 — BSD-style license plus bundled third-party notices;
  installed only by explicit `vibeedit setup --browser`.
- NumPy — BSD-3-Clause plus licenses recorded in its wheel metadata.
- Pillow — MIT-CMU.
- OpenCV Python headless — Apache License 2.0.
- ONNX Runtime — MIT.
- ONNX Model Zoo SSD-MobileNetV1-12 checkpoint, commit
  `019281f3fcb151a90e491f3b2f0273f9f31bd6be` — the model card states MIT,
  while the repository metadata states Apache-2.0; COCO dataset terms also
  apply. The checkpoint is not shipped and is fetched only by explicit
  `vibeedit setup --vision` with exact size/SHA-256 verification. The release
  owner approved this optional integration for public beta testing while
  preserving the upstream terms and this mixed-license disclosure.
- PyTorch 2.12.0 and torchvision 0.27.0 — BSD-style licenses.
- Hydra Core 1.3.2 — MIT; iopath 0.1.10 — MIT; tqdm 4.67.1 — MPL-2.0/MIT.
- Meta Segment Anything Model 2 source revision
  `2b90b9f5ceec907a1c18123530e92e794ad901a4` and SAM 2.1 Hiera Tiny
  checkpoint — Apache-2.0. They are not shipped in the package and are fetched
  from official URLs only by explicit `vibeedit setup --sam`, with declared
  sizes and SHA-256 verification.

The generated preset inventory includes deterministic VibeEdit-owned NumPy
implementations informed by public effect vocabularies and documentation. A
subset adapts FreeCut effect names and default concepts; FreeCut is MIT-licensed
and no FreeCut WebGPU source is bundled. Other catalog references identify
FFmpeg, MoviePy, OpenCV, Pillow, and scikit-image documentation for vocabulary
and production context; the shipped backend does not bundle those projects'
source.

No third-party recorded media is included in the beta. All 13 preview/audio
assets are entirely VibeEdit-generated, identified, and hash-bound in
`catalog/assets.json`. The release owner confirmed that the included canonical
VibeEdit material is approved and that the named open-source projects remain
optional integrations under their own terms rather than VibeEdit-owned assets.
