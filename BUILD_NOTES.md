# Build notes

BO2CS was cloned at 4a24992, with only README.md on main. Work is on codex/ios-pipeline. The user authorized GitHub Actions macOS runners and package inspection if simulator boot is environmentally unavailable.

CMake generates Xcode targets from pinned SDL2 and JSON sources. No Swift packages are declared; Xcode dependency resolution is still executed. Shared Bash/Python scripts perform simulator/device builds, runtime testing, packaging and validation. CI jobs exchange ZIP bundles and receipts and upload reports on failures. Explicit discovered simulator UUIDs avoid ambiguity from unrelated booted devices.

The original native prototype implements grid collision, hitscan, armor, reload, team bots, bomb timers and rounds, procedural visuals, multitouch safe areas, controller input and log export. Asset discovery preserves unknown data and supports standard PNG/PCM WAV and original grid scene conversion through a separate intermediate stage.

Limitations: no network multiplayer, BSP importer, arbitrary triangle mesh renderer, skeletal models, PS3 proprietary decoders, texture streaming, weapon pickup or full weapon selection. SWAP currently logs the single-carbine limitation. Jump is a camera offset without vertical traversal. Bots are basic. The procedural renderer reports zero textures/meshes honestly. Physical iPhone performance, touch ergonomics, thermals, signing and controller behavior remain untested.

Local verification: seven Python tests passed; original fixture conversion and Python syntax compilation passed. A local bash syntax check could not execute because Bash was absent at the probed path; CI performs bash -n. Native results must come from Actions.

Authoritative generated reports: Build/Reports, uploaded as BO2CS-Validation-Reports. Download GameName-unsigned-IPA and SimulatorBuild for binaries. Root reports are initial status records, not evidence of CI success. No PS3 assets were supplied or uploaded.
