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
test('only expected assets and four source documents are served',async()=>{
 for(const route of ['/','/index.html','/style.css','/app.mjs','/facts.mjs','/favicon.svg','/source/architecture','/source/recovery','/source/backup','/source/completion']){const res=await request(route);assert.equal(res.status,200,route);assert(res.text.length>0);}
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
