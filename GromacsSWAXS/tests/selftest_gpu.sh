#!/usr/bin/env bash
set -euo pipefail

set +u
source /usr/local/gromacs/bin/GMXRC
set -u

export OMPI_ALLOW_RUN_AS_ROOT=1
export OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1

DATA_GEN_SCRIPT="/opt/gromacs-swaxs/tests/data_gen/generate_minimal_system.sh"
WORKDIR="${SWAXS_SELFTEST_WORKDIR:-/tmp/gromacs-swaxs-selftest}"

fail() {
    echo "selftest_gpu: $*" >&2
    exit 1
}

usage() {
    cat <<'EOF'
Usage:
  selftest_gpu.sh [--workdir DIR]

Runs a GPU-required end-to-end validation:
1) Generate a synthetic MD system.
2) Run mdrun in GPU mode.
3) Run SWAXS (SAXS + SANS) through the swaxs CLI.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --workdir)
            [[ -n "${2:-}" ]] || fail "--workdir requires a value"
            WORKDIR="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            fail "Unknown option: $1"
            ;;
    esac
done

require_gpu_runtime() {
    if [[ ! -e /dev/nvidiactl && ! -e /dev/nvidia0 ]]; then
        fail "NVIDIA device files are unavailable. Re-run with --gpus all."
    fi
}

validate_xvg() {
    local file="$1"
    [[ -s "$file" ]] || fail "Missing or empty output: $file"
    grep -q "@TYPE xy" "$file" || fail "Invalid XVG format (missing @TYPE xy): $file"
    grep -Eq '^[[:space:]]*[0-9]+\.[0-9]+' "$file" || fail "No numeric q/intensity rows found: $file"
}

require_gpu_runtime
[[ -x "$DATA_GEN_SCRIPT" ]] || fail "Data generation script not found: $DATA_GEN_SCRIPT"

rm -rf "$WORKDIR"
mkdir -p "$WORKDIR/input" "$WORKDIR/out"

"$DATA_GEN_SCRIPT" "$WORKDIR/input" gpu

swaxs run \
    --traj "$WORKDIR/input/md.xtc" \
    --structure "$WORKDIR/input/md.tpr" \
    --type saxs \
    --startq 0 \
    --endq 1.0 \
    --qspacing 0.1 \
    --output "$WORKDIR/out/saxs.xvg"

swaxs run \
    --traj "$WORKDIR/input/md.xtc" \
    --structure "$WORKDIR/input/md.tpr" \
    --type sans \
    --startq 0 \
    --endq 1.0 \
    --qspacing 0.1 \
    --output "$WORKDIR/out/sans.xvg"

validate_xvg "$WORKDIR/out/saxs.xvg"
validate_xvg "$WORKDIR/out/sans.xvg"

echo "selftest_gpu: PASS"
echo "Outputs:"
echo "  $WORKDIR/out/saxs.xvg"
echo "  $WORKDIR/out/sans.xvg"
