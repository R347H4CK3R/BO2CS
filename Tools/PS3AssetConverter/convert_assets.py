#!/usr/bin/env python3
"""Read-only discovery and two-stage conversion. No DRM/container guessing."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import wave


def identify(header, name):
    signatures = [(b'\x89PNG\r\n\x1a\n', 'PNG', 'texture', 'deflate', 'big'),
                  (b'DDS ', 'DDS', 'texture', 'format-dependent', 'little'),
                  (b'OggS', 'OGG', 'audio', 'codec-dependent', 'little'),
                  (b'IBSP', 'IBSP', 'map', 'unknown', 'unknown'),
                  (b'VBSP', 'VBSP', 'map', 'unknown', 'unknown'),
                  (b'PK\x03\x04', 'ZIP', 'container', 'per-entry', 'little'),
                  (b'\x1f\x8b', 'GZIP', 'container', 'gzip', 'little'),
                  (b'\x00PSF', 'PSF', 'metadata', 'none', 'little'),
                  (b'\x7fELF', 'ELF', 'executable', 'none', 'header-defined')]
    if header.startswith(b'RIFF') and header[8:12] == b'WAVE':
        return 'WAV', 'audio', 'format-dependent', 'little'
    if name.endswith('.scene.json'):
        return 'BO2CS_SCENE', 'map', 'none', 'text'
    for magic, *info in signatures:
        if header.startswith(magic):
            return tuple(info)
    suffix = Path(name).suffix.lower()
    classes = {'.gtf': 'texture', '.gxt': 'texture', '.dds': 'texture', '.bsp': 'map',
               '.mdl': 'mesh', '.obj': 'mesh', '.glb': 'mesh', '.gltf': 'mesh',
               '.anim': 'animation', '.wav': 'audio', '.ogg': 'audio', '.mp3': 'audio',
               '.vag': 'audio', '.nav': 'navigation', '.cfg': 'script', '.lua': 'script',
               '.ff': 'container', '.pak': 'container', '.iwi': 'texture'}
    return 'unknown', classes.get(suffix, 'unknown'), 'unknown', 'unknown'


def normalize_scene(data):
    if data.get('format') != 'bo2cs.scene.v1':
        raise ValueError('unsupported scene schema')
    rows = data['rows']
    if not 4 <= len(rows) <= 128 or not 4 <= len(rows[0]) <= 128:
        raise ValueError('map dimensions out of bounds')
    width = len(rows[0])
    if any(len(row) != width or set(row) - set('#.') for row in rows):
        raise ValueError('map must be rectangular with # walls and . floors')
    if any(c != '#' for c in rows[0] + rows[-1]) or any(r[0] != '#' or r[-1] != '#' for r in rows):
        raise ValueError('map boundary must be closed')
    scale = float(data.get('meters_per_cell', 1))
    if not math.isfinite(scale) or not 0.1 <= scale <= 10:
        raise ValueError('invalid scale')
    def point(p):
        x, y = map(float, p)
        if not all(math.isfinite(v) for v in (x, y)) or not (0 <= x < width and 0 <= y < len(rows)):
            raise ValueError('nonfinite/out-of-bounds point')
        if rows[int(y)][int(x)] != '.':
            raise ValueError('point is in collision')
        return [x, y]
    spawns = data['spawns']
    if not all(len(spawns.get(team, [])) >= 3 for team in ('attack', 'defense')):
        raise ValueError('need at least three original spawn locations per team')
    return {'format': 'bo2cs.map.v1', 'rows': rows, 'meters_per_cell': scale,
            'coordinates': 'X east, Y south, Z up; cell coordinates; right-handed conversion is explicit',
            'spawns': {team: [point(p) for p in spawns[team]] for team in ('attack', 'defense')},
            'plant_zone': point(data['plant_zone']), 'source_kind': 'original_fixture',
            'collision': 'solid cells', 'navigation': 'four-neighbor walkable grid'}


def convert(source, output, intermediate):
    source, output, intermediate = (Path(p).resolve() for p in (source, output, intermediate))
    if not source.is_dir():
        raise ValueError('source directory does not exist')
    for a, b in ((source, output), (source, intermediate), (output, intermediate)):
        if a == b or a in b.parents or b in a.parents:
            raise ValueError('source, intermediate and output must be disjoint')
    output.mkdir(parents=True, exist_ok=True)
    intermediate.mkdir(parents=True, exist_ok=True)
    assets = []
    for path in sorted(source.rglob('*')):
        if path.is_dir() and not path.is_symlink():
            continue
        rel = path.relative_to(source)
        record = dict(original_path=rel.as_posix(), file_size=None, detected_format='unknown',
                      probable_asset_class='unknown', compression='unknown', endianness='unknown',
                      conversion_status='unsupported', converter_used=None, generated_output_path=None,
                      intermediate_path=None, warnings=[], errors=[])
        assets.append(record)
        try:
            if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != source.parent):
                raise ValueError('symlink not followed')
            record['file_size'] = path.stat().st_size
            with path.open('rb') as f:
                header = f.read(64)
            info = identify(header, path.name)
            for k, v in zip(('detected_format', 'probable_asset_class', 'compression', 'endianness'), info):
                record[k] = v
            supported = info[0] in ('PNG', 'WAV', 'BO2CS_SCENE') and record['file_size'] <= 32 * 1024**2
            target = intermediate / ('normalized' if supported else 'unsupported') / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            # Copy first, so malformed supported files are still preserved.
            shutil.copyfile(path, target)
            record['intermediate_path'] = target.relative_to(intermediate).as_posix()
            if not supported:
                record['warnings'].append('Preserved unchanged; no verified decoder for this format. No decryption attempted.')
                continue
            if info[0] == 'BO2CS_SCENE':
                data = normalize_scene(json.loads(target.read_text(encoding='utf-8')))
                target.write_text(json.dumps(data, indent=2), encoding='utf-8')
                native = output / (rel.name.replace('.scene.json', '.map.json'))
                record['converter_used'] = 'original-grid-scene-v1'
            else:
                if info[0] == 'WAV':
                    with wave.open(str(target), 'rb') as w:
                        if w.getcomptype() != 'NONE':
                            raise ValueError('only PCM WAV supported')
                native = output / rel
                record['converter_used'] = 'standard-format-copy-v1'
            native.parent.mkdir(parents=True, exist_ok=True)
            # Engine conversion is deliberately separate and reads intermediate, never source.
            shutil.copyfile(target, native)
            record['generated_output_path'] = native.relative_to(output).as_posix()
            record['conversion_status'] = 'converted'
        except (OSError, ValueError, KeyError, TypeError, IndexError, wave.Error) as exc:
            record['conversion_status'] = 'error'
            record['errors'].append(str(exc))
    manifest = {'schema': 1, 'assets': assets, 'source_modified': False,
                'ps3_proprietary_decoders': [], 'note': 'Detection is not proof of conversion support.'}
    (output / 'asset_inventory.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--intermediate', default='GameDataIntermediate')
    args = parser.parse_args()
    result = convert(args.source, args.output, args.intermediate)
    print(json.dumps({'assets': len(result['assets']), 'errors': sum(bool(a['errors']) for a in result['assets'])}))
    raise SystemExit(1 if any(a['errors'] for a in result['assets']) else 0)
