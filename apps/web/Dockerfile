# Build stage using pinned Bun version
FROM oven/bun:1.4.4 AS builder

WORKDIR /app

# Copy dependency specifications and lockfile
COPY package.json bun.lock* ./
RUN bun install --frozen-lockfile

# Copy source code and build config
COPY . .

ARG VITE_API_URL=""
ENV VITE_API_URL=${VITE_API_URL}

# Build production static bundle
RUN bun run build

# Runtime stage: Nginx static file server (for local docker-compose)
FROM nginx:1.27-alpine AS runtime

COPY --from=builder /app/dist /usr/share/nginx/html

# Custom Nginx configuration supporting SPA client-side routing fallback
RUN echo 'server {' \
  '    listen 80;' \
  '    server_name localhost;' \
  '    root /usr/share/nginx/html;' \
  '    index index.html;' \
  '    location / {' \
  '        try_files $uri $uri/ /index.html;' \
  '    }' \
  '}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
