cmake_minimum_required(VERSION 3.21)
project(OpmShowcase LANGUAGES CXX)
# A documentation-only driver: the UI, models and resources are production files.
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(BUILD_TESTING OFF CACHE BOOL "" FORCE)
set(OPM_BUILD_EDITOR ON CACHE BOOL "" FORCE)
get_filename_component(OPM_ROOT ../.. ABSOLUTE)
add_subdirectory(${OPM_ROOT} opm)
find_package(Qt6 REQUIRED COMPONENTS Gui Qml Quick QuickControls2 Test)
find_package(KF6Service REQUIRED)
find_package(KF6Config REQUIRED)
add_executable(opm-showcase-editor editor.cpp
    ${OPM_ROOT}/native/editor_catalog.cpp ${OPM_ROOT}/native/editor_catalog.hpp
    ${OPM_ROOT}/native/editor.qrc)
target_link_libraries(opm-showcase-editor PRIVATE opm_native Qt6::Gui Qt6::Qml
    Qt6::Quick Qt6::QuickControls2 Qt6::Test KF6::Service KF6::ConfigCore)
