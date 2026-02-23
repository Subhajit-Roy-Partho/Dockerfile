# CUDA 13.1.1 (Ubuntu 24.04) was attempted first, but can fail linking GROMACS 2025.0 in this setup.
# Use CUDA 12.8.1 as the default known-good base image.
# To try CUDA 13.1.1 explicitly, build with:
# docker build --build-arg CUDA_BASE_IMAGE=nvidia/cuda:13.1.1-devel-ubuntu24.04 -t gromacs:cuda13-mpi-omp Gromacs
ARG CUDA_BASE_IMAGE=nvidia/cuda:12.8.1-devel-ubuntu24.04
FROM ${CUDA_BASE_IMAGE}

ARG GMX_VERSION=2025.0
ARG GMX_SIMD=AVX2_256

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    cmake \
    git \
    pkg-config \
    wget \
    libfftw3-dev \
    libopenmpi-dev \
    openmpi-bin \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt

RUN wget -q https://ftp.gromacs.org/gromacs/gromacs-${GMX_VERSION}.tar.gz \
    && tar -xzf gromacs-${GMX_VERSION}.tar.gz \
    && rm -f gromacs-${GMX_VERSION}.tar.gz

WORKDIR /opt/gromacs-${GMX_VERSION}
RUN mkdir build
WORKDIR /opt/gromacs-${GMX_VERSION}/build

RUN cmake .. \
    -DGMX_BUILD_OWN_FFTW=OFF \
    -DGMX_GPU=CUDA \
    -DGMX_MPI=ON \
    -DGMX_THREAD_MPI=OFF \
    -DGMX_OPENMP=ON \
    -DGMX_SIMD=${GMX_SIMD} \
    -DCMAKE_C_COMPILER=mpicc \
    -DCMAKE_CXX_COMPILER=mpicxx \
    -DCMAKE_INSTALL_PREFIX=/usr/local/gromacs \
    && cmake --build . -j"$(nproc)" \
    && cmake --install . \
    && rm -rf /opt/gromacs-${GMX_VERSION}

ENV PATH=/usr/local/gromacs/bin:${PATH}
ENV LD_LIBRARY_PATH=/usr/local/gromacs/lib:${LD_LIBRARY_PATH}

CMD ["bash"]
