import { existsSync,mkdirSync,readdirSync,readFileSync,writeFileSync } from 'node:fs'
import { dirname,extname,join,resolve } from 'node:path'

const input=resolve(process.argv[2] || 'local-data/media.jsonl')
const output=resolve(process.argv[3] || 'src/data/localHousingMedia.generated.ts')
const mediaRoot=resolve(process.argv[4] || 'public/media/apartments/sibdom')
const imageExtensions=new Set(['.jpg','.jpeg','.png','.webp','.avif'])

const mediaPath=value => {
  const path=String(value || '').replace(/\\/g,'/').replace(/^\.\//,'')
  const marker='/media/'
  const index=path.lastIndexOf(marker)
  const relative=index >= 0 ? path.slice(index+marker.length) : path.replace(/^media\//,'')
  return '/media/'+relative.split('/').filter(Boolean).map(encodeURIComponent).join('/')
}

const groups={}

function push(entityId,item) {
  ;(groups[entityId] ||= []).push(item)
}

function fromJsonl() {
  const rows=readFileSync(input,'utf8')
    .split(/\r?\n/)
    .map(line => line.trim())
    .filter(Boolean)
    .map((line,index) => {
      try { return JSON.parse(line) }
      catch(error) { throw new Error(`Invalid JSONL at line ${index+1}: ${error.message}`) }
    })

  for (const row of rows) {
    if (row.entity_type && row.entity_type !== 'apartment') continue
    const entityId=String(row.entity_id || '').trim()
    if (!entityId) continue
    const url=mediaPath(row.local_path || row.storage_key)
    if (url === '/media/') continue
    push(entityId,{
      id:String(row.id || row.storage_key || `${entityId}:${row.position ?? 0}`),
      url,
      order:Number.isFinite(Number(row.position)) ? Number(row.position) : 0,
      is_cover:Boolean(row.is_cover),
      storage_key:row.storage_key || undefined,
      local_path:row.local_path || undefined,
      attribution:row.attribution || undefined,
      rights_status:row.rights_status || undefined,
      publication_allowed:typeof row.publication_allowed === 'boolean' ? row.publication_allowed : undefined
    })
  }
}

function fromMediaFolders() {
  if (!existsSync(mediaRoot)) {
    throw new Error(`Neither ${input} nor media root ${mediaRoot} exists`)
  }

  const apartmentDirs=readdirSync(mediaRoot,{ withFileTypes:true })
    .filter(entry => entry.isDirectory())
    .sort((a,b) => a.name.localeCompare(b.name,'ru',{ numeric:true }))

  for (const directory of apartmentDirs) {
    const apartmentId=directory.name
    const folder=join(mediaRoot,apartmentId)
    const files=readdirSync(folder,{ withFileTypes:true })
      .filter(entry => entry.isFile() && imageExtensions.has(extname(entry.name).toLowerCase()))
      .sort((a,b) => a.name.localeCompare(b.name,'ru',{ numeric:true }))

    const items=files.map((file,index) => {
      const localPath=join('media','apartments','sibdom',apartmentId,file.name).replace(/\\/g,'/')
      return {
        id:`sibdom:${apartmentId}:${index}`,
        url:mediaPath(localPath),
        order:index,
        is_cover:index === 0,
        storage_key:localPath,
        local_path:localPath,
        attribution:'СИБДОМ',
        rights_status:'local-demo',
        publication_allowed:undefined
      }
    })

    if (!items.length) continue
    groups[apartmentId]=items
    groups[`sibdom:${apartmentId}`]=items
  }
}

if (existsSync(input)) {
  fromJsonl()
  console.log(`Media manifest source: ${input}`)
} else {
  fromMediaFolders()
  console.log(`media.jsonl not found; scanned local folders: ${mediaRoot}`)
}

for (const items of Object.values(groups)) items.sort((a,b) => a.order-b.order)

mkdirSync(dirname(output),{ recursive:true })
const source=`// Generated from local housing media. Temporary frontend-only bridge.\nexport const localHousingMedia = ${JSON.stringify(groups,null,2)} as Record<string, Array<{ id:string; url:string; order:number; is_cover:boolean; storage_key?:string; local_path?:string; attribution?:string; rights_status?:string; publication_allowed?:boolean }>>\n`
writeFileSync(output,source)

const physicalFiles=Object.values(groups)
  .flat()
  .filter((item,index,array) => array.findIndex(candidate => candidate.url === item.url) === index)
  .length
console.log(`Wrote ${Object.keys(groups).length} lookup keys for ${physicalFiles} local photos to ${output}`)
