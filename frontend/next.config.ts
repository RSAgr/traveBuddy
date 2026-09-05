import type { NextConfig } from "next";

// FastAPI is started on IPv4 loopback. Using the same explicit address avoids
// Windows resolving `localhost` to IPv6 and dropping the Next.js proxy request.
const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "images.unsplash.com",
      },
      {
        protocol: "https",
        hostname: "places.googleapis.com",
      }
    ],
  },
};

export default nextConfig;
