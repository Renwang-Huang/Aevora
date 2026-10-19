import {chromium,expect} from '@playwright/test';
import fs from 'node:fs/promises';import {createHash} from 'node:crypto';
const base=process.env.AEVORA_PRODUCT_URL||((process.env.AEVORA_BROWSER_URL || 'http://127.0.0.1:19064') + ''),out=process.env.AEVORA_BROWSER_OUTPUT;
if(!out)throw Error('Explicit evidence output required');await fs.mkdir(out,{recursive:true});
const checks=[],responses=[],errors=[],pending=[];let browser,context,page;const started=new Date().toISOString();
async function check(name,fn){try{const actual=await fn();checks.push({name,status:'PASS',actual:actual??null});}catch(e){checks.push({name,status:'FAIL',error:e.message});throw e;}}
async function ready(){await expect(page.locator('.case-heading .badge')).not.toHaveText('LOADING');await expect(page.locator('.content .state-box.danger')).toHaveCount(0);}
async function shot(name){await page.screenshot({path:out+'/'+name+'.png',fullPage:true});}
try{
 browser=await chromium.launch({headless:true});context=await browser.newContext({viewport:{width:1280,height:800}});await context.tracing.start({screenshots:true,snapshots:true,sources:true});page=await context.newPage();
 page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.url().includes('/api/'))pending.push((async()=>{const body=await r.body(),name='http-'+(responses.length+1)+'.json';responses.push({url:r.url(),status:r.status(),artifact:name,sha256:createHash('sha256').update(body).digest('hex')});await fs.writeFile(out+'/'+name,body);})());});
 await check('public_image_three_page_replay',async()=>{
  await page.goto(base+'/?page=activity&case=case-a&mode=REPLAY');await ready();await expect(page.locator('.event-mini')).toHaveCount(3);await shot('01-product-activity-replay');
  await page.getByRole('button',{name:'02 Experience Explorer',exact:true}).click();await expect(page.locator('#evidence-graph canvas').first()).toBeVisible();await page.locator('.node-list summary').click();await page.locator('.node-row').first().click();await expect(page.locator('#node-inspector')).toContainText('Selected evidence');await shot('02-product-explorer-replay');
  await page.getByRole('button',{name:'03 Governance Timeline',exact:true}).click();await expect(page.locator('.timeline-event')).not.toHaveCount(0);await shot('03-product-governance-replay');
 });
 await check('public_image_independent_proof',async()=>{await page.getByRole('button',{name:'Verify source',exact:true}).click();await expect(page.locator('dialog pre')).toContainText('PUBLIC');await page.getByRole('button',{name:'Close',exact:true}).click();});
 await check('empty_fresh_live_no_replay_fallback',async()=>{await page.goto(base+'/?page=explorer&case=case-b&mode=LIVE');await ready();await expect(page.locator('.case-heading .badge')).toHaveText('EMPTY');await expect(page.getByRole('heading',{name:'APPLY',exact:true})).toHaveCount(0);await shot('04-product-empty-live');});
 await check('actual_owner_channel_headers_no_invented_native_identity',async()=>{
  const response=await context.request.get(base+'/api/sessions?mode=LIVE&case=case-b');expect(response.status()).toBe(200);const v=await response.json();await fs.writeFile(out+'/actual-sessions.json',JSON.stringify(v,null,2)+'\n');
  const serialized=JSON.stringify(v);expect(serialized).toContain('fresh-user-sdk');expect(serialized).toContain('MCP_REQUESTS_OBSERVED');expect(serialized).toContain('resolve_experience');expect(serialized).toContain('propose_experience');return {actual_payload_sha256:createHash('sha256').update(serialized).digest('hex'),identity:'No native identity inferred from MCP owner log'};
 });
 await check('private_proof_denied',async()=>{await page.goto(base+'/?page=activity&case=case-a&mode=REPLAY&proof=private-manifest');await expect(page.locator('dialog')).toContainText('FORBIDDEN');await shot('05-product-private-proof-denied');await page.getByRole('button',{name:'Close',exact:true}).click();});
 await check('readonly_api_rejects_mutation',async()=>{const r=await context.request.post(base+'/api/review',{data:{candidate:'anything'}});expect(r.status()).toBe(403);return {http_status:r.status(),body:await r.json()};});
 await check('real_browser_disconnect_clears_view',async()=>{await page.goto(base+'/?page=activity&case=case-b&mode=LIVE');await ready();await context.setOffline(true);await page.getByRole('button',{name:'Refresh',exact:true}).click();await expect(page.locator('.case-heading .badge')).toHaveText('DISCONNECTED');await shot('06-product-browser-disconnected');await context.setOffline(false);await page.getByRole('button',{name:'Retry',exact:true}).click();await ready();});
 await check('no_browser_script_errors',async()=>{expect(errors).toEqual([]);});
}catch(e){await fs.writeFile(out+'/FAILURE.txt',e.stack+'\n');process.exitCode=1;if(page)await shot('failure').catch(()=>{});}
finally{await Promise.allSettled(pending);if(context)await context.tracing.stop({path:out+'/browser-trace.zip'});const result={status:process.exitCode?'FAIL':'PASS',checks,errors,responses,browser_version:browser?.version(),started_at:started,ended_at:new Date().toISOString(),source:'Actual public-only Docker image / separate Playwright Chromium / real new Volume / official SDK channel'};await fs.writeFile(out+'/RESULT.json',JSON.stringify(result,null,2)+'\n');if(browser)await browser.close();console.log(JSON.stringify({status:result.status,checks:checks.length,responses:responses.length}));}
