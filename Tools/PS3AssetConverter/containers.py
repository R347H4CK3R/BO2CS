"""Metadata-only parsing of documented, unencrypted IPak container headers.

Reference: https://openassettools.dev/reference/ipak-file-format.html
No authentication, signature, or encryption processing is implemented.
"""
from pathlib import Path
import struct


def ipak_metadata(path):
    path = Path(path)
    size = path.stat().st_size
    with path.open('rb') as stream:
        header = stream.read(16)
        if len(header) != 16 or header[:4] not in (b'IPAK', b'KAPI'):
            raise ValueError('invalid/truncated IPak header')
        endian = '>' if header[:4] == b'IPAK' else '<'
        magic, version, declared_size, count = struct.unpack(endian+'4I', header)
        if version != 0x50000 or count > 64 or 16 + count * 16 > size:
            raise ValueError('unsupported version or invalid IPak section count')
        sections = []
        for _ in range(count):
            raw = stream.read(16)
            kind, offset, length, items = struct.unpack(endian+'4I', raw)
            if offset < 16 + count * 16 or offset + length > size:
                raise ValueError('IPak section outside file bounds')
            if kind == 1 and items * 16 > length:
                raise ValueError('IPak index exceeds section')
            sections.append({'type': kind, 'offset': offset, 'size': length, 'item_count': items,
                             'role': {1:'image_index',2:'image_data'}.get(kind,'unknown_preserved')})
    return {'endianness': 'big' if endian == '>' else 'little', 'version': version,
            'declared_size': declared_size, 'actual_size': size, 'sections': sections,
            'warnings': [] if declared_size == size else ['Header file size differs from actual size'],
            'payload_decoded': False}
