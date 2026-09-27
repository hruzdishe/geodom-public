FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_API_URL=
ARG VITE_YANDEX_MAPS_API_KEY=
ARG VITE_API_REQUEST_TIMEOUT_MS=15000
ARG VITE_LOCAL_MEDIA_BASE_URL=/media
ARG VITE_ALLOW_UNVERIFIED_LOCAL_MEDIA=false

ENV VITE_API_URL=$VITE_API_URL \
    VITE_API_REQUEST_TIMEOUT_MS=$VITE_API_REQUEST_TIMEOUT_MS \
    VITE_YANDEX_MAPS_API_KEY=$VITE_YANDEX_MAPS_API_KEY \
    VITE_LOCAL_MEDIA_BASE_URL=$VITE_LOCAL_MEDIA_BASE_URL \
    VITE_ALLOW_UNVERIFIED_LOCAL_MEDIA=$VITE_ALLOW_UNVERIFIED_LOCAL_MEDIA

RUN npm run build

FROM nginx:1.27-alpine AS runtime
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O - http://127.0.0.1/healthz || exit 1
