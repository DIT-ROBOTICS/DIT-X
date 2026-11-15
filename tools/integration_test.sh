#!/bin/bash
# System test, run inside the dev container by `ditx test --integration` (and CI):
# start every domain's bringup together, exactly like the robot does, then check
#   1. the startup handshake completes (every domain reports ready to main)
#   2. the live ROS graph matches contract.yaml (names, types, a publisher each)
# usage: integration_test.sh OUT_DIR DOMAIN[,DOMAIN...] INSTALL_DIR...
set -o pipefail   # no -u: ROS setup.bash files read unset variables
out="$1"; domains="$2"; shift 2
mkdir -p "$out"
for install in "$@"; do
  # shellcheck disable=SC1091
  source "$install/setup.bash"
done

# private DDS domain on loopback, so parallel runs / other robots never mix in
export ROS_DOMAIN_ID=$((RANDOM % 100 + 100))
if [[ "$ROS_DISTRO" == humble ]]; then export ROS_LOCALHOST_ONLY=1
else export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST; fi

pids=()
# shellcheck disable=SC2317  # invoked by the EXIT trap
cleanup() {
  kill -INT "${pids[@]}" 2>/dev/null
  sleep 2
  kill -9 "${pids[@]}" 2>/dev/null
  wait 2>/dev/null
}
trap cleanup EXIT

IFS=, read -ra list <<< "$domains"
for d in "${list[@]}"; do
  ros2 launch "${d}_bringup" bringup.launch.py robot:=sim > "$out/$d.log" 2>&1 &
  pids+=($!)
  echo "▸ started $d (log: $out/$d.log)"
done

rc=0
python3 "$(dirname "$0")/integration_check.py" --domains "$domains" --timeout 45 || rc=1
ros2 run eurobot_common contract_check --wait 3 --require all || rc=1
if (( rc )); then
  for d in "${list[@]}"; do echo "──── tail $d.log"; tail -n 20 "$out/$d.log"; done
fi
exit $rc
