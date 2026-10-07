# ==============================================================================
# MARGA Frontend — Vite production build served by nginx
#
# VITE_API_BASE is baked at build time. The default is relative (/api/v1):
# nginx proxies it to the backend service, so no hostname and no CORS setup is
# needed. Override with a build arg for a split deployment, e.g.
#   --build-arg VITE_API_BASE=https://api.example.com/api/v1
# ==============================================================================

FROM node:22-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Wins over any .env file in the build context (Vite gives process env priority).
ARG VITE_API_BASE=/api/v1
ENV VITE_API_BASE=$VITE_API_BASE

RUN npm run build

# ------------------------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/ > /dev/null || exit 1
