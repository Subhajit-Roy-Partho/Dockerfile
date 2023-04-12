FROM ubuntu:latest
ENV DEBIAN_FRONTEND=noninteractive
RUN apt update && apt upgrade -y && apt dist-upgrade -y && apt auto-remove -y && apt install wget git xclip -y;
RUN wget https://github.com/neovim/neovim/releases/download/v0.9.0/nvim-linux64.tar.gz; tar -xvf nvim-linux64.tar.gz; rm -rf nvim-linux64.tar.gz; echo 'export PATH="$PATH:/nvim-linux64/bin"' >> ~/.bashrc;
RUN git clone https://github.com/NvChad/NvChad ~/.config/nvim --depth 1;
