FROM subhajitroy/gromacs:2025.0-cuda12.8-gpu-mpi

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    coreutils \
    gawk \
    grep \
    sed \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/gromacs-swaxs

COPY bin/swaxs /usr/local/bin/swaxs
COPY tests /opt/gromacs-swaxs/tests

RUN chmod +x \
    /usr/local/bin/swaxs \
    /opt/gromacs-swaxs/tests/selftest_gpu.sh \
    /opt/gromacs-swaxs/tests/data_gen/generate_minimal_system.sh

ENTRYPOINT ["swaxs"]
CMD ["help"]
