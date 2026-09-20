# BO2CS

Standalone original tactical FPS prototype and native iOS CI pipeline. SDL2 provides the open-source runtime and Metal presentation. No Steam, Valve game data or proprietary assets are needed for CI.

This is not yet the complete PS3-content project: the original validation map is a grid raycaster scene. See BUILD_NOTES.md for explicit renderer/gameplay/converter limitations.

On macOS with Xcode 16+, CMake 3.24+, Python 3 and Git:

```sh
bash Scripts/build_ios.sh simulator
bash Scripts/build_ios.sh test
bash Scripts/build_ios.sh device
bash Scripts/build_ios.sh ipa
```

`test` runs Python tests, desktop C++ tests, simulator compilation and 60-second real simulator gameplay. `ipa` builds/packages/validates a device binary; it does not establish gameplay validation by itself. Build outputs are under Build/. Simulator and device bundles are separate.

GitHub Actions uses the same commands. Open the **iOS Build** run and download **GameName-unsigned-IPA**, **SimulatorBuild**, and **BO2CS-Validation-Reports**. Actions wraps artifacts in ZIP files. The IPA inside is unsigned and requires a suitable user signing/installation route. Never infer playability from compilation or IPA structural validation alone.

```sh
python3 Tools/PS3AssetConverter/convert_assets.py --source /path/to/PS3_GAME --intermediate ./GameDataIntermediate --output ./GeneratedGameData
```

The scanner preserves unsupported files and records relative paths and diagnostics. It supports standard PNG/PCM WAV copies and the original grid fixture schema; no proprietary PS3 format decoder is verified. Keep PS3 inputs and generated proprietary outputs out of Git and CI.

Touch to start; left area moves, right area looks. FIRE/RELOAD/JUMP/CROUCH/USE/SCORE/PAUSE controls are displayed. Pause allows sensitivity, opacity, alternate button layout and log export. AUTOTEST=1 drives the player and bots for a timed match and writes Documents/Logs/AUTOTEST_RESULT.json.
