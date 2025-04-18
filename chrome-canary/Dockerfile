FROM ubuntu:latest 
ENV DEBIAN_FRONTEND=noninteractive
RUN apt update && \
	apt install -y wget gnupg
RUN wget https://dl.google.com/linux/direct/google-chrome-canary_current_amd64.deb && \
	apt install -y ./google-chrome-canary_current_amd64.deb

#docker run -it --rm \
  # --gpus all \
  # -e DISPLAY=$DISPLAY \
  # -v /tmp/.X11-unix:/tmp/.X11-unix \
  # --name gpu_gui_test \
  # nvidia/cuda:12.2.0-base-ubuntu22.04 \
  # bash
