"""Replace unqualified legacy fonts with pinned OFL fonts; preserve parent digests."""
import hashlib
import json
import urllib.request
from urllib.parse import quote
from pathlib import Path

root = Path(__file__).resolve().parent.parent
policy = json.loads((root / 'scripts/font-policy.json').read_text())
runtime = root / 'catalog/text-runtime'
assets = runtime / 'assets/fonts'
for record in policy['fonts']:
    target = assets / record['filename']
    if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != record['sha256']:
        raw = urllib.request.urlopen(record['url'], timeout=30).read(record['byteLength'] + 1)
        if len(raw) != record['byteLength'] or hashlib.sha256(raw).hexdigest() != record['sha256']:
            raise ValueError('Pinned font/license integrity mismatch')
        target.write_bytes(raw)
replaced = []
for original in list(runtime.rglob('*')):
    if original.name in policy['replacements']:
        name = policy['replacements'][original.name]
        replaced.append({'original':original.relative_to(runtime).as_posix(),'parentSha256':hashlib.sha256(original.read_bytes()).hexdigest(),'replacement':original.with_name(name).relative_to(runtime).as_posix()})
        original.with_name(name).write_bytes((assets / name).read_bytes())
        original.unlink()
for path in runtime.rglob('*'):
    if path.suffix not in {'.html','.css','.js','.json'} or path.name in {'font-provenance.json','manifest.json'}:
        continue
    text = path.read_text()
    for before, after in policy['replacements'].items():
        text = text.replace(before, after)
        text = text.replace(quote(before), quote(after))
    path.write_text(text)
provenance_path = runtime / 'font-provenance.json'
previous = json.loads(provenance_path.read_text()) if provenance_path.exists() else {}
provenance_path.write_text(json.dumps({**policy,'adaptation':'Legacy unqualified fonts replaced for unrestricted commercial editing; font appearance intentionally changes. OFL terms govern fonts, MIT governs VibeEdit code.','replaced':previous.get('replaced',replaced)},indent=2)+'\n')
manifest_path = runtime / 'manifest.json'
manifest = json.loads(manifest_path.read_text())
manifest['fontPolicy'] = {'path':'font-provenance.json','sourceRevision':policy['sourceRevision'],'fidelity':'OFL replacements; no pixel-equivalence claim for affected font faces'}
manifest['files'] = [{'path':path.relative_to(runtime).as_posix(),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(runtime.rglob('*')) if path.is_file() and path != manifest_path]
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'ok':True,'fontsPinned':len(policy['fonts']),'replaced':len(replaced)}))
