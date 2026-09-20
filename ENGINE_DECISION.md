# Engine decision

Use SDL2 2.32.10 pinned to 5d249570393f7a37e037abf22cd6012a4cc56a71 as the native open-source runtime, with original C++ gameplay. SDL provides Metal presentation, iOS integration, audio, multitouch and controllers. The initial renderer is a grid raycaster, not a full BSP/skeletal renderer. This is a limited validation prototype.

Xash3D was audited at 4857b389e6ba32ddaa68582aedcbc950c138f46a. Its scripts/gha/deps_ios.sh and build_ios.sh build hlsdk-portable, and its packaging produces a game-data launcher. Standalone game modules would require additional work. None of that code or content was copied. SDL2 materially simplifies original scene and CMake/Xcode targets without Valve dependencies. ioquake3 would also require a tactical game module and iOS integration.

SDL documentation: https://wiki.libsdl.org/SDL2/README-cmake
ARM64 macos-15 runner documentation: https://docs.github.com/en/actions/reference/runners/github-hosted-runners

SDL2 is zlib-licensed. nlohmann/json 3.12.0, pinned to 65ee68451d8eb2b5f3a30b410476ab83deb3289b, is MIT-licensed. Their license texts are bundled with the app. Project code and original fixtures use MIT. No CS16Client, Valve SDK, PS3 assets or commercial folders are required.

Real PS3 map/mesh/container/animation decoding remains blocked on game identification and unencrypted samples. Original fixtures are never represented as converted PS3 maps.
