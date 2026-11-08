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
      assert.ok(s.line>=1 && s.end_line>=s.line,'Source range');
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
  const manifest=await json('docs/interactive/GENERATION-V2.json');
  const trace=await json('docs/interactive/TRACEABILITY-V2.json');
  const legacy=await json('docs/interactive/GENERATION.json');
  assert.equal(manifest.sourceCommit,trace.revision);
  assert.equal(manifest.diagrams.length,7);
  for(const item of manifest.diagrams){
    const source=await read(item.source), raw=(await read(item.output)).toString('utf8'), spec=JSON.parse(source);
    assert.equal(sha(source),item.sourceSha256,item.id+' source');
    assert.equal(sha(raw),item.htmlSha256,item.id+' official HTML');
    assert.equal(spec.meta.repository.revision,trace.revision);
    assert.deepEqual(Object.values(item.gates),['pass','pass','pass','pass']);
    validateGraph(spec);
    const sheet=(await read('docs/interactive/readable/'+item.id+'.html')).toString('utf8');
    assert.equal(sheet,readingSheet(spec,raw),item.id+' reproducible reading sheet');
    assert.equal(extract(sheet).svg,extract(raw).svg,item.id+' original SVG');
    assert.ok(!/C:[\\/]Users[\\/]|BEGIN (?:RSA |EC )?PRIVATE KEY|unsubscribe\?/i.test(raw+sheet),'Private material');
    const records=trace.diagrams[item.id];
    assert.deepEqual(Object.keys(records.nodes),(spec.components??spec.events).map(n=>n.id));
    assert.deepEqual(records.relations.map(e=>[e.id,e.from,e.to,e.label]),(spec.connections??[]).map(e=>[e.id,e.from,e.to,e.label]));
    for(const n of Object.values(records.nodes))for(const key of n.references)assert.ok(trace.fragments[key]);
  }
  for(const [key,f] of Object.entries(trace.fragments)){
    assert.equal(sha(f.text),f.fragmentLfSha256,key+' fragment');
    assert.equal(f.text.trimEnd().split('\n').length<=f.endLine-f.line+1,true);
  }
  for(const [p,hash] of Object.entries(trace.implementationFiles))assert.equal(sha(lf(await read(p))),hash,'Implementation changed: review diagram claim: '+p);
  for(const [id,hash] of Object.entries(manifest.legacyHtmlSha256)){
    assert.equal(sha(await read('docs/interactive/'+id+'.html')),hash,'Historical HTML must remain intact');
    const historical=await read('docs/interactive/source/'+id+'.json');
    // October's fifth receipt hashes CRLF; the committed source is LF. Preserve both, not a fabricated new receipt.
    const historicalReceiptBytes=id==='future-integrations'?lf(historical).replaceAll('\n','\r\n'):historical;
    assert.equal(sha(historicalReceiptBytes),legacy.diagrams.find(d=>d.id===id).sourceSha256,'Historical source');
  }
  for(const [p,hash] of Object.entries(manifest.legacyRasterSha256))assert.equal(sha(await read(p)),hash,'Historical raster');
  const reproduction=await json('docs/interactive/evidence/REPRODUCTION.json');
  assert.equal(reproduction.length,7);
  for(const r of reproduction){assert.equal(r.byteIdentical,true);assert.equal(r.htmlSha256,manifest.diagrams.find(d=>d.id===r.id).htmlSha256);}
  const qa=await json('docs/interactive/evidence/screenshots/BROWSER-QA.json');
  assert.equal(qa.externalRequests,0);assert.equal(qa.captures.length,28);assert.equal(qa.mobileDetails.length,14);
  for(const c of [...qa.captures,...qa.mobileDetails]){
    assert.equal(path.basename(c.file),c.file,'Capture must be local');
    assert.equal(sha(await read('docs/interactive/evidence/screenshots/'+c.file)),c.pngSha256,'Capture changed');
    const output=manifest.diagrams.find(d=>d.id===c.id).output;
    const html=c.view==='official'?output:'docs/interactive/readable/'+c.id+'.html';
    assert.equal(sha(await read(html)),c.htmlSha256,'Screenshot no longer describes delivered HTML');
  }
  return {diagrams:manifest.diagrams.length,relations:Object.values(trace.diagrams).reduce((n,d)=>n+d.relations.length,0),fragments:Object.keys(trace.fragments).length,awsWrites:0};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))console.log(JSON.stringify(await verify()));
