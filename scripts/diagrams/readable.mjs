// Documentation-only reading sheets. The official Archify HTML is never edited.
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
export const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const esc = s => String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
export function extract(html) {
  const svgs = [...html.matchAll(/<svg\b[^>]*viewBox="[^"]+"[\s\S]*?<\/svg>/g)];
  if (svgs.length !== 1 || /<script|<foreignObject|\son\w+=/i.test(svgs[0][0])) throw Error('Expected one inert official SVG');
  const css = html.match(/<style>([\s\S]*?)<\/style>/)?.[1];
  if (!css || /@import|url\(\s*["']?https?:/i.test(css)) throw Error('External CSS is not admitted');
  return {svg:svgs[0][0], css};
}
export function readingSheet(spec, raw) {
  const {svg,css}=extract(raw), id=path.basename(spec.meta.output,'.html');
  const nodes=spec.components ?? spec.events;
  const names=new Map(nodes.map(n=>[n.id,n.label??n.title]));
  const cite=s=>{
    const url=spec.meta.repository.url.replace(/\.git$/,'')+'/blob/'+spec.meta.repository.revision+'/'+s.path+'#L'+s.line;
    return `<a href="${esc(url)}">${esc(s.path)}:${s.line}${s.end_line?'–'+s.end_line:''}</a>`;
  };
  const nodeRows=nodes.map(n=>`<article id="node-${esc(n.id)}"><h3>${esc(n.label??n.title)}</h3><p class="status">${esc(n.tag??'DEMOSTRADO · EVENTO FECHADO')}</p><p>${esc(n.sublabel??n.detail)}</p>${n.at?`<p><time>${esc(n.at)}</time></p>`:''}<ul>${(spec.connections??[]).filter(e=>e.from===n.id).map(e=>`<li>${esc(e.label)} → <a href="#node-${esc(e.to)}">${esc(names.get(e.to))}</a></li>`).join('')}</ul><details><summary>Fuentes en el commit revisado</summary><ul>${n.sources.map(s=>`<li>${cite(s)}</li>`).join('')}</ul></details></article>`).join('');
  const cards=spec.cards.map(c=>`<article><h3>${esc(c.title)}</h3><ul>${c.items.map(i=>`<li>${esc(i)}</li>`).join('')}</ul></article>`).join('');
  return `<!doctype html>
<html lang="es" data-theme="light" data-motion="still"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="generator" content="terragrunt_demo reading sheet v1; original SVG by Archify 3.1.0"><meta name="archify-html-sha256" content="${sha(raw)}"><meta name="archify-svg-sha256" content="${sha(svg)}"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; font-src data:; img-src data:; base-uri 'none'; form-action 'none'"><title>${esc(spec.meta.title)}</title><style>${css}</style><style>
body{display:block;margin:0;padding:24px;background:#f4f6fa;color:#172b40;font:16px/1.55 system-ui,sans-serif;min-height:100vh}main{max-width:1320px;margin:auto}h1{font-size:clamp(24px,3vw,36px);line-height:1.2;margin:12px 0}h2{font-size:23px;margin:30px 0 16px}h3{font-size:17px;margin:0 0 10px}a{color:#165b94;text-decoration:underline;overflow-wrap:anywhere}a:focus-visible,button:focus-visible,summary:focus-visible,figure:focus-visible{outline:3px solid #d08000;outline-offset:4px}.eyebrow,.status{font-weight:650;color:#486075;font-size:12px;letter-spacing:.04em}.toolbar{display:flex;flex-wrap:wrap;gap:8px;position:static;margin:16px 0}.toolbar button{font:inherit;border:1px solid #9cadbd;border-radius:5px;background:white;color:#172b40;padding:8px 15px;cursor:pointer}figure{display:block;overflow:auto;max-width:100%;margin:0;border:1px solid #bccbda;border-radius:10px;background:white;padding:12px;max-height:none}.drawing{width:100%;min-width:900px}.drawing>svg{width:100%;min-width:0;transform:none!important}.cards,.nodes{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:16px}article{min-width:0;background:white;border:1px solid #d4dce5;border-radius:8px;padding:20px;overflow-wrap:anywhere}article ul{padding-left:20px;margin:10px 0}article li+li{margin-top:8px}details{margin-top:14px;font-size:13px}summary{cursor:pointer;font-weight:600}.note{max-width:90ch;color:#42586d}footer{font-size:13px;margin-top:32px;border-top:1px solid #ccd6df;padding-top:16px}@media(min-width:1000px){.drawing{min-width:0}}@media(max-width:600px){body{padding:16px}figure{padding:8px}.drawing{min-width:1010px}article{padding:16px}}
</style></head><body><main><header><p class="eyebrow">ECS V2 / AWS DEV / SNAPSHOT 6 NOV 2026</p><h1>${esc(spec.meta.title)}</h1><p class="note">Hoja de lectura del repositorio. SVG íntegro generado por Archify; presentación y relaciones textuales generadas por <code>scripts/diagrams/readable.mjs</code>. No es un nuevo visor del portafolio ni una comprobación de salud en tiempo real.</p><p><a href="../${esc(id)}.html">Abrir Archify oficial interactivo</a> · <a href="../source/${esc(id)}.json">Fuente JSON</a> · <a href="../V2-INDEX.md">Índice y límites</a></p></header><div class="toolbar" aria-label="Escala del diagrama"><button data-scale="fit">Vista completa</button><button data-scale="1">Tamaño legible</button><button data-scale="1.5">Ampliar 150%</button></div><p class="note">En móvil: deslice el diagrama a tamaño legible. Todos los componentes, relaciones y fuentes también están disponibles como texto debajo; “Vista completa” prioriza orientación, no lectura del detalle.</p><figure tabindex="0" aria-label="Diagrama desplazable; relaciones completas en texto a continuación"><div class="drawing">${svg}</div></figure><h2>Alcance, evidencia y limitaciones</h2><section class="cards">${cards}</section><h2>${spec.events?'Cronología y fuentes':'Componentes, relaciones y fuentes'}</h2><section class="nodes">${nodeRows}</section><footer>Fuente: ${esc(spec.meta.repository.revision)}. Esta hoja no ejecuta solicitudes AWS, no carga recursos externos y no modifica el SVG original. Los cinco diagramas históricos conservan sus bytes.</footer></main><script>
const drawing=document.querySelector('.drawing');const intrinsic=drawing.querySelector('svg').viewBox.baseVal.width;for(const button of document.querySelectorAll('[data-scale]'))button.addEventListener('click',()=>{const scale=button.dataset.scale;drawing.style.minWidth='0';drawing.style.width=scale==='fit'?'100%':Math.max(1010,intrinsic)*Number(scale)+'px';});
</script></body></html>\n`;
}
export async function generate(check=false) {
  const manifest=JSON.parse(await readFile(path.join(root,'docs/interactive/GENERATION-V2.json'),'utf8'));
  await mkdir(path.join(root,'docs/interactive/readable'),{recursive:true});
  for(const item of manifest.diagrams){
    const spec=JSON.parse(await readFile(path.join(root,item.source),'utf8'));
    const raw=await readFile(path.join(root,item.output),'utf8');
    if(sha(raw)!==item.htmlSha256)throw Error('Official HTML hash mismatch: '+item.id);
    const content=readingSheet(spec,raw), dest=path.join(root,'docs/interactive/readable',item.id+'.html');
    if(check){if(await readFile(dest,'utf8')!==content)throw Error('Reading sheet differs: '+item.id);}
    else await writeFile(dest,content);
  }
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))await generate(process.argv.includes('--check'));
