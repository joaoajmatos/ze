import path from "path"
import { fileURLToPath } from "url"
import nextEnv from "@next/env"

const { loadEnvConfig } = nextEnv

const repoRoot = path.join(path.dirname(fileURLToPath(import.meta.url)), "..")

// Same repo-root .env as backend (ze/settings.py) and docker-compose env_file.
// forceReload: Next already loaded frontend/ env before this config runs.
loadEnvConfig(repoRoot, process.env.NODE_ENV !== "production", undefined, true)

/** @type {import('next').NextConfig} */
const nextConfig = {}

export default nextConfig
