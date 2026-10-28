import { build } from 'esbuild';
import { mkdir, copyFile, readdir, readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
const target='src/aevora_observatory/static';
await mkdir(`${target}/assets`,{recursive:true});
// Preserve embedded shader bytes as escaped strings without literal line-end whitespace.
await build({entryPoints:['web/app.js'],bundle:true,minify:true,target:'es2022',supported:{'template-literal':false},legalComments:'eof',outfile:`${target}/assets/app.js`,sourcemap:false});
await copyFile('web/index.html',`${target}/index.html`);
const files={};
for(const p of ['index.html',...(await readdir(`${target}/assets`)).sort().map(n=>`assets/${n}`)])files[p]=createHash('sha256').update(await readFile(`${target}/${p}`)).digest('hex');
await writeFile(`${target}/BUILD_MANIFEST.json`,JSON.stringify({product:'Aevora',kind:'PUBLIC_STATIC_BUILD',node:process.version,files},null,2)+'\n');
console.log(JSON.stringify({status:'BUILT',files:Object.keys(files).length,node:process.version}));
