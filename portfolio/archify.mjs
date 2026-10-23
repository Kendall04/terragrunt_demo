// Pinned originals, presentation-only copy, opaque iframe. No arbitrary ingestion.
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {archifyCatalog} from './archify-catalog.mjs';
import {adaptViewport,viewportStyle,viewportScript} from './archify-viewport.mjs';
const pins=JSON.parse(await readFile(new URL('./archify-pins.json',import.meta.url),'utf8'));
export const diagramPolicy="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none'; media-src 'none'; object-src 'none'; frame-src 'none'; worker-src 'none'; base-uri 'none'; form-action 'none'";
export function adaptArchify(bytes,expected){
 if(createHash('sha256').update(bytes).digest('hex')!==expected)throw new Error('Unreviewed Archify bytes');
 let html=bytes.toString('utf8');
 if(!html.includes('name="generator" content="archify 3.1.0"')||/<script[^>]+src=|<link[^>]+href=|<iframe|<object|<embed|<base\b|<form\b|\bon[a-z]+=|\b(?:fetch|eval)\s*\(|XMLHttpRequest|WebSocket|sendBeacon|serviceWorker/i.test(html))throw new Error('Unexpected active Archify resource');
 const evidence=/<script id="archify-source-evidence-data"[^>]*>[\s\S]*?<\/script>/;
 if(!evidence.test(html))throw new Error('Missing source evidence surface');
 html=html.replace(evidence,'<script id="archify-source-evidence-data" type="application/json">'+JSON.stringify({schemaVersion:1,verified:false,repository:null,referenceCount:0,nodes:{}})+'</script>');
 html=html.replace(/(<a\b[^>]*?)\s+href="[^"]*"/g,'$1 aria-disabled="true"');
 html=html.replace('<head>','<head><meta http-equiv="Content-Security-Policy" content="'+diagramPolicy+'"><meta name="referrer" content="no-referrer">');
 html=html.replace('<html lang="es"','<html lang="es" data-present="true"');
 html=html.replace('</head>','<style>'+viewportStyle+'#btn-export,#export-menu{display:none!important}</style></head>');
 html=html.replace('</body>','<script>'+viewportScript+'</script></body>');
 return adaptViewport(html);
}
export async function archifyPresentation(id){
 if(!archifyCatalog.some(item=>item.id===id))throw new Error('Unknown Archify diagram');
 return adaptArchify(await readFile(new URL('../docs/interactive/'+id+'.html',import.meta.url)),pins.originalSha256[id]);
}
