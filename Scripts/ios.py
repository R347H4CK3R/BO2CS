#!/usr/bin/env python3
"""Local/CI Xcode entrypoint. No GitHub-specific build behavior."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import time
import traceback
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'Build'
REPORTS = BUILD / 'Reports'
BUNDLE = 'io.github.r347h4ck3r.bo2cs'


def version(value):
    return tuple(int(v) for v in re.findall(r'\d+', value))


def select_simulator(data):
    candidates = []
    for runtime, devices in data.get('devices', {}).items():
        if 'iOS' not in runtime:
            continue
        for device in devices:
            name = device.get('name', '')
            if not device.get('isAvailable') or not name.startswith('iPhone'):
                continue
            rank = 3 if name == 'iPhone 16 Plus' else 2 if name == 'iPhone 16 Pro Max' else 1 if ('Plus' in name or 'Pro Max' in name) else 0
            candidates.append(((rank, version(name), version(runtime)), dict(device, runtime=runtime)))
    return max(candidates, key=lambda c: c[0])[1] if candidates else None


def run(command, log=None, timeout=1200, check=True, env=None):
    print('+', ' '.join(map(str, command)), flush=True)
    if log:
        REPORTS.mkdir(parents=True, exist_ok=True)
        with (REPORTS / log).open('w', encoding='utf-8') as f:
            p = subprocess.run(command, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, timeout=timeout, env=env)
        if p.returncode:
            print((REPORTS / log).read_text(errors='replace')[-12000:])
    else:
        p = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout, env=env)
        print(p.stdout, end='')
        print(p.stderr, end='', file=sys.stderr)
    if check and p.returncode:
        raise RuntimeError(f'command failed ({p.returncode}); see {log or command[0]}')
    return p


def write_receipt(name, status, **details):
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / (name + '.json')).write_text(json.dumps(dict(status=status, **details), indent=2))


def environment():
    if sys.platform != 'darwin':
        raise RuntimeError('Xcode execution requires macOS; use the iOS Build GitHub Actions workflow')
    candidates = []
    for app in Path('/Applications').glob('Xcode*.app'):
        p = app / 'Contents/Info.plist'
        if not p.exists():
            continue
        info = plistlib.loads(p.read_bytes())
        v = info.get('CFBundleShortVersionString', '')
        print(f'Xcode candidate: {app} {v}')
        if 'beta' not in (app.name + v).lower() and version(v) >= (16,):
            candidates.append((version(v), app))
    if os.environ.get('DEVELOPER_DIR'):
        print('Using explicit DEVELOPER_DIR:', os.environ['DEVELOPER_DIR'])
    elif candidates:
        selected = max(candidates, key=lambda c: c[0])[1] / 'Contents/Developer'
        os.environ['DEVELOPER_DIR'] = str(selected)
    else:
        raise RuntimeError('No stable Xcode >=16 found; set DEVELOPER_DIR to a compatible installation')
    run(['xcodebuild', '-version'], 'xcode-version.log')
    run(['xcodebuild', '-showsdks'], 'xcode-sdks.log')
    run(['xcrun', 'simctl', 'list', 'devices', 'available'], 'simulator-devices.log')
    run(['xcrun', 'simctl', 'list', 'runtimes'], 'simulator-runtimes.log')
    print((REPORTS / 'xcode-version.log').read_text())
    print((REPORTS / 'simulator-devices.log').read_text())
    print((REPORTS / 'simulator-runtimes.log').read_text())


def discover():
    p = run(['xcrun', 'simctl', 'list', 'devices', 'available', '-j'], timeout=60)
    return select_simulator(json.loads(p.stdout))


def fixtures():
    run([sys.executable, 'Tools/PS3AssetConverter/convert_assets.py', '--source', 'Tests/Fixtures',
         '--intermediate', 'Build/Intermediate', '--output', 'Build/GameData'], 'converter.log')
    shutil.copyfile(ROOT / 'GameData/weapons.json', BUILD / 'GameData/weapons.json')


def build(kind):
    write_receipt(kind, 'BUILDING')
    environment()
    fixtures()
    simulator = kind == 'simulator'
    sdk = 'iphonesimulator' if simulator else 'iphoneos'
    device = discover() if simulator else None
    destination = 'id=' + device['udid'] if device else 'generic/platform=iOS Simulator' if simulator else 'generic/platform=iOS'
    directory = BUILD / kind
    run(['cmake', '-S', '.', '-B', str(directory), '-G', 'Xcode', '-DCMAKE_SYSTEM_NAME=iOS',
         '-DCMAKE_OSX_SYSROOT=' + sdk, '-DCMAKE_OSX_ARCHITECTURES=arm64',
         '-DCMAKE_OSX_DEPLOYMENT_TARGET=16.0', '-DBO2CS_IOS=ON', '-DBUILD_TESTING=OFF',
         '-DFETCHCONTENT_BASE_DIR=' + str(BUILD / 'Dependencies' / kind)], kind + '-configure.log')
    common = ['xcodebuild', '-project', str(directory / 'BO2CS.xcodeproj'), '-scheme', 'GameName',
              '-configuration', 'Release', '-sdk', sdk, '-destination', destination]
    # CMake resolves pinned SDL2/JSON sources; no Swift packages are declared.
    run(common + ['-resolvePackageDependencies'], kind + '-resolve-packages.log')
    run(common + ['build', 'CODE_SIGNING_ALLOWED=NO', 'CODE_SIGNING_REQUIRED=NO',
                  'DEVELOPMENT_TEAM=', 'ARCHS=arm64', 'ONLY_ACTIVE_ARCH=NO'], kind + '-build.log')
    app = directory / ('Release-' + sdk) / 'GameName.app'
    if not (app / 'GameName').is_file():
        raise RuntimeError('Xcode build did not produce expected bundle: ' + str(app))
    archive = BUILD / ('SimulatorBuild.zip' if simulator else 'DeviceBuild.zip')
    run(['ditto', '-c', '-k', '--keepParent', str(app), str(archive)], kind + '-archive.log')
    write_receipt(kind, 'PASS', app=str(app.relative_to(ROOT)), sdk=sdk, destination=destination,
                  simulator_device=device, developer_dir=os.environ.get('DEVELOPER_DIR'))


def unpack(archive, target):
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if Path(name).is_absolute() or '..' in Path(name).parts:
                raise ValueError('unsafe bundle ZIP')
    run(['ditto', '-x', '-k', str(archive), str(target)])
    app = target / 'GameName.app'
    if not (app / 'GameName').exists():
        raise RuntimeError('missing app executable after extraction')
    return app


def runtime():
    environment()
    device = None
    booted = False
    result = {'status': 'FAIL', 'passed': False, 'reason': 'runtime did not finish'}
    app = unpack(BUILD / 'SimulatorBuild.zip', BUILD / 'SimulatorRun')
    start = time.time()
    try:
        device = discover()
        if not device:
            result = {'status': 'UNAVAILABLE', 'passed': None, 'reason': 'No available iPhone simulator'}
            return
        udid = device['udid']
        run(['xcrun', 'simctl', 'boot', udid], 'simulator-boot.log', timeout=120, check=False)
        boot_status = run(['xcrun', 'simctl', 'bootstatus', udid, '-b'], 'simulator-bootstatus.log', timeout=240, check=False)
        if boot_status.returncode:
            result = {'status': 'UNAVAILABLE', 'passed': None, 'reason': 'Simulator boot failed; see boot logs'}
            return
        booted = True
        run(['xcrun', 'simctl', 'install', udid, str(app)], 'simulator-install.log', timeout=120)
        # Explicit UUID avoids accidental launch into a different booted device.
        env = dict(os.environ, SIMCTL_CHILD_AUTOTEST='1')
        run(['xcrun', 'simctl', 'launch', '--terminate-running-process',
             '--stdout=' + str(REPORTS / 'app-stdout.log'), '--stderr=' + str(REPORTS / 'app-stderr.log'),
             udid, BUNDLE], 'simulator-launch.log', timeout=60, env=env)
        container = Path(run(['xcrun', 'simctl', 'get_app_container', udid, BUNDLE, 'data']).stdout.strip())
        logs = container / 'Documents/Logs'
        deadline = time.monotonic() + 120
        captured = False
        while time.monotonic() < deadline:
            if not captured and time.time() - start > 30:
                run(['xcrun', 'simctl', 'io', udid, 'screenshot', str(REPORTS / 'gameplay.png')], 'screenshot.log', check=False)
                captured = True
            file = logs / 'AUTOTEST_RESULT.json'
            if file.exists():
                result = json.loads(file.read_text())
                if result.get('status') == 'PASS' and (result.get('duration_seconds', 0) < 60 or result.get('frames', 0) < 60):
                    result = {'status': 'FAIL', 'passed': False, 'reason': 'Autotest evidence below minimum duration/frame count'}
                break
            time.sleep(2)
        else:
            result = {'status': 'FAIL', 'passed': False, 'reason': 'No AUTOTEST_RESULT within 120 seconds: crash, hang or failed initialization'}
        if logs.exists():
            shutil.copytree(logs, REPORTS / 'RuntimeLogs', dirs_exist_ok=True)
        run(['xcrun', 'simctl', 'spawn', udid, 'log', 'show', '--last', '5m', '--style', 'compact',
             '--predicate', 'process == "GameName"'], 'simulator-os.log', timeout=90, check=False)
    except subprocess.TimeoutExpired as exc:
        result = {'status': 'FAIL' if booted else 'UNAVAILABLE', 'passed': False if booted else None,
                  'reason': 'timeout: ' + str(exc)}
    except Exception as exc:
        result = {'status': 'FAIL', 'passed': False, 'reason': str(exc)}
    finally:
        if device:
            run(['xcrun', 'simctl', 'terminate', device['udid'], BUNDLE], 'simulator-terminate.log', check=False, timeout=30)
            run(['xcrun', 'simctl', 'shutdown', device['udid']], 'simulator-shutdown.log', check=False, timeout=60)
        crashdir = Path.home() / 'Library/Logs/DiagnosticReports'
        for crash in crashdir.glob('GameName*'):
            if crash.is_file() and crash.stat().st_mtime >= start:
                shutil.copyfile(crash, REPORTS / crash.name)
        result.update(simulator=device, performance_scope='simulator only, not device performance',
                      device_ipa_executed=False, exit_reason=result.get('exit_reason', 'not observable; see runtime/OS logs'))
        (REPORTS / 'AUTOTEST_RESULT.json').write_text(json.dumps(result, indent=2))
        write_receipt('runtime', result['status'], **{k: v for k, v in result.items() if k != 'status'})
        (REPORTS / 'SIMULATOR_TEST_REPORT.md').write_text('# Simulator runtime test\n\n' + json.dumps(result, indent=2) +
            '\n\nThe simulator app is a separate build. The device IPA was not executed here.\n')
    if result['status'] == 'FAIL':
        raise RuntimeError(result['reason'] if 'reason' in result else 'Gameplay autotest failed')


def package():
    environment()
    app = unpack(BUILD / 'DeviceBuild.zip', BUILD / 'Payload')
    run(['ditto', '-c', '-k', '--keepParent', str(app.parent), str(BUILD / 'GameName-unsigned.ipa')], 'package.log')
    write_receipt('package', 'PASS', ipa='Build/GameName-unsigned.ipa', playable=False)


def validate():
    run([sys.executable, 'Tools/validate_ipa.py', 'Build/GameName-unsigned.ipa'], 'validation.log')


def report():
    def receipt(name):
        file = REPORTS / (name + '.json')
        return json.loads(file.read_text()) if file.exists() else {'status': 'NOT_RUN'}
    runtime_result = receipt('runtime')
    progress = {'current_phase': 2, 'completed_phases': [1], 'engine': 'SDL2 + original C++ runtime',
                'simulator_build_status': receipt('simulator')['status'],
                'simulator_test_status': runtime_result['status'], 'device_build_status': receipt('device')['status'],
                'ipa_validation_status': receipt('ipa')['status'],
                'ipa_path': 'Build/GameName-unsigned.ipa' if receipt('ipa')['status'] == 'PASS' else None,
                'known_blockers': ['User PS3 game path and unencrypted samples unavailable'],
                'failed_tests': [n for n in ('simulator', 'runtime', 'device', 'ipa') if receipt(n)['status'] == 'FAIL'],
                'last_successful_build': None, 'full_project_complete': False}
    if progress['simulator_build_status'] == progress['device_build_status'] == 'PASS':
        progress['completed_phases'].append(2)
        progress['current_phase'] = 6
        progress['last_successful_build'] = 'GitHub Actions receipts attached; original fixture only'
    (REPORTS / 'PROJECT_PROGRESS.json').write_text(json.dumps(progress, indent=2))
    if not (REPORTS / 'AUTOTEST_RESULT.json').exists():
        (REPORTS / 'AUTOTEST_RESULT.json').write_text(json.dumps({'status': 'NOT_RUN', 'passed': None}))
    if not (REPORTS / 'SIMULATOR_TEST_REPORT.md').exists():
        (REPORTS / 'SIMULATOR_TEST_REPORT.md').write_text('# Simulator runtime test\n\nNOT RUN. Inspect upstream job failures.\n')
    if not (REPORTS / 'IPA_VALIDATION_REPORT.md').exists():
        (REPORTS / 'IPA_VALIDATION_REPORT.md').write_text('# IPA validation\n\nNOT RUN. No validated package received.\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['environment', 'fixtures', 'simulator', 'device', 'runtime', 'package', 'validate', 'ipa', 'test', 'report'])
    args = parser.parse_args()
    REPORTS.mkdir(parents=True, exist_ok=True)
    try:
        if args.action in ('simulator', 'device'):
            build(args.action)
        elif args.action == 'ipa':
            build('device')
            package()
            validate()
        elif args.action == 'test':
            run([sys.executable, '-m', 'unittest', 'discover', '-s', 'Tests', '-v'], 'python-tests.log')
            run(['cmake', '-S', '.', '-B', 'Build/Host', '-DBO2CS_IOS=OFF', '-DBUILD_TESTING=ON'], 'host-configure.log')
            run(['cmake', '--build', 'Build/Host', '--config', 'Release'], 'host-build.log')
            run(['ctest', '--test-dir', 'Build/Host', '-C', 'Release', '--output-on-failure'], 'unit-tests.log')
            build('simulator')
            runtime()
        else:
            globals()[args.action]()
    except Exception as exc:
        write_receipt(args.action, 'FAIL', reason=str(exc))
        traceback.print_exc()
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
