import type { NextConfig } from "next";

// A web fala só com `/api/*` (mesma origem); o Next encaminha para a API FastAPI.
// Assim o cookie `leia_sessao` (HttpOnly, SameSite=Lax) funciona sem CORS.
const API = process.env.LEIA_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/:path*` }];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
