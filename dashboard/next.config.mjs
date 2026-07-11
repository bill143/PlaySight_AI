/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Standalone output keeps the Docker image for docker/Dockerfile.dashboard small.
  output: "standalone",
};

export default nextConfig;
