"""Build a source/data ZIP without dependencies, secrets or private inputs."""
from pathlib import Path
import zipfile
import hashlib
import json

root=Path(__file__).resolve().parents[1]
target=root.parent/'library-files'/'Smart_ID_Photo_v0.2_LargeImages_15KB.zip'
target.parent.mkdir(parents=True,exist_ok=True)
allowed_dirs={'src','configs','tests','notebooks','examples','reports','tools','models'}
allowed_files={'README.md','pyproject.toml','requirements.txt','requirements-tested-linux.txt',
               'THIRD_PARTY_NOTICES.md','.gitignore','LICENSE','UPGRADE_COLAB.md'}
# Only include public benchmark exports currently referenced in the bundled report.
report=json.loads((root/'reports'/'preliminary-results.json').read_text())
public_outputs={str(entry[key]) for entry in report for key in ('output','preview') if entry.get(key)}
paths=[]
for path in sorted(root.rglob('*')):
    if not path.is_file(): continue
    relative=path.relative_to(root)
    if any(part in {'__pycache__','.pytest_cache'} or part.endswith('.egg-info') for part in relative.parts): continue
    if relative.suffix=='.pyc': continue
    if relative.parts[0] in allowed_dirs or str(relative) in allowed_files or str(relative) in public_outputs or str(relative) in {'input/.gitkeep','output/.gitkeep'}:
        paths.append(path)
with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as archive:
    for path in paths: archive.write(path,root.name+'/'+str(path.relative_to(root)))
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
print(json.dumps({'zip':str(target),'bytes':target.stat().st_size,'files':len(paths),
                  'sha256':hashlib.sha256(target.read_bytes()).hexdigest()},indent=2))
