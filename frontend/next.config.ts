import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Docker's runtime stage copies only .next/standalone + .next/static + public/ - a fraction
  // of a full node_modules install - rather than shipping the entire project into the image.
  output: "standalone",
};

export default nextConfig;
