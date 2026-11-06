// Optional local visual QA. Uses an already installed browser/Playwright; installs nothing.
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
import path from 'node:path';
import {root,sha} from './readable.mjs';
if(!process.env.PLAYWRIGHT_MODULE||!process.env.CHROME_PATH)throw Error('Set PLAYWRIGHT_MODULE and CHROME_PATH to existing local installations');
const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href);
const dest=path.resolve(process.argv[2]??path.join(root,'logs/diagram-audit/captures'));
await mkdir(dest,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH});
const context=await browser.newContext(),receipt=[],requests=[],mobileDetails=[];
await context.route('**/*',r=>{if(new URL(r.request().url()).protocol==='file:')return r.continue();requests.push(r.request().url());return r.abort();});
const page=await context.newPage();
const manifest=JSON.parse(await readFile(path.join(root,'docs/interactive/GENERATION-V2.json'),'utf8'));
try {
  for(const item of manifest.diagrams)for(const reading of [false,true])for(const width of [1440,390]){
    const file=path.join(root,'docs/interactive',reading?'readable':'',item.id+'.html');
    await page.setViewportSize({width,height:1000});await page.goto(pathToFileURL(file).href);await page.waitForTimeout(150);
    const state=await page.evaluate(()=>({pageWidth:document.documentElement.scrollWidth,svgCount:document.querySelectorAll('svg').length,clippedText:[...document.querySelectorAll('article')].filter(e=>e.scrollWidth>e.clientWidth+1).length,viewBox:document.querySelector('svg').getAttribute('viewBox')}));
    if(state.pageWidth>width+1||state.clippedText)throw Error('Overflow: '+item.id+' '+width+' '+reading);
    const name=item.id+(reading?'-reading':'-official')+'-'+width+'.png';
    await page.screenshot({path:path.join(dest,name),fullPage:true});
    if(reading && width===390){
      await page.screenshot({path:path.join(dest,item.id+'-mobile-top.png'),fullPage:false});
      await page.locator('.nodes').scrollIntoViewIfNeeded();
      await page.screenshot({path:path.join(dest,item.id+'-mobile-text.png'),fullPage:false});
      for(const suffix of ['-mobile-top.png','-mobile-text.png'])mobileDetails.push({id:item.id,file:item.id+suffix,pngSha256:sha(await readFile(path.join(dest,item.id+suffix))),htmlSha256:sha(await readFile(file))});
    }
    if(reading){
      await page.getByRole('button',{name:'Vista completa'}).click();
      const fits=await page.locator('.drawing').evaluate(e=>e.scrollWidth<=e.parentElement.clientWidth);
      if(!fits)throw Error('Fit control failed: '+item.id);
      await page.getByRole('button',{name:'Ampliar 150%'}).click();
      if(await page.locator('.drawing').evaluate(e=>e.offsetWidth)<1010)throw Error('Zoom failed');
    }
    receipt.push({id:item.id,view:reading?'reading-sheet':'official',viewport:{width,height:1000},file:name,pngSha256:sha(await readFile(path.join(dest,name))),htmlSha256:sha(await readFile(file)),...state});
  }
  if(requests.length)throw Error('Unexpected external browser requests: '+requests.length);
  await writeFile(path.join(dest,'BROWSER-QA.json'),JSON.stringify({browser:await browser.version(),externalRequests:0,captures:receipt,mobileDetails},null,2)+'\n');
  console.log(JSON.stringify({captures:receipt.length,externalRequests:0}));
} finally {await browser.close();}
