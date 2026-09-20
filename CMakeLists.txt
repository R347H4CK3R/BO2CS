cmake_minimum_required(VERSION 3.24)
project(BO2CS LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
option(BO2CS_IOS "Build native iOS application" OFF)
include(FetchContent)
FetchContent_Declare(json GIT_REPOSITORY https://github.com/nlohmann/json.git GIT_TAG 65ee68451d8eb2b5f3a30b410476ab83deb3289b)
set(JSON_BuildTests OFF CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(json)
add_library(GameCore Source/Game.cpp)
target_include_directories(GameCore PUBLIC Source)
target_link_libraries(GameCore PUBLIC nlohmann_json::nlohmann_json)

find_package(Python3 REQUIRED COMPONENTS Interpreter)
execute_process(COMMAND "${Python3_EXECUTABLE}" "${CMAKE_SOURCE_DIR}/Tools/PS3AssetConverter/convert_assets.py"
    --source "${CMAKE_SOURCE_DIR}/Tests/Fixtures" --intermediate "${CMAKE_BINARY_DIR}/Intermediate"
    --output "${CMAKE_BINARY_DIR}/GameData" COMMAND_ERROR_IS_FATAL ANY)
configure_file(GameData/weapons.json GameData/weapons.json COPYONLY)

if(BO2CS_IOS)
    enable_language(OBJC)
    enable_language(OBJCXX)
    set(SDL_SHARED OFF CACHE BOOL "" FORCE)
    set(SDL_STATIC ON CACHE BOOL "" FORCE)
    set(SDL_TEST OFF CACHE BOOL "" FORCE)
    set(SDL_TESTS OFF CACHE BOOL "" FORCE)
    FetchContent_Declare(SDL2 GIT_REPOSITORY https://github.com/libsdl-org/SDL.git GIT_TAG 5d249570393f7a37e037abf22cd6012a4cc56a71)
    FetchContent_MakeAvailable(SDL2)
    configure_file("${sdl2_SOURCE_DIR}/LICENSE.txt" "${CMAKE_BINARY_DIR}/SDL2-LICENSE.txt" COPYONLY)
    configure_file("${json_SOURCE_DIR}/LICENSE.MIT" "${CMAKE_BINARY_DIR}/JSON-LICENSE.txt" COPYONLY)
    add_executable(GameName MACOSX_BUNDLE Source/Main.cpp Source/Platform.mm)
    target_link_libraries(GameName PRIVATE GameCore SDL2::SDL2main SDL2::SDL2-static "-framework UIKit")
    set_target_properties(GameName PROPERTIES
        MACOSX_BUNDLE_INFO_PLIST "${CMAKE_SOURCE_DIR}/iOS/Info.plist.in"
        XCODE_GENERATE_SCHEME TRUE
        XCODE_ATTRIBUTE_PRODUCT_BUNDLE_IDENTIFIER "io.github.r347h4ck3r.bo2cs"
        XCODE_ATTRIBUTE_TARGETED_DEVICE_FAMILY "1,2"
        XCODE_ATTRIBUTE_CODE_SIGNING_ALLOWED "NO"
        XCODE_ATTRIBUTE_IPHONEOS_DEPLOYMENT_TARGET "16.0"
        XCODE_ATTRIBUTE_ENABLE_BITCODE "NO")
    foreach(resource validation.map.json weapons.json)
        set(file "${CMAKE_BINARY_DIR}/GameData/${resource}")
        target_sources(GameName PRIVATE "${file}")
        set_source_files_properties("${file}" PROPERTIES MACOSX_PACKAGE_LOCATION "Resources/GameData")
    endforeach()
    foreach(notice SDL2-LICENSE.txt JSON-LICENSE.txt)
        target_sources(GameName PRIVATE "${CMAKE_BINARY_DIR}/${notice}")
        set_source_files_properties("${CMAKE_BINARY_DIR}/${notice}" PROPERTIES MACOSX_PACKAGE_LOCATION "Resources")
    endforeach()
else()
    include(CTest)
    if(BUILD_TESTING)
        add_executable(core_tests Tests/core_tests.cpp)
        target_link_libraries(core_tests PRIVATE GameCore)
        add_test(NAME gameplay COMMAND core_tests "${CMAKE_BINARY_DIR}/GameData/validation.map.json" "${CMAKE_BINARY_DIR}/GameData/weapons.json")
    endif()
endif()
