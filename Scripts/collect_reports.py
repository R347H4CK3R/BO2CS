#!/usr/bin/env python3
"""Fetch the newest attempt of each CI report group without stale ZIP merging."""
import argparse
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
import zipfile

GROUPS = {
    'SimulatorBuildReports': ['simulator.json'],
    'DeviceBuildReports': ['device.json'],
    'SimulatorRuntimeReports': ['runtime.json','AUTOTEST_RESULT.json','SIMULATOR_TEST_REPORT.md','gameplay.png'],
    'PackageReports': ['package.json'],
    'IPAValidationReports': ['ipa.json','IPA_VALIDATION_REPORT.md','ipa-native-tools.log'],
}


def latest_reports(artifacts):
    selected={}
    for a in artifacts:
        name=a['name']
        if name not in GROUPS or a.get('expired'):
            continue
        previous=selected.get(name)
        if previous is None or (a['created_at'],a['id']) > (previous['created_at'],previous['id']):
            selected[name]=a
    return selected


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repository',required=True)
    p.add_argument('--run-id',required=True,type=int)
    p.add_argument('--output',default='Build/Reports')
    args=p.parse_args()
    pages=json.loads(subprocess.check_output(['gh','api','--paginate','--slurp',
        f'repos/{args.repository}/actions/runs/{args.run_id}/artifacts?per_page=100']))
    chosen=latest_reports([a for page in pages for a in page['artifacts']])
    root=Path(args.output);root.mkdir(parents=True,exist_ok=True)
    for name,artifact in chosen.items():
        with tempfile.TemporaryDirectory() as temporary:
            archive=Path(temporary)/'artifact.zip'
            with archive.open('wb') as f:
                subprocess.run(['gh','api',f'repos/{args.repository}/actions/artifacts/{artifact["id"]}/zip'],stdout=f,check=True,timeout=180)
            with zipfile.ZipFile(archive) as z:
                for member in z.infolist():
                    path=PurePosixPath(member.filename)
                    if path.is_absolute() or '..' in path.parts or '\\' in member.filename or ':' in member.filename:
                        raise ValueError('unsafe report ZIP')
                    if (member.external_attr>>16)&0o170000==0o120000:
                        raise ValueError('symlink in report ZIP')
                destination=root/'ReportSources'/name
                z.extractall(destination)
            for filename in GROUPS[name]:
                source=destination/filename
                if source.exists():shutil.copyfile(source,root/filename)
    manifest={'repository':args.repository,'build_run_id':args.run_id,
              'artifacts':{name:{k:a[k] for k in ('id','created_at','name')} for name,a in chosen.items()}}
    (root/'collection_manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':main()
