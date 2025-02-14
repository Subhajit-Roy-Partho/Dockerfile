FROM ubuntu:latest

ENV TZ=America/Phoenix
ENV DEBIAN_FRONTEND=noninteractive
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN apt update && apt upgrade -y && apt dist-upgrade -y && apt auto-remove -y && apt install -y gcc g++ wget python3 cmake ninja-build zsh sudo git software-properties-common;add-apt-repository ppa:neovim-ppa/unstable -y; apt update; apt install -y neovim && rm -rf /var/lib/apt/lists/*
RUN mkdir /home/ringtail; useradd -m -s /bin/zsh -d /home/ringtail ringtail; chsh -s $(which zsh)
SHELL [ "/bin/zsh", "-c" ]



# WORKDIR /home/ringtail
# USER ringtail
# RUN git clone https://github.com/lorenzo-rovigatti/oxDNA.git

