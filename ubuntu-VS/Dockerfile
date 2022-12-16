FROM ubuntu:latest
ENV DEBIAN_FRONTEND=noninteractive
RUN apt update && apt upgrade -y && apt dist-upgrade -y && apt auto-remove -y && apt install gcc g++ wget python3 libarchive-dev libarchive-tools -y && rm -rf /var/lib/apt/lists/*
RUN wget -O- https://aka.ms/install-vscode-server/setup.sh | sh
