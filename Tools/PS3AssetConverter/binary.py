"""Bounds-checked reading for unencrypted binary formats."""
import struct


class Reader:
    def __init__(self, data, endian='big'):
        if endian not in ('big', 'little'):
            raise ValueError('endianness must be explicit')
        self.data = memoryview(data)
        self.offset = 0
        self.prefix = '>' if endian == 'big' else '<'

    def take(self, size):
        if size < 0 or self.offset + size > len(self.data):
            raise ValueError(f'truncated data at offset {self.offset}; requested {size}')
        out = self.data[self.offset:self.offset + size]
        self.offset += size
        return out

    def u32(self):
        return struct.unpack(self.prefix + 'I', self.take(4))[0]

    def f32(self):
        return struct.unpack(self.prefix + 'f', self.take(4))[0]
