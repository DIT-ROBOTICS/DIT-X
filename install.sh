#!/bin/bash
# First step after cloning: put `ditx` on your PATH and enable Tab completion.
#   ./install.sh              install      ./install.sh --dry-run    show what would change
#   ./install.sh --uninstall  undo it      (same as tools/install.sh, which does the work)
set -euo pipefail
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/tools/install.sh" "$@"
