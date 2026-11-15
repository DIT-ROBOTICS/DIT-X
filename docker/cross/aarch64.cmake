# Cross compile for arm64 on an amd64 machine: compilers from g++-aarch64-linux-gnu,
# headers and libraries from the arm64 sysroot next to this file (make-sysroot.sh).
# The eurobot-cross image sets CMAKE_TOOLCHAIN_FILE to this file, so a plain
# `colcon build` there (what `ditx build --arch arm64` runs) produces arm64 code.
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)
set(CMAKE_C_COMPILER aarch64-linux-gnu-gcc)
set(CMAKE_CXX_COMPILER aarch64-linux-gnu-g++)

set(_sysroot "${CMAKE_CURRENT_LIST_DIR}/sysroot")
set(CMAKE_SYSROOT "${_sysroot}")
set(CMAKE_FIND_ROOT_PATH "${_sysroot}")
# tools (python, rosidl generators) run on this machine; libraries and headers come
# from the sysroot; CMake packages from the sysroot first, then from the workspace
# (its arm64 installs under build/ live outside the sysroot)
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH)

# python extensions (rosidl_generator_py) need the target's file name tag
file(GLOB _py RELATIVE "${_sysroot}/usr/include" "${_sysroot}/usr/include/python3.*")
string(REPLACE "python3." "" _minor "${_py}")
set(PYTHON_SOABI "cpython-3${_minor}-aarch64-linux-gnu")

# let the linker find indirect dependencies (librcl, libddsc, ...) in every prefix
string(REPLACE ":" ";" _prefixes "$ENV{AMENT_PREFIX_PATH}:$ENV{CMAKE_PREFIX_PATH}")
set(_link "")
foreach(_p IN LISTS _prefixes)
  if(_p STREQUAL "")
    continue()
  endif()
  if(IS_DIRECTORY "${_sysroot}${_p}/lib")
    set(_p "${_sysroot}${_p}")
  endif()
  foreach(_d "${_p}/lib" "${_p}/lib/aarch64-linux-gnu")
    if(IS_DIRECTORY "${_d}")
      string(APPEND _link " -Wl,-rpath-link,${_d}")
    endif()
  endforeach()
endforeach()
set(CMAKE_EXE_LINKER_FLAGS_INIT "${_link}")
set(CMAKE_SHARED_LINKER_FLAGS_INIT "${_link}")
set(CMAKE_MODULE_LINKER_FLAGS_INIT "${_link}")
