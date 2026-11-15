#!/bin/bash
# Fingerprint of the shared interfaces: hash of every .msg/.srv/.action file and
# contract.yaml under DIR. Used by the image build and by `ditx build --base`;
# overlays carry it so a robot can refuse one built against other interfaces.
set -euo pipefail
cd "${1:?usage: fingerprint.sh DIR}"
find . -type f \( -name '*.msg' -o -name '*.srv' -o -name '*.action' -o -name contract.yaml \) \
  -not -path '*/build/*' -printf '%P\n' | LC_ALL=C sort | xargs -r sha256sum | sha256sum | cut -c1-16
