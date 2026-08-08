#!/usr/bin/env bash
#
# Run the sync load suite with credentials read from tests/load/.env, so they
# do not have to be typed (or land in shell history) on every run.
#
#   ./tests/load/run.sh                      # full suite
#   ./tests/load/run.sh --vus 5 --duration 30s   # extra flags pass through to k6
#
# k6 has no --env-file, but it inherits the process environment by default
# (--include-system-env-vars), so exporting the values here is enough.
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
env_file="$script_dir/.env"

if [[ ! -f "$env_file" ]]; then
	cat >&2 <<-EOF
		No $env_file found.

		  cp tests/load/.env.example tests/load/.env
		  \$EDITOR tests/load/.env    # fill in K6_USER and K6_PASS

		The file is gitignored, so the credentials stay local.
	EOF
	exit 1
fi

# Anything already exported by the caller wins over the file, so a one-off run
# against a different site stays a one-off: K6_BASE=... ./tests/load/run.sh
pre_base=${K6_BASE-}
pre_user=${K6_USER-}
pre_pass=${K6_PASS-}

set -a
# shellcheck source=/dev/null
source "$env_file"
set +a

[[ -n "$pre_base" ]] && export K6_BASE="$pre_base"
[[ -n "$pre_user" ]] && export K6_USER="$pre_user"
[[ -n "$pre_pass" ]] && export K6_PASS="$pre_pass"

missing=()
[[ -n "${K6_USER:-}" ]] || missing+=(K6_USER)
[[ -n "${K6_PASS:-}" ]] || missing+=(K6_PASS)
if ((${#missing[@]})); then
	echo "Still blank in $env_file: ${missing[*]}" >&2
	exit 1
fi

# Echo the target, never the credentials.
echo "k6 -> ${K6_BASE:-http://egrm.local:8000} as ${K6_USER}"
exec k6 run "$@" "$script_dir/sync_api.js"
