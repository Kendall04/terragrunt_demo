import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {root,extract,readingSheet} from './readable.mjs';
import {validateGraph,verify} from './verify.mjs';
const source=JSON.parse(await readFile(root+'/docs/interactive/source/ecs-platform.json','utf8'));
test('Five current diagrams, original SVGs, citations and source bytes verify offline',async()=>{assert.equal((await verify()).diagrams,5);});
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
test('Mobile reading text escapes evidence labels and includes all graph relationships',async()=>{
  const spec=structuredClone(source);spec.components[0].label='<script>label</script>';
  const html=readingSheet(spec,await readFile(root+'/docs/interactive/ecs-platform.html','utf8'));
  assert.ok(html.includes('&lt;script&gt;label&lt;/script&gt;'));
  for(const e of spec.connections)assert.ok(html.includes('href="#node-'+e.to+'"'));
});
