#!/usr/bin/env bash
# ==============================================================================
# Nyxuri CLI launcher — the permanent entry point. `~/.local/bin/nyxuri` and
# `/usr/bin/nyxuri` (system package) symlink here; KM5 demoted install.sh to a
# one-time bootstrap. Hardening: -I ignores PYTHON* env injection, -S skips
# sitecustomize. XDG normalization parity with the pre-KM5 entry behavior.
# ==============================================================================
set -euo pipefail

# Normalize XDG variables so sandboxes (e.g. HOME=$(mktemp -d)) don't leak
# into the host: an XDG var pointing outside the current HOME is reset.
if [ -n "${XDG_STATE_HOME:-}" ] && [[ "$XDG_STATE_HOME" != "$HOME/"* ]]; then
    export XDG_STATE_HOME="$HOME/.local/state"
fi
if [ -n "${XDG_CONFIG_HOME:-}" ] && [[ "$XDG_CONFIG_HOME" != "$HOME/"* ]]; then
    export XDG_CONFIG_HOME="$HOME/.config"
fi
if [ -n "${XDG_CACHE_HOME:-}" ] && [[ "$XDG_CACHE_HOME" != "$HOME/"* ]]; then
    export XDG_CACHE_HOME="$HOME/.cache"
fi

# Repo root = parent of this file's directory (launcher lives at <repo>/nyxuri/).
self="${BASH_SOURCE[0]}"
resolved="$(readlink -f "$self" 2>/dev/null || echo "$self")"
repo_dir="$(cd -- "$(dirname -- "$resolved")/.." && pwd)"

exec python3 -I -S -c '
import sys
if sys.version_info < (3, 11):
    sys.stderr.write(
        "[✗] 需要 Python 3.11+（当前 %d.%d），请升级后重试。\n"
        "[✗] Python 3.11+ is required (found %d.%d). Please upgrade python3.\n"
        % (sys.version_info[0], sys.version_info[1], sys.version_info[0], sys.version_info[1])
    )
    sys.exit(1)
target = sys.argv.pop(1)
sys.path.insert(0, target)
sys.argv[0] = "nyxuri"
from pathlib import Path
if (Path(target) / "personal/entry.py").is_file():
    from personal.entry import main
else:
    from nyxuri.cli import main
main()
' "$repo_dir" "$@"
