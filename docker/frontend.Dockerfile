# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Frontend image: build the Vite/React bundle, then serve it with nginx.
# nginx also reverse-proxies /api to the backend so the browser talks to a
# single origin (no CORS, no API base configuration needed in the bundle).
# Build context is the repository root (see docker-compose.yml).
# ---------------------------------------------------------------------------

# ---- Stage 1: build the static assets --------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies from the lockfile for reproducible builds.
COPY package.json package-lock.json ./
RUN npm ci

# Copy the sources needed by `tsc && vite build`.
COPY tsconfig.json vite.config.ts postcss.config.js tailwind.config.js ./
COPY scripts ./scripts
COPY app ./app

# `npm run build` runs `tsc && vite build`; output goes to ./dist
# (vite.config.ts sets build.outDir to ../../dist relative to app/frontend).
RUN npm run build

# ---- Stage 2: serve with nginx ---------------------------------------------
FROM nginx:1.27-alpine AS runtime

# Reverse-proxy + SPA fallback configuration.
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf

# Static bundle produced in stage 1.
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=5 \
    CMD wget -q -O /dev/null http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
