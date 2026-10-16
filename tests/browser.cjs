// Optional integration check: npm install --prefix /tmp/pelinie-browser playwright
// NODE_PATH=/tmp/pelinie-browser/node_modules node tests/browser.cjs
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fixture={version:1,source:'SYNTHETIC TEST DATA, NOT OFFICIAL',importedAt:'2026-10-16T12:00:00Z',lines:[{id:'r1',number:'41',label:'Test route',type:'tram',stops:['A','B'],coordinates:[[44.43,26.1],[44.44,26.11]],reverseStops:['C','A'],reverseCoordinates:[[44.45,26.12],[44.43,26.1]]}]};
(async()=>{
const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox']});
try {
const context=await browser.newContext();const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto('http://127.0.0.1:8000');await page.waitForSelector('#linesList button');
await page.locator('#transitFile').setInputFiles({name:'fixture.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(fixture))});
assert.match(await page.locator('#dataStatus').innerText(),/SYNTHETIC/);assert.equal(await page.locator('#linesList button').count(),1);
assert.equal(await page.locator('.leaflet-interactive').count(),3);assert.match(await page.locator('#directionText').innerText(),/A → B/);
await page.locator('#reverseButton').click();assert.match(await page.locator('#directionText').innerText(),/C → A/);
await page.locator('#newReportButton').click();assert.equal(await page.locator('#formStop option').first().innerText(),'C');await page.locator('#reportForm button[type=submit]').click();assert.equal(await page.locator('.report-origin.me').count(),1);
await page.locator('#demoDataButton').click();assert.equal(await page.locator('.report-origin.me').count(),0);
await page.locator('#transitFile').setInputFiles({name:'bad.json',mimeType:'application/json',buffer:Buffer.from('{}')});assert.match(await page.locator('#dataStatus').innerText(),/nereușit/);assert.equal(await page.locator('#linesList button').count(),5);
await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);
console.log('PASS imported route rendering, actual return stops, dataset isolation, invalid import, mobile and browser errors');
if(process.env.COMMUNITY_URL){
 const a=await browser.newContext(),b=await browser.newContext();const p=await a.newPage(),q=await b.newPage();
 await Promise.all([p.goto(process.env.COMMUNITY_URL),q.goto(process.env.COMMUNITY_URL)]);await p.waitForFunction(()=>document.querySelector('#modeStatus').textContent.includes('comunitare'));await q.waitForFunction(()=>document.querySelector('#modeStatus').textContent.includes('comunitare'));
 await p.locator('#newReportButton').click();await p.locator('#reportForm button[type=submit]').click();await p.waitForSelector('.report');await q.reload();await q.waitForSelector('.report');assert.match(await q.locator('.report-origin').innerText(),/COMUNITATE/);assert.equal(await q.locator('.delete').count(),0);
 await q.locator('.report button[aria-pressed]').click();await q.waitForFunction(()=>document.querySelector('.report button[aria-pressed]').getAttribute('aria-pressed')==='true');await p.reload();await p.waitForSelector('.delete');assert.match(await p.locator('.report button[aria-pressed]').innerText(),/1/);await p.locator('.delete').click();await p.waitForFunction(()=>document.querySelectorAll('.report').length===0);
 console.log('PASS two independent sessions share reports, vote, enforce deletion ownership');await a.close();await b.close();
}
}finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
