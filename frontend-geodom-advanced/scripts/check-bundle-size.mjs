import { gzipSync } from 'node:zlib'
import { readdirSync,readFileSync,statSync } from 'node:fs'
import { join } from 'node:path'

const assetsDir='dist/assets'
const files=readdirSync(assetsDir).filter(file => file.endsWith('.js'))
const rows=files.map(file => {
  const path=join(assetsDir,file)
  const raw=statSync(path).size
  const gzip=gzipSync(readFileSync(path)).length
  return { file,raw,gzip }
}).sort((a,b) => b.gzip-a.gzip)

const kib=value => Math.round(value/1024)
const totalGzip=rows.reduce((sum,row) => sum+row.gzip,0)
const largest=rows[0]

for (const row of rows) {
  console.log(`${row.file.padEnd(42)} raw ${String(kib(row.raw)).padStart(4)} KiB · gzip ${String(kib(row.gzip)).padStart(4)} KiB`)
}
console.log(`TOTAL JS GZIP: ${kib(totalGzip)} KiB`)

const MAX_SINGLE_GZIP=260*1024
const MAX_TOTAL_GZIP=550*1024

if (largest && largest.gzip > MAX_SINGLE_GZIP) {
  console.error(`Largest JS chunk exceeds ${kib(MAX_SINGLE_GZIP)} KiB gzip: ${largest.file} (${kib(largest.gzip)} KiB)`)
  process.exitCode=1
}
if (totalGzip > MAX_TOTAL_GZIP) {
  console.error(`Total JS exceeds ${kib(MAX_TOTAL_GZIP)} KiB gzip: ${kib(totalGzip)} KiB`)
  process.exitCode=1
}
