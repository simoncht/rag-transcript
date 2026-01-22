/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  optimizeFonts: false,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  },
  webpack: (config, { isServer }) => {
    // Work around an occasional Windows dev/build mismatch where the server runtime
    // tries to require `./<id>.js` while chunks are emitted under `server/chunks/`.
    if (isServer && config?.output?.chunkFilename) {
      const chunkFilename = String(config.output.chunkFilename);
      if (!chunkFilename.includes('chunks/')) {
        config.output.chunkFilename = 'chunks/[id].js';
      }
    }
    return config;
  },
  async rewrites() {
    return [
      {
        // Proxy API requests to backend, but exclude NextAuth routes
        source: '/api/v1/:path*',
        destination: 'http://localhost:8000/api/v1/:path*',
      },
    ];
  },
}

module.exports = nextConfig
