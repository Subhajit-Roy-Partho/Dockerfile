FROM alpine:latest
RUN apk add --no-cache x11vnc x11vnc-doc xvfb xterm xorg-server xf86-video-dummy i3wm i3status i3lock xdpyinfo xdpyinfo-doc i3wm-doc i3lock-doc i3status-doc ttf-dejavu xset
COPY ./script.sh /root/
WORKDIR /root/
RUN sh script.sh

COPY ./10-headless.conf /etc/X11/xorg.conf.d/
RUN mkdir /root/i3logs
COPY ./.xinitrc /root/
COPY ./.Xresources /root/
COPY ./vnc.sh /root/
RUN apk add --no-cache g++ gcc libstdc++
RUN wget -O- https://aka.ms/install-vscode-server/setup.sh | sh
