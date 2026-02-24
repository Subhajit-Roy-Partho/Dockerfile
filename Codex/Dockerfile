FROM node:lts-alpine3.22

RUN apk add --no-cache socat net-tools \
    && npm install -g @openai/codex

WORKDIR /home/node

COPY --chown=node:node docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

USER node

EXPOSE 1456

ENTRYPOINT ["docker-entrypoint.sh"]
CMD []

############### For running with local auth and setup ######################
# docker run --rm -it -p 1455:1456 -v ~/.codex:/home/node/.codex subhajitroy/codex:latest


############## For running normal sh ############################
# docker run --rm -it -p 1455:1456 -v $PWD:/home/node/mount subhajitroy/codex:latest

# Don't forget to mount a local dir or push your task to github before closing