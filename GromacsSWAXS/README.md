# GromacsSWAXS

`GromacsSWAXS` provides a SWAXS-focused CLI on top of your existing GROMACS MPI/CUDA image:

- Base image: `subhajitroy/gromacs:2025.0-cuda12.8-gpu-mpi`
- SWAXS backend: `gmx_mpi scattering`
- Entry command: `swaxs`

## Build

```bash
docker build -t subhajitroy/gromacs-swaxs:2025.0-cuda12.8-gpu-mpi /home/subho/Documents/tmp/GromacsSWAXS
```

## CLI Usage

Show help:

```bash
docker run --rm subhajitroy/gromacs-swaxs:2025.0-cuda12.8-gpu-mpi help
```

Run SWAXS with your own files:

```bash
docker run --rm -v "$PWD:/work" -w /work \
  subhajitroy/gromacs-swaxs:2025.0-cuda12.8-gpu-mpi \
  run --traj traj.xtc --structure topol.tpr --type saxs --output scattering.xvg
```

## Tests

### 1) Local functional smoke test (CPU path)

This verifies command wiring and output format when no GPU is available.

```bash
docker run --rm --entrypoint bash subhajitroy/gromacs-swaxs:2025.0-cuda12.8-gpu-mpi -lc '
set -e
/opt/gromacs-swaxs/tests/data_gen/generate_minimal_system.sh /tmp/swaxs-smoke cpu
swaxs run --traj /tmp/swaxs-smoke/md.xtc --structure /tmp/swaxs-smoke/md.tpr --type saxs --output /tmp/swaxs-smoke/scattering.xvg
test -s /tmp/swaxs-smoke/scattering.xvg
'
```

### 2) Required GPU end-to-end self-test

This test is strict and fails if GPU runtime is unavailable.

```bash
docker run --rm --gpus all subhajitroy/gromacs-swaxs:2025.0-cuda12.8-gpu-mpi selftest
```

The self-test validates:
- synthetic input generation
- `mdrun -nb gpu`
- SWAXS output for both `saxs` and `sans`

## Notes

- This image uses `gmx_mpi` (not `gmx`).
- For MPI inside container as root, `OMPI_ALLOW_RUN_AS_ROOT` variables are set by the scripts.
