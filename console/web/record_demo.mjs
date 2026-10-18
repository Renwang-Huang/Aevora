import {chromium,expect} from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
const out=process.env.AEVORA_BROWSER_OUTPUT;
const base=process.env.AEVORA_BROWSER_URL||'http://127.0.0.1:19064';
if(!out)throw Error('Explicit external AEVORA_BROWSER_OUTPUT required');
await fs.mkdir(out,{recursive:true});
const record=process.env.AEVORA_RECORD_VIDEO==='1';const dwell=record?15000:0;
const checks=[],errors=[],responses=[],actions=[];let browser,context,page;const start=Date.now();
function mark(action){actions.push({seconds:(Date.now()-start)/1000,action});}
async function check(name,fn){try{await fn();checks.push({name,status:'PASS'});}catch(e){checks.push({name,status:'FAIL',error:e.message});throw e;}}
async function shot(name){await page.screenshot({path:path.join(out,name+'.png'),fullPage:true});}
async function waitVerdict(value){await expect(page.locator('.verdict')).toHaveText(value);}
async function pause(action){mark(action);if(dwell)await page.waitForTimeout(dwell);}
try{
 browser=await chromium.launch({headless:true});context=await browser.newContext({viewport:{width:1440,height:1000},...(record?{recordVideo:{dir:out,size:{width:1440,height:1000}}}:{})});
 await context.tracing.start({screenshots:true,snapshots:true,sources:true});page=await context.newPage();
 page.on('pageerror',e=>errors.push({type:'pageerror',message:e.message}));
 page.on('console',m=>{if(m.type()==='error'&&!/favicon|Failed to load resource.*404|ERR_INTERNET_DISCONNECTED/.test(m.text()))errors.push({type:'console',message:m.text()});});
 page.on('response',r=>{if(r.url().includes('/api/journey'))responses.push({url:r.url(),status:r.status()});});
 await check('actual_live_threads_apply',async()=>{await page.goto(base+'/journey.html');await waitVerdict('APPLY');await expect(page.locator('h1')).toHaveText('Know when to reuse experience. See why.');await expect(page.locator('main')).toContainText('LIVE_SYNTHETIC_DEMO');await shot('01-live-apply');await pause('Shared threads: actual FalkorDB APPLY; synthetic source labelled.');});
 await check('actual_live_workers_abstain',async()=>{await page.getByRole('button',{name:'Independent workers',exact:true}).click();await waitVerdict('ABSTAIN');await shot('02-workers-abstain');await pause('Independent processes violate the lock premise: ABSTAIN.');});
 await check('actual_unknown_premise_verify',async()=>{await page.getByRole('button',{name:'Unknown premise',exact:true}).click();await waitVerdict('VERIFY');await shot('03-unknown-verify');await pause('Unknown premise: VERIFY, not an assumed match.');});
 await check('actual_graph_explorer',async()=>{await page.getByRole('button',{name:'Shared threads',exact:true}).click();await waitVerdict('APPLY');await page.getByRole('button',{name:'Experience Explorer',exact:true}).click();await expect(page.locator('#graph canvas').first()).toBeVisible();await shot('04-graph-witness');await pause('Actual Graph v2 Witness: rule, premise, evidence, Outcome and Authority.');await page.getByText('Inspect complete visible graph records',{exact:true}).click();await expect(page.locator('details pre')).toContainText('SUPPORTED_BY');await shot('05-visible-records');await pause('Inspect the actual evidence records; no relationships are invented by layout.');});
 await check('actual_withdrawal_changes_verdict',async()=>{await page.getByRole('button',{name:'Governance Timeline',exact:true}).click();await page.getByRole('button',{name:'After withdrawal',exact:true}).click();await waitVerdict('ABSTAIN');await shot('06-withdrawal');await pause('Separate owned graph state: a real GovernanceEvent withdraws the revision.');await page.getByRole('button',{name:'Before withdrawal',exact:true}).click();await waitVerdict('APPLY');});
 await check('historical_core_and_agent_choices_separate',async()=>{const card=page.locator('section').filter({has:page.getByRole('heading',{name:'Historical verified evidence · G23',exact:true})});await card.scrollIntoViewIfNeeded();await expect(card).toContainText('CORE: APPLY');await expect(card).toContainText('AGENT: VERIFY');await expect(card).toContainText('28/28 PASS');await expect(card).toContainText('REPLAY');await shot('07-historical-scope');await pause('Historical sanitized G23 records: Core APPLY; Agent VERIFY; original Oracle28/28.');await expect(card).toContainText('Host-approved follow-up');await pause('Trusted feedback is separate from natural proposal publication; causal benefit UNKNOWN.');});
 await check('public_http_boundaries',async()=>{expect((await page.request.post(base+'/api/journey')).status()).toBe(403);expect((await page.request.get(base+'/api/journey?graph=other')).status()).toBe(400);expect((await page.request.get(base+'/api/journey?context=threads&context=workers')).status()).toBe(400);});
 await check('disconnect_clears_live_data_without_replay',async()=>{await page.getByRole('button',{name:'Activity & Decisions',exact:true}).click();await waitVerdict('APPLY');await context.setOffline(true);await page.getByRole('button',{name:'Refresh live graph',exact:true}).click();await expect(page.locator('.notice.error')).toContainText('No replay fallback');await expect(page.locator('.verdict')).toHaveCount(0);await shot('08-no-fallback');await pause('Actual browser offline: live data clears; historical data is not used as fallback.');await context.setOffline(false);await page.getByRole('button',{name:'Refresh live graph',exact:true}).click();await waitVerdict('APPLY');});
 await check('desktop_and_mobile_layout',async()=>{for(const [width,height] of [[1440,1000],[390,844]]){await page.setViewportSize({width,height});expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width+1);await shot('09-layout-'+width);}await page.setViewportSize({width:1440,height:1000});});
 await check('no_javascript_errors',async()=>expect(errors).toEqual([]));
}catch(e){process.exitCode=1;await fs.writeFile(path.join(out,'FAILURE.txt'),e.stack+'\n');if(page)await shot('failure').catch(()=>{});}
finally{
 if(context)await context.tracing.stop({path:path.join(out,'browser-trace.zip')});
 const video=page?.video();if(context)await context.close();let videoPath=null;if(video)videoPath=await video.path();
 if(browser)await browser.close();const result={status:process.exitCode?'FAIL':'PASS',checks,errors,responses,actions,video:videoPath,model_execution:false,mechanism:'Actual Chromium/HTTP/FalkorDB; no request mocking',elapsed_seconds:(Date.now()-start)/1000};
 await fs.writeFile(path.join(out,'RESULT.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({status:result.status,checks:checks.length,errors:errors.length,video:videoPath}));
}
