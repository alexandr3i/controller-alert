const {chromium}=require('playwright');const assert=require('node:assert/strict');
(async()=>{const b=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});try{
 const p=await b.newPage();const errors=[];p.on('pageerror',e=>errors.push(e.message));await p.goto(process.env.APP_URL||'http://127.0.0.1:8020');
 await p.waitForFunction(()=>document.querySelector('#linesList').children.length>100);
 const numbers=await p.locator('#linesList .line-box').allTextContents();assert.deepEqual(numbers,[...numbers].sort((a,b)=>a.localeCompare(b,'ro',{numeric:true,sensitivity:'base'})));
 await p.locator('#lineSearch').fill('41');await p.locator('#linesList button').filter({has:p.locator('.line-box').filter({hasText:/^41$/})}).click();
 await p.waitForSelector('.departure-card');assert.match(await p.locator('#timetableStatus').innerText(),/GTFS/);
 assert(await p.locator('#journeyStop option').count()>5);assert(await p.locator('#variantSelect option').count()>=2);
 const before=await p.locator('#journeyStop').inputValue();await p.locator('#journeyStop').selectOption({index:3});await p.waitForSelector('.departure-card');assert.notEqual(before,await p.locator('#journeyStop').inputValue());
 await p.locator('#fullSchedule').check();await p.waitForSelector('.departure-card');assert(await p.locator('#scheduleDate').inputValue());
 await p.locator('#newReportButton').click();await p.locator('#reportForm button[type=submit]').click();await p.locator('.report').filter({has:p.locator('.delete')}).waitFor();const reportId=await p.locator('.report').filter({has:p.locator('.delete')}).getAttribute('data-report-id');await p.locator(`.control-pin[data-control-report="${reportId}"]`).waitFor();
 const q=await b.newPage();await q.goto(process.env.APP_URL||'http://127.0.0.1:8020');await q.locator(`.control-pin[data-control-report="${reportId}"]`).waitFor();assert.equal(await q.locator('.delete').count(),0);
 await p.locator('.delete').click();await p.locator(`.control-pin[data-control-report="${reportId}"]`).waitFor({state:'detached'});
 await p.setViewportSize({width:390,height:844});assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await p.screenshot({path:'/tmp/pelinie-journey-mobile.png',fullPage:true});
 await p.setViewportSize({width:1440,height:1000});await p.screenshot({path:'/tmp/pelinie-journey-desktop.png',fullPage:true});assert.deepEqual(errors,[]);
 console.log('PASS numeric route order, stop timetable, all-day schedule, variants, shared report pins/deletion and responsive layout');
}finally{await b.close()}})().catch(e=>{console.error(e);process.exit(1)});
