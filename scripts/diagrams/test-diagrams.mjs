import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {root,extract,readingSheet} from './readable.mjs';
import {validateGraph,verify} from './verify.mjs';
const source=JSON.parse(await readFile(root+'/docs/interactive/source/v2-sentinel.json','utf8'));
test('All diagrams, original SVGs, citations and historical bytes verify offline',async()=>{assert.equal((await verify()).diagrams,7);});
test('Broken and duplicate graph relationships fail closed',()=>{
  const d=structuredClone(source);d.connections[0].to='imaginary-remediator';assert.throws(()=>validateGraph(d));
  const duplicate=structuredClone(source);duplicate.components.push(duplicate.components[0]);assert.throws(()=>validateGraph(duplicate));
});
test('Missing evidence and arbitrary source paths are rejected',()=>{
  const d=structuredClone(source);d.components[0].sources=[];assert.throws(()=>validateGraph(d));
  const p=structuredClone(source);p.components[0].sources[0].path='../secret';assert.throws(()=>validateGraph(p));
});
test('Reading sheet refuses executable SVG or external CSS',()=>{
  assert.throws(()=>extract('<style>a{}</style><svg viewBox="0 0 1 1"><script>bad()</script></svg>'));
  assert.throws(()=>extract('<style>@import url(https://example.test/a)</style><svg viewBox="0 0 1 1"></svg>'));
});
test('Sentinel observes and never substitutes for recovery; real short incident has no fake alert',async()=>{
  assert.ok(!source.connections.some(e=>/nat|asg/i.test(e.to)));
  const t=JSON.parse(await readFile(root+'/docs/interactive/source/v2-nat-incident.json','utf8'));
  assert.ok(t.events.some(e=>e.id==='unknown'));
  assert.ok(t.cards.some(c=>c.items.some(i=>i.includes('NO hubo correo de caída'))));
  const a=t.events.find(e=>e.id==='terminate'),b=t.events.find(e=>e.id==='https');
  assert.equal(Date.parse(b.at)-Date.parse(a.at),149192); // Millisecond-rounded display; original evidence 149.191494 s.
});
test('Mobile reading text escapes evidence labels and includes all graph relationships',async()=>{
  const spec=structuredClone(source);spec.components[0].label='<script>label</script>';
  const html=readingSheet(spec,await readFile(root+'/docs/interactive/v2-sentinel.html','utf8'));
  assert.ok(html.includes('&lt;script&gt;label&lt;/script&gt;'));
  for(const e of spec.connections)assert.ok(html.includes('href="#node-'+e.to+'"'));
});


test('Current ECS atlas has five authenticated sources, no operational Sentinel and explicit DEV CD',async()=>{
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
    assert.equal(hash(await readFile(root+'/docs/interactive/'+d.output)),d.htmlSha256);
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
});
