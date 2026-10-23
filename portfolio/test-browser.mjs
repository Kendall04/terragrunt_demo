import assert from 'node:assert/strict';
import {mkdir,writeFile,readdir} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {createServer} from './server.mjs';
const destination=process.env.UI_EVIDENCE_DIRECTORY,dependency=process.env.PLAYWRIGHT_MODULE,chrome=process.env.CHROME_EXECUTABLE;
assert(destination&&dependency&&chrome,'Explicit approved dependency, Chrome and owned evidence paths required');
await mkdir(destination,{recursive:true});assert.equal((await readdir(destination)).length,0,'Preserve prior evidence');
const profile=path.join(destination,'temporary-profile-root');await mkdir(profile);process.env.TEMP=profile;process.env.TMP=profile;
const {chromium}=await import(pathToFileURL(dependency));const server=createServer();await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const base=`http://127.0.0.1:${server.address().port}`;
let browser;const errors=[],external=[],checks=[];const receipt={BaseUrl:base,SyntheticOnly:true,PersonalSessionsUsed:false,ExternalRequests:external,Checks:checks,ForceCleanup:false,BrowserClosed:false,ServerClosed:false};
function check(name){checks.push(name);}
try{
 browser=await chromium.launch({headless:true,executablePath:chrome});receipt.BrowserVersion=browser.version();
 const context=await browser.newContext({viewport:{width:1440,height:1080},deviceScaleFactor:1});await context.route('**/*',route=>{if(new URL(route.request().url()).origin!==base){external.push(route.request().url());return route.abort();}return route.continue();});
 const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));page.on('console',msg=>{if(msg.type()==='error')errors.push(msg.text());});await page.goto(base);await page.locator('#messages li').first().waitFor();
 assert.match(await page.locator('.mode').innerText(),/DEMO LOCAL/);assert.match(await page.locator('.hero-aside').innerText(),/no cifra/);assert.equal(await page.locator('#messages li').count(),2);check('DEMO and no-backend labels with synthetic seed');
 await page.locator('#message-form button').click();assert.match(await page.locator('#form-error').innerText(),/Escribe/);check('Empty input validation');
 const text='<img src=x onerror=window.injected=true> mensaje sintético';await page.locator('#message').fill(text);await page.locator('#message-form button').click();assert.equal(await page.locator('#messages li').count(),3);assert.match(await page.locator('#messages li').first().innerText(),/onerror/);assert.equal(await page.evaluate(()=>window.injected),undefined);assert.equal(await page.locator('#messages img').count(),0);check('Memory-only submit and literal XSS handling');
 await page.locator('#reset').click();assert.equal(await page.locator('#messages li').count(),2);check('Synthetic reset');
 await page.screenshot({path:path.join(destination,'desktop-product.png'),fullPage:true});
 await page.locator('nav [data-view=architecture]').click();await page.locator('[data-node=kms]').click();assert.equal(await page.locator('#node-title').innerText(),'AWS KMS');assert.match(await page.locator('#node-limit').innerText(),/no cifra/);assert.match(await page.locator('#flow').innerText(),/API ↔ KMS/);check('Architecture inspector and actual dependency flow');
 await page.locator('[data-node=ecs]').focus();await page.keyboard.press('Enter');assert.equal(await page.locator('#node-title').innerText(),'API en Fargate');check('Keyboard architecture navigation');
 await page.locator('[data-topology=az6]').click();assert.equal(await page.locator('[data-node=ecs]').count(),0);assert.match(await page.locator('#flow').innerText(),/Origen → S3/);assert.match(await page.locator('#diagram-note').innerText(),/No creó ECS ni ALB/);await page.locator('[data-node=target]').click();assert.match(await page.locator('#node-limit').innerText(),/Destino preparado/);check('Separate V1 and az6 historical topology/limits');
 await page.screenshot({path:path.join(destination,'desktop-architecture.png'),fullPage:true});
 const source=await context.request.get(base+'/source/architecture');assert.equal(source.status(),200);assert.match(await source.text(),/Architecture and current contracts/);const denied=await context.request.get(base+'/source/unknown');assert.equal(denied.status(),404);const mutation=await context.request.post(base+'/');assert.equal(mutation.status(),405);assert.match((await context.request.get(base)).headers()['content-security-policy'],/connect-src 'none'/);check('Read-only allowlisted source routes and CSP');
 await page.locator('nav [data-view=evidence]').click();assert.match(await page.locator('#evidence').innerText(),/142,63/);assert.match(await page.locator('#evidence').innerText(),/sin reparación manual/);assert.match(await page.locator('#evidence').innerText(),/correo real/);check('Historical proof and pending integrations remain explicit');
 await page.setViewportSize({width:390,height:844});await page.locator('nav [data-view=demo]').click();assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));await page.screenshot({path:path.join(destination,'mobile-product.png'),fullPage:true});check('Mobile product layout without horizontal overflow');
 await page.locator('nav [data-view=architecture]').click();assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));await page.screenshot({path:path.join(destination,'mobile-architecture.png'),fullPage:true});check('Mobile architecture layout without horizontal overflow');
 assert.deepEqual(errors,[]);assert.deepEqual(external,[]);check('No browser errors or external requests');receipt.Status='PASS';
}catch(error){receipt.Status='FAILED';receipt.Error=error.message;process.exitCode=1;}
finally{if(browser){await browser.close();receipt.BrowserClosed=true;}await new Promise(resolve=>server.close(resolve));receipt.ServerClosed=true;receipt.ConsoleErrors=errors;receipt.FinishedUtc=new Date().toISOString();await writeFile(path.join(destination,'browser-receipt.json'),JSON.stringify(receipt,null,2)+'\n');console.log(JSON.stringify(receipt,null,2));}
