#!/usr/bin/env python3
"""Verify tracked sources and compile Python without uploading local content."""
from pathlib import Path
import ast
import json
import subprocess

root = Path(__file__).resolve().parents[1]
files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
for name in filter(None, files):
    if any(part in {'PS3_GAME', 'GeneratedGameData', 'LocalGameData', 'GameDataIntermediate', 'ProprietaryAssets', 'Build'} for part in Path(name).parts):
        raise SystemExit('Forbidden generated/proprietary content tracked: ' + name)
    p = root / name
    if p.suffix == '.py':
        ast.parse(p.read_text(encoding='utf-8-sig'), filename=name)
    if p.suffix == '.json':
        json.loads(p.read_text(encoding='utf-8-sig'))
print('PASS: tracked source and local-content boundary checks')
