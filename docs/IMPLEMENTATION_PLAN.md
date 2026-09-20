# Native iOS CI implementation plan

The user's project brief and GitHub Actions follow-up are the specification. Execute inline on codex/ios-pipeline; explicit instructions authorize implementation and CI execution without design approval pauses.

## Architecture

Use pinned SDL2 (zlib license) as the native open-source runtime and original C++ gameplay, with a small original grid/raycast scene for initial verification. SDL supplies Metal presentation, audio, touch and controller interfaces. Keep gameplay independent of SDL so CTest can exercise it on desktop runners. This replaces the unintegrated Xash proposal, not existing game code. General BSP/mesh/animation rendering is not claimed by the initial scene.

Python owns deterministic conversion, simulator discovery, process timeouts, IPA inspection and reporting. Bash entrypoints delegate to Python and work on local Macs. CMake generates the Xcode project and resolves pinned source dependencies. There are no Swift packages. CI jobs exchange zipped app bundles and JSON receipts; runtime unavailable differs from runtime failure and from success.

## Execution ledger

- [ ] Test simulator selection, archive validation and read-only conversion against malformed inputs.
- [ ] Implement source-to-intermediate-to-runtime conversion with original CI fixtures; preserve unsupported bytes locally.
- [ ] Implement original map loading, movement/collision, weapons, bots and round/objective core; run CTest on CI.
- [ ] Implement SDL iOS presentation, touch controls, structured logs and 60-second automated play.
- [ ] Implement shared Xcode selection, simulator/device builds, simulator execution, packaging and validation.
- [ ] Add separate source, unit/converter, simulator build/runtime, device, packaging and validation jobs. Use original fixtures only.
- [ ] Run local Python checks and shell syntax checks, publish the feature branch to execute Actions, inspect failures, fix and rerun.

## Failure cases to verify

Unavailable simulators must preserve compile/package jobs without inventing runtime PASS. An app failure after successful boot must fail the runtime job. A simulator ARM64 binary must fail IPA validation. Unknown assets and truncated binary data must preserve inputs and report diagnostics. Output paths inside source directories and archive traversal must be rejected. A failed command must leave logs and never update a success receipt. Incomplete original-game features remain explicit limitations.

## External input

No local PS3 game path or game identification has been supplied. CI cannot establish proprietary format support. Actual conversion of a PS3 map remains blocked on those inputs; synthetic data is never reported as a converted PS3 map.
