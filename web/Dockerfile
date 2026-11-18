# Web da Léia (Next.js). LEIA_API_URL entra no build (rewrites do next.config.ts).
FROM node:24-slim AS build
WORKDIR /app
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
ARG LEIA_API_URL=http://api:8000
ENV LEIA_API_URL=$LEIA_API_URL NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:24-slim
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=build /app ./
EXPOSE 3000
CMD ["npm", "run", "start", "--", "-p", "3000"]
