# Build context is the repo root (see docker-compose.yml) so the
# @home-finder/shared workspace resolves during install + build.
FROM node:20-slim
WORKDIR /srv
COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/
COPY packages/shared/package.json ./packages/shared/
RUN npm ci
COPY . .
RUN npm run build --workspace @home-finder/web
EXPOSE 3000
WORKDIR /srv/apps/web
CMD ["npm", "start"]
