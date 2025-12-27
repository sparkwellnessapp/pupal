/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow images from any domain for PDF thumbnails
  images: {
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
      },
    ],
  },
}

module.exports = nextConfig
