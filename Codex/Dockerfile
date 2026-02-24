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
