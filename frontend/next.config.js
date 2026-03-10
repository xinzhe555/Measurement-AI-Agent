// next.config.js
/** @type {import('next').NextConfig} */
const nextConfig = {
  // 讓 Next.js 知道後端 API URL（開發 vs 部署時從 .env 讀取）
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000',
  },
}

module.exports = nextConfig
