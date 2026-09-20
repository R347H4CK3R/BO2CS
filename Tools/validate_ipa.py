#!/usr/bin/env python3
"""Validate device package structure and Mach-O platforms without executing it."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import plistlib
import re
import struct
import subprocess
import sys
import tempfile
import zipfile


def inspect_macho(data):
    if len(data) < 32 or data[:4] != b'\xcf\xfa\xed\xfe':
        raise ValueError('expected thin little-endian ARM64 Mach-O (fat/x86 not accepted)')
    magic, cpu, subtype, filetype, count, size, flags, reserved = struct.unpack_from('<8I', data)
    if cpu != 0x100000c or filetype not in (2, 6, 8):
        raise ValueError('not ARM64 executable/dylib/bundle')
    if 32 + size > len(data) or count > 10000:
        raise ValueError('truncated Mach-O command table')
    position, platform, minimum = 32, None, None
    dependencies, rpaths = [], []
    for _ in range(count):
        if position + 8 > 32 + size:
            raise ValueError('truncated load command')
        cmd, length = struct.unpack_from('<2I', data, position)
        if length < 8 or position + length > 32 + size:
            raise ValueError('invalid load command size')
        if cmd == 0x32:
            if length < 24:
                raise ValueError('short LC_BUILD_VERSION')
            platform, minimum = struct.unpack_from('<2I', data, position + 8)
        if cmd in (0x24, 0x25, 0x2f, 0x30):
            if length < 16:
                raise ValueError('short minimum-version command')
            platform = 2 if cmd == 0x25 else -1
            minimum = struct.unpack_from('<I', data, position + 8)[0]
        if cmd in (0xc, 0x80000018, 0x8000001f, 0x80000023, 0x8000001c):
            if length < 12:
                raise ValueError('short path command')
            start = struct.unpack_from('<I', data, position + 8)[0]
            if not 12 <= start < length:
                raise ValueError('invalid command string offset')
            value = data[position + start:position + length].split(b'\0', 1)[0].decode('utf-8')
            (rpaths if cmd == 0x8000001c else dependencies).append(value)
        position += length
    if platform != 2:
        raise ValueError(f'expected iOS device platform 2, found {platform}; simulator binaries are forbidden')
    if not minimum or minimum >> 16 < 12:
        raise ValueError('missing/unsupported deployment target')
    return {'architecture': 'arm64', 'platform': 'iOS device', 'minimum_os': minimum,
            'dependencies': dependencies, 'rpaths': rpaths}


def inspect_archive(path):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError('duplicate ZIP entries')
        if sum(i.file_size for i in z.infolist()) > 2 * 1024**3:
            raise ValueError('archive exceeds 2 GiB safety limit')
        for info in z.infolist():
            name = info.filename
            p = PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:
                raise ValueError('unsafe archive path')
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('symlinks not permitted in this static-runtime package')
        if z.testzip():
            raise ValueError('archive CRC failure')
        apps = {p.parts[1] for n in names if len((p := PurePosixPath(n)).parts) >= 2
                and p.parts[0] == 'Payload' and p.parts[1].endswith('.app')}
        if apps != {'GameName.app'}:
            raise ValueError('expected exactly Payload/GameName.app')
        prefix = 'Payload/GameName.app/'
        plist = plistlib.loads(z.read(prefix + 'Info.plist'))
        executable = plist.get('CFBundleExecutable', '')
        if not executable or '/' in executable or '\\' in executable:
            raise ValueError('invalid CFBundleExecutable')
        if not plist.get('CFBundleIdentifier') or not re.fullmatch(r'\d+\.\d+(\.\d+)?', plist.get('MinimumOSVersion', '')):
            raise ValueError('missing bundle ID or invalid minimum OS')
        if plist.get('CFBundleSupportedPlatforms') != ['iPhoneOS']:
            raise ValueError('Info.plist is not for iPhoneOS')
        for required in (executable, 'GameData/validation.map.json', 'GameData/weapons.json'):
            if prefix + required not in names:
                raise ValueError('missing required resource: ' + required)
        map_data = json.loads(z.read(prefix + 'GameData/validation.map.json'))
        if map_data.get('format') != 'bo2cs.map.v1':
            raise ValueError('validation map schema mismatch')
        binaries = {}
        for name in names:
            if name.endswith('/'):
                continue
            if 'steam' in name.lower():
                raise ValueError('forbidden Steam resource/dependency')
            with z.open(name) as stream:
                magic = stream.read(4)
            if magic in (b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca', b'\xce\xfa\xed\xfe'):
                binaries[name] = inspect_macho(z.read(name))
        if prefix + executable not in binaries:
            raise ValueError('bundle executable is not valid Mach-O')
        for name, binary in binaries.items():
            loader = str(PurePosixPath(name).parent)
            def resolve(value):
                return value.replace('@executable_path', prefix.rstrip('/')).replace('@loader_path', loader)
            for rpath in binary['rpaths']:
                if rpath.startswith('/') or '..' in PurePosixPath(resolve(rpath)).parts:
                    raise ValueError('absolute/escaping rpath: ' + rpath)
            for dependency in binary['dependencies']:
                if 'steam' in dependency.lower():
                    raise ValueError('forbidden Steam dependency')
                if dependency.startswith(('/System/Library/', '/usr/lib/')):
                    continue
                candidates = [resolve(dependency)]
                if dependency.startswith('@rpath/'):
                    candidates = [resolve(r.rstrip('/') + '/' + dependency[7:]) for r in binary['rpaths']]
                if not any(c in binaries for c in candidates):
                    raise ValueError(f'unresolved dependency in {name}: {dependency}')
        return {'status': 'PASS', 'bundle_id': plist['CFBundleIdentifier'], 'executable': executable,
                'binaries': binaries, 'resources': 'original converted validation map and weapons present',
                'runtime': 'SDL2 linked statically; no external runtime dylib expected',
                'signature': 'signature directory present' if any('_CodeSignature/' in n for n in names) else 'unsigned',
                'execution': 'structural validation only; device IPA not executed'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('ipa')
    parser.add_argument('--report-dir', default='Build/Reports')
    args = parser.parse_args()
    reports = Path(args.report_dir)
    reports.mkdir(parents=True, exist_ok=True)
    try:
        result = inspect_archive(args.ipa)
        if sys.platform == 'darwin':
            with tempfile.TemporaryDirectory() as directory:
                with zipfile.ZipFile(args.ipa) as z:
                    z.extractall(directory)
                app = Path(directory) / 'Payload/GameName.app'
                executable = app / result['executable']
                commands = [['file', str(executable)], ['xcrun', 'lipo', '-archs', str(executable)],
                            ['xcrun', 'otool', '-L', str(executable)], ['plutil', '-lint', str(app / 'Info.plist')],
                            ['codesign', '-dv', '--verbose=4', str(app)]]
                diagnostics = []
                for command in commands:
                    p = subprocess.run(command, capture_output=True, text=True, timeout=60)
                    diagnostics.append(' '.join(command[:2]) + f' (exit {p.returncode})\n' + p.stdout + p.stderr)
                    if command[0] != 'codesign' and p.returncode:
                        raise ValueError('native inspection failed: ' + command[0])
                (reports / 'ipa-native-tools.log').write_text('\n'.join(diagnostics))
        code = 0
    except Exception as exc:
        result, code = {'status': 'FAIL', 'error': str(exc)}, 1
    (reports / 'ipa.json').write_text(json.dumps(result, indent=2))
    (reports / 'IPA_VALIDATION_REPORT.md').write_text('# IPA validation\n\n' + result['status'] + '\n\n```json\n' + json.dumps(result, indent=2) + '\n```\n')
    print(json.dumps(result, indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
