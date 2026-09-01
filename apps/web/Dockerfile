# Stage 1: Install dependencies
FROM node:20-alpine AS deps
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci

# Stage 2: Build
FROM node:20-alpine AS builder
WORKDIR /repo
COPY pyproject.toml ./
COPY apps/web/ ./apps/web/
COPY --from=deps /app/node_modules ./apps/web/node_modules
WORKDIR /repo/apps/web
ARG DGX_VERIFICATION_STATUS=container-build-unverified
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG NEXT_PUBLIC_DEMO_MODE=false
ENV DGX_VERIFICATION_STATUS=$DGX_VERIFICATION_STATUS
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_DEMO_MODE=$NEXT_PUBLIC_DEMO_MODE
RUN npm run build

# Stage 3: Runner
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs
USER nextjs

COPY --from=builder /repo/apps/web/public ./public
COPY --from=builder --chown=nextjs:nodejs /repo/apps/web/.next/standalone/apps/web ./
COPY --from=builder --chown=nextjs:nodejs /repo/apps/web/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
