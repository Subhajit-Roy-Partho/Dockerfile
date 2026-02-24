#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  generate_minimal_system.sh OUTPUT_DIR [cpu|gpu]

Arguments:
  OUTPUT_DIR  Directory where md.tpr and md.xtc are generated.
  MODE        mdrun nonbonded mode: cpu (default) or gpu.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi

output_dir="${1:-}"
nb_mode="${2:-cpu}"

[[ -n "$output_dir" ]] || { usage; exit 1; }
case "$nb_mode" in
    cpu|gpu) ;;
    *)
        echo "Invalid mode: $nb_mode (expected cpu or gpu)" >&2
        exit 1
        ;;
esac

set +u
source /usr/local/gromacs/bin/GMXRC
set -u

export OMPI_ALLOW_RUN_AS_ROOT=1
export OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1

mkdir -p "$output_dir"
cd "$output_dir"

cat > conf.pdb <<'PDB'
ATOM      1  A1  MOL A   1       1.000   1.000   1.000  1.00  0.00          AR
ATOM      2  A2  MOL A   1       1.450   1.000   1.000  1.00  0.00          AR
TER
END
PDB

cat > topol.top <<'TOP'
[ defaults ]
1 2 yes 1.0 1.0

[ atomtypes ]
; name  mass    charge ptype sigma epsilon
A       39.948  0.0    A     0.34  0.1

[ moleculetype ]
; name  nrexcl
MOL 1

[ atoms ]
; nr type resnr residue atom cgnr charge mass
1 A 1 MOL A1 1 0.0 39.948
2 A 1 MOL A2 1 0.0 39.948

[ system ]
SWAXS synthetic argon-like dimer

[ molecules ]
MOL 1
TOP

cat > md.mdp <<'MDP'
integrator = md
nsteps = 50
dt = 0.002
cutoff-scheme = Verlet
nstxout-compressed = 1
nstenergy = 10
nstlog = 10
coulombtype = Cut-off
rcoulomb = 0.9
vdwtype = Cut-off
rvdw = 0.9
rlist = 0.9
tcoupl = no
pcoupl = no
constraints = none
gen-vel = yes
gen-temp = 300
gen-seed = 173529
MDP

mpirun -np 1 gmx_mpi editconf -f conf.pdb -o conf.gro -box 2 2 2
mpirun -np 1 gmx_mpi grompp -f md.mdp -c conf.gro -p topol.top -o md.tpr
mpirun -np 1 gmx_mpi mdrun -deffnm md -s md.tpr -ntomp "${SWAXS_OMP_THREADS:-1}" -pin off -nb "$nb_mode"

[[ -s md.tpr ]] || { echo "Missing md.tpr" >&2; exit 1; }
[[ -s md.xtc ]] || { echo "Missing md.xtc" >&2; exit 1; }

echo "Generated synthetic input in: $output_dir"
