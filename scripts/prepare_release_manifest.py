"""Build an exact public bootstrap manifest; publication remains a separate gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tomllib
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--sdist', type=Path, required=True)
    parser.add_argument('--npm', type=Path, required=True)
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-f0-9]{40}', args.source_revision):
        raise ValueError('Pin a complete committed public source revision')
    root = Path(__file__).resolve().parent.parent
    npm = json.loads((root / 'package.json').read_text())
    python = tomllib.loads((root / 'pyproject.toml').read_text())['project']
    tag = 'v' + npm['version']
    base = 'https://github.com/Momenta-App/vibeedit-sdk/releases/download/' + tag + '/'
    def artifact(path, name=None):
        raw = path.read_bytes()
        return {'url':base + (name or path.name), 'sha256':hashlib.sha256(raw).hexdigest(), 'byteLength':len(raw)}
    value = {
        'schemaVersion':'vibeedit.release.v1', 'id':tag,
        'source':{'repository':'https://github.com/Momenta-App/vibeedit-sdk', 'revision':args.source_revision},
        'versions':{'python':python['version'], 'npm':npm['version'], 'pi':'1.3.0'},
        'artifacts':{'pythonWheel':artifact(args.wheel), 'pythonSource':artifact(args.sdist), 'npm':artifact(args.npm),
                     'coreRequirements':artifact(root / 'requirements-core.lock'), 'setupScript':artifact(root / 'skills/vibeedit-setup/scripts/setup.py')},
        'setupSkill':'https://raw.githubusercontent.com/Momenta-App/vibeedit-sdk/' + args.source_revision + '/skills/vibeedit-setup/SKILL.md',
        'setupSkillSha256':hashlib.sha256((root / 'skills/vibeedit-setup/SKILL.md').read_bytes()).hexdigest(),
        'customer':{'signup':'https://u83j0k7e5m.execute-api.ca-central-1.amazonaws.com/billing',
                    'api':'https://u83j0k7e5m.execute-api.ca-central-1.amazonaws.com', 'commercialMode':'metered-prepaid-with-optional-auto-topup'},
        'qualification':'Publish only alongside the exact-artifact platform matrix and complete launch acceptance evidence; a generated manifest alone is not launch proof.',
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as output:
        output.write(json.dumps(value,indent=2)+'\n')
    print(json.dumps({'ok':True,'manifest':str(args.output),'sha256':hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
