#!/bin/bash
# Build the arm64 sysroot used to cross compile on an amd64 machine:
#   make-sysroot.sh SYSROOT SRC_DIR...
# mmdebstrap downloads the arm64 packages of ROS and of every build dependency
# declared in SRC_DIR/**/package.xml and only unpacks them, so no arm64 binary
# ever runs (no qemu, on a laptop or in CI).
set -euo pipefail

sysroot="$1"
shift
# shellcheck disable=SC1091
. /etc/os-release
gcc_major="$(gcc -dumpversion | cut -d. -f1)"

# installed ROS packages count as "source" for --ignore-src once ROS is sourced
keys="$(env -u AMENT_PREFIX_PATH -u ROS_PACKAGE_PATH rosdep keys --from-paths "$@" --ignore-src | sort -u)"
# shellcheck disable=SC2086
deps="$(rosdep resolve $keys | grep -v '^#' | tr ' ' '\n' | grep . | sort -u | paste -sd, -)"

ports=http://ports.ubuntu.com/ubuntu-ports
mmdebstrap --variant=extract --architectures=arm64 --mode=root --format=directory \
  --include="ros-$ROS_DISTRO-ros-base,ros-$ROS_DISTRO-rmw-cyclonedds-cpp,libc6-dev,libstdc++-$gcc_major-dev,libpython3-dev,python3-numpy${deps:+,$deps}" \
  "$VERSION_CODENAME" "$sysroot" \
  "deb $ports $VERSION_CODENAME main universe" \
  "deb $ports $VERSION_CODENAME-updates main universe" \
  "deb [signed-by=/usr/share/keyrings/ros2-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $VERSION_CODENAME main"

# packages ship absolute symlinks (libz.so -> /lib/...): point them inside the sysroot
find "$sysroot" -type l -lname '/*' -print0 | while IFS= read -r -d '' link; do
  ln -sfnr "$sysroot$(readlink "$link")" "$link"
done
# exported CMake configs name system libraries by absolute path (libpython, eigen)
grep -rlE '/usr/(lib|include)/' "$sysroot/opt/ros" --include='*.cmake' |
  xargs -r sed -i -E "s#([\";( ]|^)/usr/(lib|include)/#\1$sysroot/usr/\2/#g"
du -sh "$sysroot"
