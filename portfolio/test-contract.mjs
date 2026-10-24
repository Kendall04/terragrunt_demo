import {createHash} from 'node:crypto';
import {adaptArchify,archifyPresentation} from './archify.mjs';
import {archifyCatalog} from './archify-catalog.mjs';
import test,{before,after} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import http from 'node:http';
import {createServer} from './server.mjs';
import {portfolioContract,topologies} from './facts.mjs';
import {assertPortfolioContract} from './contract.mjs';
const read=name=>readFile(new URL(name,import.meta.url),'utf8');
const input={html:await read('index.html'),app:await read('app.mjs'),css:await read('style.css'),contract:portfolioContract,topologies};
test('DEMO/history, source facts, navigation and accessible source contracts',()=>assertPortfolioContract(input));
test('guided evidence path and historical distinct-image rollback preserve scope',async()=>{
 const deployment=await read('../terraform/docs/deployment.md');
 assert.match(deployment,/sha256:ca7d92532/);assert.match(deployment,/sha256:7aa96288/);assert.match(deployment,/A also read\/decrypted the text written by B/);
 assert.match(input.html,/A → B → A/);assert.match(input.html,/continuidad SQL\/KMS/);assert.match(input.html,/No revierte migraciones/);
 for(const step of ['demo','v1','deployment','az6','observability','pending'])assert(input.html.includes(`data-tour="${step}"`));
 assert.match(input.html,/10 efectos Pending/);assert.match(input.html,/LOCAL · NO DESPLEGADO/);assert.match(input.html,/PKI fuera de alcance de ECS/);
});

test('Sentinel pilot, local target and real backup freshness are distinct',async()=>{
 const trial=await read('../operations/integrations/NATIVE-TRIAL-2026-10-23.md');
 assert.match(trial,/owner separately supplied both inbox receipts/);assert.match(trial,/10 Pending effects/);
 assert.match(input.html,/7 recibos y 7 auditorías/);assert.match(input.html,/ambos avisos se acreditaron en el buzón/);
 assert.match(input.html,/todavía no está desplegada ni autorizada/);assert.match(input.html,/168 h/);assert.match(input.html,/no prueba frescura de 2 h/);
 assert.doesNotMatch(input.html,/Sentinel y correo real\.<|Observación y notificaciones reales siguen pendientes|Persistencia de prueba en memoria/);
});

test('external requests and injected third-party assets fail policy',()=>{
 for(const app of [input.app+"\nfetch('https://example.invalid')",input.app+'\nnew WebSocket("wss://example.invalid")'])assert.throws(()=>assertPortfolioContract({...input,app}));
 for(const html of [input.html+'<script src="https://example.invalid/a.js"></script>',input.html+'<img src="//example.invalid/x">'])assert.throws(()=>assertPortfolioContract({...input,html}));
 assert.throws(()=>assertPortfolioContract({...input,css:input.css+'\n@import "theme.css";'}));
});
test('false live data/provenance and live topology labels fail policy',()=>{
 assert.throws(()=>assertPortfolioContract({...input,html:input.html.replace('DEMO LOCAL','AWS LIVE')}));
 assert.throws(()=>assertPortfolioContract({...input,contract:{...portfolioContract,liveConnected:true}}));
 assert.throws(()=>assertPortfolioContract({...input,contract:{...portfolioContract,provenance:'archify-generated'}}));
 const changed=structuredClone(topologies);changed.az6.mode='live';assert.throws(()=>assertPortfolioContract({...input,topologies:changed}));
});
test('reintroducing PKI as an ECS completion requirement fails current scope',()=>{
 assert.throws(()=>assertPortfolioContract({...input,html:input.html.replace('PKI fuera de alcance de ECS','PKI requerida para ECS')}));
});

test('removing navigation focus, skip link or live announcements fails contract',()=>{
 assert.throws(()=>assertPortfolioContract({...input,app:input.app.replace('if(moveFocus)','if(false)')}));
 assert.throws(()=>assertPortfolioContract({...input,html:input.html.replace('class="skip-link"','class="removed"')}));
 assert.throws(()=>assertPortfolioContract({...input,html:input.html.replace('role="status" aria-live="polite"','role="note"')}));
});
test('historical node facts cite the actual repository contracts',async()=>{
 const architecture=await read('../terraform/docs/architecture.md'),recovery=await read('../operations/sql-backup/recovery/RUNBOOK.md');
 for(const fact of ['API Gateway','VPC Link','ALB','Fargate','SQL','KMS'])assert(architecture.includes(fact),fact);
 assert(recovery.includes('NAT Gateway'));assert(recovery.includes('142.630783'));assert.match(input.html,/142,63/);assert.match(input.html,/destino ya preparado/);
});
const server=createServer();let port;
before(async()=>{await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));port=server.address().port;assert.equal(server.address().address,'127.0.0.1');});
after(async()=>{await new Promise(resolve=>server.close(resolve));assert.equal(server.listening,false);});
function request(target,method='GET'){return new Promise((resolve,reject)=>{const req=http.request({host:'127.0.0.1',port,path:target,method,agent:false},res=>{let text='';res.setEncoding('utf8');res.on('data',chunk=>text+=chunk);res.on('end',()=>resolve({status:res.statusCode,headers:res.headers,text}));});req.on('error',reject);req.end();});}
test('only expected assets and six source documents are served',async()=>{
 for(const route of ['/','/index.html','/style.css','/app.mjs','/facts.mjs','/favicon.svg','/source/architecture','/source/recovery','/source/backup','/source/completion','/source/sentinel-trial','/source/sentinel-next']){const res=await request(route);assert.equal(res.status,200,route);assert(res.text.length>0);}
});
test('HEAD is read-only and CSP forbids connections/external assets',async()=>{
 const res=await request('/','HEAD');assert.equal(res.status,200);assert.equal(res.text,'');assert.match(res.headers['content-security-policy'],/connect-src 'none'/);assert.match(res.headers['content-security-policy'],/script-src 'self'/);assert.match(res.headers['content-security-policy'],/form-action 'none'/);assert.equal(res.headers['x-content-type-options'],'nosniff');assert.equal(res.headers['cache-control'],'no-store');
});
test('unintended repository files and encoded traversal are never served',async()=>{
 for(const route of ['/README.md','/.git/config','/.aws/config','/portfolio/contract.mjs','/contract.mjs','/test-contract.mjs','/test-browser.mjs','/server.mjs','/source/unknown','/source/../README.md','/%2e%2e/.git/config','/source/%2e%2e/README.md','/source/architecture%00']){const res=await request(route);assert.equal(res.status,404,route);assert.equal(res.text,'Not found');}
});
test('mutation requests cannot change demo/source state',async()=>{
 for(const method of ['POST','PUT','PATCH','DELETE']){const res=await request('/',method);assert.equal(res.status,405,method);}
 assert.equal((await request('/')).text,input.html);
});
test('invalid or external absolute request targets refuse without proxying',async()=>{
 for(const route of ['http://[','http://example.invalid/source/architecture','//example.invalid/source/architecture'])assert.equal((await request(route)).status,400,route);
 assert.equal((await request('/')).status,200);
});

test('five genuine pinned Archify artifacts preserve historical/local and pending-installation scopes',async()=>{
 assert.equal(archifyCatalog.length,5);assert.match(archifyCatalog[4].mode,/LOCAL.*PENDIENTE/);assert.match(archifyCatalog[4].note,/PKI fuera de alcance de ECS/);assert.doesNotMatch(archifyCatalog[4].note,/son requisitos pendientes/);
 const pins=JSON.parse(await read('archify-pins.json'));assert.equal(pins.generator,'Archify 3.1.0');
 for(const item of archifyCatalog){const raw=await readFile(new URL('../docs/interactive/'+item.id+'.html',import.meta.url));assert.equal(createHash('sha256').update(raw).digest('hex'),pins.originalSha256[item.id]);assert.match(raw.toString(),/name="generator" content="archify 3.1.0"/);if(item.id==='future-integrations'){assert.doesNotMatch(raw.toString(),/Service Identity PKI|Servicio B objetivo/);assert.match(raw.toString(),/Piloto AWS retirado/);}}
});
test('presentation refuses changed bytes and active resource mutants',async()=>{
 const raw=await readFile(new URL('../docs/interactive/v1-platform.html',import.meta.url));
 assert.throws(()=>adaptArchify(raw,'0'.repeat(64)),/Unreviewed/);
 for(const suffix of ['<script src="https://example.invalid/x.js"></script>',"<script>fetch('https://example.invalid')</script>",'<iframe src="/other"></iframe>']){const changed=Buffer.concat([raw,Buffer.from(suffix)]);assert.throws(()=>adaptArchify(changed,createHash('sha256').update(changed).digest('hex')),/Unexpected active/);}
});
test('only isolated presentation routes served; original source and generator stay private',async()=>{
 for(const item of archifyCatalog){const res=await request('/diagrams/'+item.id);assert.equal(res.status,200,item.id);assert.match(res.headers['content-security-policy'],/connect-src 'none'/);assert.match(res.headers['content-security-policy'],/frame-src 'none'/);assert.match(res.text,/"verified":false,"repository":null/);assert.doesNotMatch(res.text,/<a[^>]*href=|Kendall04|C:\\Users/);assert.equal((await request('/diagrams/'+item.id,'HEAD')).text,'');}
 for(const route of ['/diagrams/unknown','/docs/interactive/v1-platform.html','/docs/interactive/source/v1-platform.json','/archify.mjs','/archify-pins.json','/diagrams/../server.mjs'])assert.equal((await request(route)).status,404,route);
});
test('host stays no-connect and diagram sandbox has no same-origin permission',async()=>{
 assert.match(input.html,/sandbox="allow-scripts"/);assert.doesNotMatch(input.html,/allow-same-origin|allow-top-navigation/);
 const res=await request('/');assert.match(res.headers['content-security-policy'],/frame-src 'self'/);assert.doesNotMatch(res.headers['content-security-policy'],/unsafe-inline/);
});
