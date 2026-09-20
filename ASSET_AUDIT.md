# Local BO2 asset audit

The user identified a Desktop dump. Read-only inventory found 431 files, approximately 16.8 GB. The configurable source path is local only; it is not embedded in project code or CI.

Detected by file headers: 144 signed T6 fastfiles, 82 IPak texture containers, 80 T6 sound banks, three PNG files (including one with a different extension), one PSF metadata file and 121 otherwise unsupported files. IPak section metadata parsed with explicit big-endian bounds checks; no payload textures were decoded.

The scanner completed without errors. Three PNG files passed through the intermediate and output directories with source/output SHA-256 equality. No geometry, models, weapon metadata, rigs, animations or audio were extracted. All 428 other files were left at their original source paths and diagnosed in the local manifest. Inventory and generated content are ignored by Git and excluded from CI.

The signed fastfiles are recognized by their TAff0100 headers. The signed/encrypted T6 loading family in [OpenAssetTools](https://github.com/Laupetin/OpenAssetTools/blob/main/src/ZoneLoading/Game/T6/ZoneLoaderFactoryT6.cpp) is not used to bypass encryption or authentication. The exact signed PS3 layout is not supported by this project's parser. An existing unencrypted geometry/entity export is needed to proceed with the real-map milestone while honoring the user's no-decryption boundary.

The pre-existing Desktop converter was inspected as text only. It declares in-place mutation/deletion, so it was not executed. The original dump remains untouched.

Reproduce local discovery:

```sh
python3 Tools/PS3AssetConverter/convert_assets.py --source /path/to/PS3_GAME --output LocalGameData/Inventory --intermediate LocalGameData/Intermediate --scan-only
```

Use `--standard-only` instead of `--scan-only` to normalize only supported standard formats without duplicating the multi-gigabyte unsupported containers. The default conversion mode also copies unsupported bytes into the intermediate directory; allow enough disk space before using it.
