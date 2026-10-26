cmake_minimum_required(VERSION 3.20)
project(ScreenshooterContextMenu LANGUAGES CXX)

if(NOT WIN32)
    message(FATAL_ERROR "The Windows 11 Explorer context-menu extension is Windows-only.")
endif()

add_library(ScreenshooterContextMenu SHARED ContextMenuCommand.cpp)
target_compile_features(ScreenshooterContextMenu PRIVATE cxx_std_17)
target_compile_definitions(ScreenshooterContextMenu PRIVATE UNICODE _UNICODE)
target_link_libraries(ScreenshooterContextMenu PRIVATE shlwapi shell32 ole32)
set_target_properties(ScreenshooterContextMenu PROPERTIES
    OUTPUT_NAME "ScreenshooterContextMenu"
    PREFIX ""
)
