FROM alpine:latest
RUN apk add --no-cache wget git g++ gcc cmake make libintl gettext-dev
RUN cd /home; git clone https://github.com/neovim/neovim; cd neovim; make CMAKE_BUILD_TYPE=RelWithDebInfo; make install; cd ..; rm -rf neovim
RUN git clone https://github.com/NvChad/NvChad ~/.config/nvim --depth 1;