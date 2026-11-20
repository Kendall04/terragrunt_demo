// Offline diagram/evidence integrity checks. No AWS, browser, package install or Git mutation.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {root,sha,extract,readingSheet} from './readable.mjs';
const read = p => readFile(path.join(root,p));
const json = async p => JSON.parse(await read(p));
const lf = b => b.toString('utf8').replace(/^\uFEFF/,'').replaceAll('\r\n','\n');
export function validateGraph(spec) {
  const nodes=spec.components??spec.events, ids=nodes.map(n=>n.id);
  assert.equal(ids.length,new Set(ids).size,'Duplicate node');
  assert.match(spec.meta.repository.revision,/^[0-9a-f]{40}$/);
  assert.equal(spec.meta.repository.url,'https://github.com/Kendall04/terragrunt_demo.git');
  for(const n of nodes){
    assert.ok(n.sources.length>0 && n.sources.length<=3,'Source required');
    for(const s of n.sources){
      assert.ok(!s.path.includes('..') && !path.isAbsolute(s.path) && !s.path.includes('\\'),'Repository source path');
      assert.ok(s.line>=1 && (s.end_line??s.line)>=s.line,'Source range');
    }
  }
  const edges=spec.connections??[];
  assert.equal(edges.length,new Set(edges.map(e=>e.id)).size,'Duplicate relationship');
  for(const e of edges)assert.ok(ids.includes(e.from)&&ids.includes(e.to)&&e.from!==e.to&&e.label,'Invalid relationship');
  for(const b of spec.boundaries??[])for(const id of b.wraps)assert.ok(ids.includes(id),'Unknown boundary member');
  if(spec.events){
    for(const e of spec.events)assert.ok(spec.lanes.some(l=>l.id===e.lane)&&Number.isFinite(Date.parse(e.at)),'Timeline event');
    assert.ok(spec.events.every((e,i)=>i===0||Date.parse(e.at)>=Date.parse(spec.events[i-1].at)),'Timeline order');
  }
}
export async function verify() {
  const current=JSON.parse(await readFile(root+'/docs/interactive/GENERATION-CURRENT.json','utf8'));
  const trace=JSON.parse(await readFile(root+'/docs/interactive/TRACEABILITY-CURRENT.json','utf8'));
  assert.equal(current.diagrams.length,5);
  const {createHash}=await import('node:crypto');const hash=b=>createHash('sha256').update(b).digest('hex');
  for(const d of current.diagrams){
    const src=await readFile(root+'/docs/interactive/'+d.source);assert.equal(hash(src),d.sourceSha256);
    const spec=JSON.parse(src);validateGraph(spec);
    assert.equal(spec.meta.repository.revision,current.sourceRevision);
    assert.equal(await readFile(root+'/docs/interactive/readable/'+d.id+'.html','utf8'),readingSheet(spec,await readFile(root+'/docs/interactive/'+d.output,'utf8')),'Reproducible current reader');
    assert(!/tarea blue actuales|recursos AWS pendientes de retiro/.test(src.toString()),'No transient or retired runtime claims');
    assert(!spec.components.some(n=>/sentinel|observer/i.test(n.id)));
    const raw = await readFile(root+'/docs/interactive/'+d.output,'utf8');
    assert.equal(hash(raw),d.htmlSha256);
    assert.equal(extract(await readFile(root+'/docs/interactive/readable/'+d.id+'.html','utf8')).svg,extract(raw).svg);
    assert.ok(!/C:[\\/]Users[\\/]|BEGIN (?:RSA |EC )?PRIVATE KEY|unsubscribe\?/i.test(raw),'Private material');
    assert.equal(hash(await readFile(root+'/docs/interactive/readable/'+d.id+'.html')),d.readingSha256);
    assert.deepEqual(Object.values(d.gates),['pass','pass','pass','pass']);
  }
  const qa=JSON.parse(await readFile(root+'/docs/interactive/evidence/current/BROWSER-QA.json','utf8'));
  assert.equal(qa.status,'PASS');
  for(const d of current.diagrams)assert.equal(qa.diagrams[d.id],d.htmlSha256,'Visual review describes current output');
  for(const c of [...qa.captures,...qa.before])assert.equal(hash(await readFile(root+'/docs/interactive/evidence/current/'+c.file)),c.sha256,'Visual evidence bytes');
  for(const [p,expected] of Object.entries(trace.filesLfSha256)){
    const text=(await readFile(root+'/'+p,'utf8')).replace(/^\uFEFF/,'').replaceAll('\r\n','\n');
    assert.equal(hash(text),expected,'Current source changed: '+p);
  }

  return {diagrams:current.diagrams.length, awsWrites:0};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))console.log(JSON.stringify(await verify()));
