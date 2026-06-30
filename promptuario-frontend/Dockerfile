# ─── Stage 1: Build ───────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --frozen-lockfile

COPY . .
RUN npm run build



# ─── Stage 2: Serve ───────────────────────────────────────────────────────
FROM nginx:1.27-alpine

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# SPA fallback config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
