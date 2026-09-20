import importlib.util
import json
import pathlib
import struct
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SimulatorTests(unittest.TestCase):
    def test_prefers_exact_phone_even_over_newer_pro_max(self):
        m = module('ios', 'Scripts/ios.py')
        data = {'devices': {'com.apple.CoreSimulator.SimRuntime.iOS-26-0': [
            {'name': 'iPhone 17 Pro Max', 'udid': 'new', 'isAvailable': True}],
            'com.apple.CoreSimulator.SimRuntime.iOS-18-5': [
            {'name': 'iPhone 16 Plus', 'udid': 'exact', 'isAvailable': True}]}}
        self.assertEqual(m.select_simulator(data)['udid'], 'exact')

    def test_ignores_unavailable_and_ipads(self):
        m = module('ios', 'Scripts/ios.py')
        data = {'devices': {'iOS-26-0': [
            {'name': 'iPhone 16 Plus', 'udid': 'bad', 'isAvailable': False},
            {'name': 'iPad Pro', 'udid': 'ipad', 'isAvailable': True},
            {'name': 'iPhone 17 Pro Max', 'udid': 'good', 'isAvailable': True}]}}
        self.assertEqual(m.select_simulator(data)['udid'], 'good')
        self.assertIsNone(m.select_simulator({'devices': {}}))


class ConverterTests(unittest.TestCase):
    def test_unknown_bytes_preserved_and_source_unchanged(self):
        m = module('convert', 'Tools/PS3AssetConverter/convert_assets.py')
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d)
            (p / 'source').mkdir()
            raw = b'unknown\x00\xffpayload'
            (p / 'source/opaque.bin').write_bytes(raw)
            m.convert(p / 'source', p / 'out', p / 'intermediate')
            inventory = json.loads((p / 'out/asset_inventory.json').read_text())
            self.assertEqual(inventory['assets'][0]['conversion_status'], 'unsupported')
            self.assertEqual((p / 'source/opaque.bin').read_bytes(), raw)
            self.assertEqual((p / 'intermediate/unsupported/opaque.bin').read_bytes(), raw)

    def test_rejects_output_nested_in_source(self):
        m = module('convert', 'Tools/PS3AssetConverter/convert_assets.py')
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d)
            with self.assertRaises(ValueError):
                m.convert(p, p / 'out', p / 'intermediate')

    def test_truncated_endian_reader(self):
        m = module('binary', 'Tools/PS3AssetConverter/binary.py')
        self.assertEqual(m.Reader(b'\x01\x02\x03\x04', 'big').u32(), 16909060)
        with self.assertRaises(ValueError):
            m.Reader(b'\x01', 'big').u32()


class IPATests(unittest.TestCase):
    def test_rejects_archive_traversal(self):
        m = module('ipa', 'Tools/validate_ipa.py')
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / 'bad.ipa'
            with zipfile.ZipFile(p, 'w') as z:
                z.writestr('../outside', 'bad')
            with self.assertRaises(ValueError):
                m.inspect_archive(p)

    def test_arm64_simulator_is_not_device(self):
        m = module('ipa', 'Tools/validate_ipa.py')
        # Little-endian 64-bit Mach-O header plus LC_BUILD_VERSION.
        header = struct.pack('<8I', 0xfeedfacf, 0x100000c, 0, 2, 1, 24, 0, 0)
        simulator = header + struct.pack('<6I', 0x32, 24, 7, 0x100000, 0x120000, 0)
        device = header + struct.pack('<6I', 0x32, 24, 2, 0x100000, 0x120000, 0)
        with self.assertRaises(ValueError):
            m.inspect_macho(simulator)
        self.assertEqual(m.inspect_macho(device)['architecture'], 'arm64')


if __name__ == '__main__':
    unittest.main()
