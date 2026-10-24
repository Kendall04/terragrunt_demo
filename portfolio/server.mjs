import http from 'node:http';
import {archifyPresentation,diagramPolicy} from './archify.mjs';
import {archifyCatalog} from './archify-catalog.mjs';
import {readFile} from 'node:fs/promises';
import {fileURLToPath,pathToFileURL} from 'node:url';
import path from 'node:path';
const root=path.dirname(fileURLToPath(import.meta.url));
const routes=new Map([
 ['/', ['index.html','text/html']], ['/index.html',['index.html','text/html']],
 ['/style.css',['style.css','text/css']], ['/app.mjs',['app.mjs','text/javascript']],
 ['/facts.mjs',['facts.mjs','text/javascript']], ['/archify-catalog.mjs',['archify-catalog.mjs','text/javascript']], ['/favicon.svg',['favicon.svg','image/svg+xml']],
 ['/source/architecture',['../terraform/docs/architecture.md','text/plain']],
 ['/source/recovery',['../operations/sql-backup/recovery/RUNBOOK.md','text/plain']],
 ['/source/backup',['../operations/sql-backup/README.md','text/plain']],
 ['/source/completion',['../terraform/docs/v2-local-completion.md','text/plain']],
 ['/source/sentinel-trial',['../operations/integrations/NATIVE-TRIAL-2026-10-23.md','text/plain']],
 ['/source/sentinel-next',['../terraform/infra/sentinel-backup/REVIEW-r20261024b2.md','text/plain']]
]);
export function createServer(){
 return http.createServer(async(req,res)=>{
  res.setHeader('Content-Security-Policy',"default-src 'self'; connect-src 'none'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'; frame-src 'self'");
  res.setHeader('X-Content-Type-Options','nosniff');
  res.setHeader('Cache-Control','no-store');
  res.setHeader('Referrer-Policy','no-referrer');
  if(!['GET','HEAD'].includes(req.method)){
   res.setHeader('Allow','GET, HEAD');res.writeHead(405);res.end('Read-only local demo');return;
  }
  // This is a local origin server, never a proxy; malformed targets must not
  // throw out of the async callback or resolve an external absolute URI.
  if(typeof req.url!=='string'||!req.url.startsWith('/')||req.url.startsWith('//')){
   res.writeHead(400);res.end('Invalid request target');return;
  }
  let url;
  try{url=new URL(req.url,'http://127.0.0.1');}
  catch{res.writeHead(400);res.end('Invalid request target');return;}
  const diagram=archifyCatalog.find(item=>url.pathname==='/diagrams/'+item.id);
  if(diagram){
   try{const body=await archifyPresentation(diagram.id);res.setHeader('Content-Security-Policy',diagramPolicy);res.setHeader('Content-Type','text/html; charset=utf-8');res.writeHead(200);res.end(req.method==='HEAD'?undefined:body);}
   catch{res.writeHead(503);res.end('Diagram unavailable or integrity mismatch');}
   return;
  }
  const route=routes.get(url.pathname);
  if(!route){res.writeHead(404);res.end('Not found');return;}
  try{
   const body=await readFile(path.resolve(root,route[0]));
   res.setHeader('Content-Type',route[1]+'; charset=utf-8');
   res.writeHead(200);res.end(req.method==='HEAD'?undefined:body);
  }catch{res.writeHead(404);res.end('Source unavailable');}
 });
}
if(process.argv[1]&&import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href){
 const server=createServer();
 server.on('error',()=>{console.error('Local port unavailable; no existing server adopted.');process.exitCode=1;});
 server.listen(4181,'127.0.0.1',()=>console.log('DEMO LOCAL: http://127.0.0.1:4181 — synthetic only; Ctrl+C to close.'));
 for(const event of ['SIGTERM','SIGINT'])process.once(event,()=>server.close());
}
