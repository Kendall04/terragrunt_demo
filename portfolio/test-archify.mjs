import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {adaptArchify} from './archify.mjs';
const raw=await readFile(new URL('../docs/interactive/ecs-platform.html',import.meta.url));
test('presentation refuses changed bytes and active resource mutants',()=>{
 assert.throws(()=>adaptArchify(raw,'0'.repeat(64)),/Unreviewed/);
 for(const suffix of ['<script src="https://example.invalid/x.js"></script>',"<script>fetch('https://example.invalid')</script>",'<iframe src="/other"></iframe>']){
  const changed=Buffer.concat([raw,Buffer.from(suffix)]);
  assert.throws(()=>adaptArchify(changed,createHash('sha256').update(changed).digest('hex')),/Unexpected active/);
 }
});
test('current host preserves focus, announcements, opaque frames and current-only navigation',async()=>{
 const app=await readFile(new URL('./product/app.mjs',import.meta.url),'utf8');
 const html=await readFile(new URL('./product/index.html',import.meta.url),'utf8');
 assert.match(app,/allow-scripts/);assert.doesNotMatch(app,/allow-same-origin|allow-top-navigation|Historia · V1/);
 assert.match(html,/skip/);assert.match(html,/aria-live/);
});
