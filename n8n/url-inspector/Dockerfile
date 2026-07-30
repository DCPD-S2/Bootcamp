FROM node:22-bookworm

WORKDIR /app

# Aceeași locație pentru instalare și rulare
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

RUN npm init -y \
    && npm install express playwright ipaddr.js \
    && npx playwright install --with-deps chromium \
    && chmod -R 755 /ms-playwright

COPY --chown=node:node server.js .

USER node

EXPOSE 8080

CMD ["node", "server.js"]