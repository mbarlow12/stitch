FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY index.html vite.config.js ./
COPY public/ ./public/
COPY src/ ./src/

ARG VITE_APP_VERSION
ARG VITE_BUILD_ID
ARG VITE_BUILD_TIME
ARG VITE_GIT_SHA
ARG VITE_NODE_VERSION
ARG VITE_VITE_VERSION
ARG VITE_USE_MOCK_DATA=false

ENV VITE_APP_VERSION=$VITE_APP_VERSION \
    VITE_BUILD_ID=$VITE_BUILD_ID \
    VITE_GIT_SHA=$VITE_GIT_SHA \
    VITE_NODE_VERSION=$VITE_NODE_VERSION \
    VITE_VITE_VERSION=$VITE_VITE_VERSION \
    VITE_BUILD_TIME=$VITE_BUILD_TIME \
    VITE_USE_MOCK_DATA=$VITE_USE_MOCK_DATA

RUN \
  export VITE_APP_VERSION=${VITE_APP_VERSION:-$(node -p "require('./package.json').version")} && \
  export VITE_BUILD_ID=${VITE_BUILD_ID:-docker-local} && \
  export VITE_BUILD_TIME=${VITE_BUILD_TIME:-$(date -u +%Y-%m-%dT%H:%M:%SZ)} && \
  export VITE_NODE_VERSION=${VITE_NODE_VERSION:-$(node -p process.version)} && \
  export VITE_VITE_VERSION=${VITE_VITE_VERSION:-$(node -p "require('./package.json').devDependencies.vite")} && \
  npm run build

FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
