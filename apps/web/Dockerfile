FROM node:22.22.2-bookworm-slim@sha256:9f6d5975c7dca860947d3915877f85607946403fc55349f39b4bc3688448bb6e AS build
WORKDIR /app
ARG ORQENTRA_DEPLOYMENT_ENV=development
ENV ORQENTRA_DEPLOYMENT_ENV=$ORQENTRA_DEPLOYMENT_ENV
ARG VITE_CLERK_PUBLISHABLE_KEY=
ENV VITE_CLERK_PUBLISHABLE_KEY=$VITE_CLERK_PUBLISHABLE_KEY
COPY package.json package-lock.json .npmrc ./
COPY apps/web/package.json apps/web/package.json
COPY packages/contracts/package.json packages/contracts/package.json
RUN npm ci
COPY apps/web apps/web
COPY packages/contracts packages/contracts
COPY infrastructure/nginx.conf infrastructure/nginx.conf
COPY infrastructure/web_security.mjs infrastructure/web_security.mjs
RUN NODE_OPTIONS=--max-old-space-size=512 npm run build && node infrastructure/web_security.mjs infrastructure/nginx.conf /app/nginx.conf

FROM nginx:stable-alpine@sha256:47928bf67eb62a1863cb08d9ecb52d3e704304ba614eaee17884204677702951
COPY --from=build /app/nginx.conf /etc/nginx/nginx.conf
COPY --from=build /app/apps/web/dist /usr/share/nginx/html
COPY --chmod=555 infrastructure/start-web.sh /start-web.sh
USER nginx
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
ENTRYPOINT ["/start-web.sh"]
