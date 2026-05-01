import { cpSync, existsSync, mkdirSync, rmSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(scriptDir, '..')
const repoRoot = resolve(frontendRoot, '..')
const backendSource = resolve(repoRoot, 'tremor-guard-backend')
const backendBundle = resolve(frontendRoot, 'api', '_backend_bundle')

const copiedEntries = ['app', 'clinical.db', 'identity.db', 'storage']

if (!existsSync(backendSource)) {
  console.warn(`Skipping Vercel backend bundle; source not found: ${backendSource}`)
  process.exit(0)
}

rmSync(backendBundle, { recursive: true, force: true })
mkdirSync(backendBundle, { recursive: true })

for (const entry of copiedEntries) {
  const source = resolve(backendSource, entry)
  if (existsSync(source)) {
    cpSync(source, resolve(backendBundle, entry), { recursive: true })
  }
}

console.log(`Prepared Vercel backend bundle at ${backendBundle}`)
