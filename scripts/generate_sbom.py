import json
from pathlib import Path


root = Path(__file__).resolve().parent.parent
version = json.loads((root / "package.json").read_text(encoding="utf-8"))["version"]
document = {
    "spdxVersion": "SPDX-2.3",
    "dataLicense": "CC0-1.0",
    "SPDXID": "SPDXRef-DOCUMENT",
    "name": f"vibeedit-{version}",
    "documentNamespace": f"https://vibeedit.com/sbom/vibeedit-{version}",
    "creationInfo": {"created": "2026-07-14T00:00:00Z", "creators": [f"Tool: VibeEdit SBOM generator {version}"]},
    "packages": [
        {"name": "vibeedit", "SPDXID": "SPDXRef-Package-VibeEdit", "versionInfo": version, "downloadLocation": "NOASSERTION", "licenseConcluded": "LicenseRef-VibeEdit", "licenseDeclared": "LicenseRef-VibeEdit", "copyrightText": "Copyright Attention Engine Inc."},
        {"name": "ajv", "SPDXID": "SPDXRef-Package-Ajv", "versionInfo": "8.20.0", "downloadLocation": "https://www.npmjs.com/package/ajv", "licenseConcluded": "MIT", "licenseDeclared": "MIT", "copyrightText": "NOASSERTION"},
        {"name": "ajv-formats", "SPDXID": "SPDXRef-Package-AjvFormats", "versionInfo": "3.0.1", "downloadLocation": "https://www.npmjs.com/package/ajv-formats", "licenseConcluded": "MIT", "licenseDeclared": "MIT", "copyrightText": "NOASSERTION"},
        {"name": "jsonschema", "SPDXID": "SPDXRef-Package-Jsonschema", "versionInfo": "4.23-or-later-less-than-5", "downloadLocation": "https://pypi.org/project/jsonschema/", "licenseConcluded": "MIT", "licenseDeclared": "MIT", "copyrightText": "NOASSERTION"},
        {"name": "playwright", "SPDXID": "SPDXRef-Package-Playwright", "versionInfo": "1.61.0", "downloadLocation": "https://playwright.dev/", "licenseConcluded": "Apache-2.0", "licenseDeclared": "Apache-2.0", "copyrightText": "Copyright Microsoft Corporation"},
        {"name": "numpy", "SPDXID": "SPDXRef-Package-NumPy", "versionInfo": "2.4.6-py311-or-2.5.1-py312plus", "downloadLocation": "https://pypi.org/project/numpy/", "licenseConcluded": "NOASSERTION", "licenseDeclared": "BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0", "copyrightText": "NOASSERTION"},
        {"name": "pillow", "SPDXID": "SPDXRef-Package-Pillow", "versionInfo": "11.3.0", "downloadLocation": "https://pypi.org/project/Pillow/", "licenseConcluded": "MIT-CMU", "licenseDeclared": "MIT-CMU", "copyrightText": "NOASSERTION"},
        {"name": "opencv-python-headless", "SPDXID": "SPDXRef-Package-OpenCV", "versionInfo": "4.13.0.92", "downloadLocation": "https://pypi.org/project/opencv-python-headless/", "licenseConcluded": "Apache-2.0", "licenseDeclared": "Apache-2.0", "copyrightText": "Copyright OpenCV contributors"},
        {"name": "onnxruntime", "SPDXID": "SPDXRef-Package-ONNXRuntime", "versionInfo": "1.27.0", "downloadLocation": "https://pypi.org/project/onnxruntime/", "licenseConcluded": "MIT", "licenseDeclared": "MIT", "copyrightText": "Copyright Microsoft Corporation"},
        {"name": "torch", "SPDXID": "SPDXRef-Package-Torch", "versionInfo": "2.12.0", "downloadLocation": "https://pypi.org/project/torch/", "licenseConcluded": "BSD-3-Clause", "licenseDeclared": "BSD-3-Clause", "copyrightText": "Copyright PyTorch contributors"},
        {"name": "torchvision", "SPDXID": "SPDXRef-Package-Torchvision", "versionInfo": "0.27.0", "downloadLocation": "https://pypi.org/project/torchvision/", "licenseConcluded": "BSD-3-Clause", "licenseDeclared": "BSD-3-Clause", "copyrightText": "Copyright PyTorch contributors"},
        {"name": "hydra-core", "SPDXID": "SPDXRef-Package-HydraCore", "versionInfo": "1.3.2", "downloadLocation": "https://pypi.org/project/hydra-core/", "licenseConcluded": "MIT", "licenseDeclared": "MIT", "copyrightText": "Copyright Meta Platforms, Inc. and affiliates"},
        {"name": "iopath", "SPDXID": "SPDXRef-Package-Iopath", "versionInfo": "0.1.10", "downloadLocation": "https://pypi.org/project/iopath/", "licenseConcluded": "MIT", "licenseDeclared": "MIT", "copyrightText": "Copyright Facebook, Inc. and affiliates"},
        {"name": "tqdm", "SPDXID": "SPDXRef-Package-Tqdm", "versionInfo": "4.67.1", "downloadLocation": "https://pypi.org/project/tqdm/", "licenseConcluded": "MPL-2.0 OR MIT", "licenseDeclared": "MPL-2.0 OR MIT", "copyrightText": "Copyright tqdm contributors"},
        {"name": "ssd-mobilenet-v1-12", "SPDXID": "SPDXRef-Package-SSDMobileNet", "versionInfo": "019281f3fcb151a90e491f3b2f0273f9f31bd6be", "downloadLocation": "https://huggingface.co/onnxmodelzoo/ssd_mobilenet_v1_12", "checksums": [{"algorithm": "SHA256", "checksumValue": "b8fba5e404077d4048d27fcd1667e85e27e192eb9bf51e696c46a3acd7d21058"}], "licenseConcluded": "NOASSERTION", "licenseDeclared": "MIT", "copyrightText": "NOASSERTION", "comment": "Optional 29,461,455-byte object detector. Model card states MIT; repository metadata states Apache-2.0; COCO dataset terms apply. Not distributed in package archives."},
        {"name": "sam2-source", "SPDXID": "SPDXRef-Package-SAM2Source", "versionInfo": "2b90b9f5ceec907a1c18123530e92e794ad901a4", "downloadLocation": "https://github.com/facebookresearch/sam2", "checksums": [{"algorithm": "SHA256", "checksumValue": "1f2fbfad3ffa38110368abac76c6ef9df9c282a66d5c2807bc94abf4d2fb30f8"}], "licenseConcluded": "Apache-2.0", "licenseDeclared": "Apache-2.0", "copyrightText": "Copyright Meta Platforms, Inc.", "comment": "Optional 55,645,345-byte source archive downloaded only by explicit setup; not distributed in package archives."},
        {"name": "sam2.1-hiera-tiny", "SPDXID": "SPDXRef-Package-SAM21Tiny", "versionInfo": "2024-09-29", "downloadLocation": "https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt", "checksums": [{"algorithm": "SHA256", "checksumValue": "7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69"}], "licenseConcluded": "Apache-2.0", "licenseDeclared": "Apache-2.0", "copyrightText": "Copyright Meta Platforms, Inc.", "comment": "Optional 156,008,466-byte checkpoint downloaded only by explicit setup; not distributed in package archives."},
        {"name": "chromium", "SPDXID": "SPDXRef-Package-Chromium", "versionInfo": "playwright-revision-1228", "downloadLocation": "NOASSERTION", "licenseConcluded": "NOASSERTION", "licenseDeclared": "BSD-3-Clause", "copyrightText": "Copyright Chromium contributors", "comment": "Optional browser runtime installed explicitly by vibeedit setup --browser; bundled Chromium third-party notices apply."},
        {"name": "ffmpeg", "SPDXID": "SPDXRef-Package-FFmpeg", "versionInfo": "user-supplied", "downloadLocation": "https://ffmpeg.org/", "licenseConcluded": "NOASSERTION", "licenseDeclared": "NOASSERTION", "copyrightText": "Copyright FFmpeg contributors", "comment": "External binary; actual LGPL/GPL configuration is determined by the user's build."}
    ],
    "relationships": [
        {"spdxElementId": "SPDXRef-DOCUMENT", "relationshipType": "DESCRIBES", "relatedSpdxElement": "SPDXRef-Package-VibeEdit"},
        *({"spdxElementId": "SPDXRef-Package-VibeEdit", "relationshipType": "DEPENDS_ON", "relatedSpdxElement": package} for package in ["SPDXRef-Package-Ajv", "SPDXRef-Package-AjvFormats", "SPDXRef-Package-Jsonschema"]),
        *({"spdxElementId": package, "relationshipType": "OPTIONAL_DEPENDENCY_OF", "relatedSpdxElement": "SPDXRef-Package-VibeEdit"} for package in ["SPDXRef-Package-Playwright", "SPDXRef-Package-NumPy", "SPDXRef-Package-Pillow", "SPDXRef-Package-OpenCV", "SPDXRef-Package-ONNXRuntime", "SPDXRef-Package-Torch", "SPDXRef-Package-Torchvision", "SPDXRef-Package-HydraCore", "SPDXRef-Package-Iopath", "SPDXRef-Package-Tqdm", "SPDXRef-Package-Chromium", "SPDXRef-Package-SSDMobileNet", "SPDXRef-Package-SAM2Source", "SPDXRef-Package-SAM21Tiny"]),
        {"spdxElementId": "SPDXRef-Package-VibeEdit", "relationshipType": "HAS_PREREQUISITE", "relatedSpdxElement": "SPDXRef-Package-FFmpeg"},
        {"spdxElementId": "SPDXRef-Package-Chromium", "relationshipType": "RUNTIME_DEPENDENCY_OF", "relatedSpdxElement": "SPDXRef-Package-Playwright"}
    ],
    "hasExtractedLicensingInfos": [{"licenseId": "LicenseRef-VibeEdit", "extractedText": (root / "LICENSE.md").read_text(encoding="utf-8")}],
}
(root / "SBOM.spdx.json").write_text(json.dumps(document, indent=2) + "\n")
