// Requires Playwright, Chromium, and a static server on 127.0.0.1:8000.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox']});
 try {
  const page=await browser.newPage(), errors=[];page.on('pageerror',e=>errors.push(e.message));
  const now=Math.floor(Date.now()/1000);
  await page.clock.install({time:new Date(now*1000)});
  const line={id:'r1',number:'41',label:'TEST ONLY',type:'bus',agencyId:'1',routeType:3,directionIds:['0','1'],stops:['A','B'],stopIds:['s1','s2'],coordinates:[[44.43,26.1],[44.44,26.11]]};
  const catalog={version:1,source:'SYNTHETIC TEST, NOT TPBI',importedAt:new Date(now*1000).toISOString(),lines:[line]};
  const base={timestamp:now,status:'fresh',error:null,receivedAt:now,attemptedAt:now,rejected:0,items:[]};
  const snapshot={enabled:true,mode:'live',generatedAt:now,pollSeconds:30,staleSeconds:180,feeds:{
   vehiclePositions:{...base,items:[{id:'v1',routeId:'r1',headsign:'B',latitude:44.43,longitude:26.1,timestamp:now-5,stale:false},{id:'v2',routeId:'r1',headsign:'B',latitude:44.44,longitude:26.11,timestamp:now-300,stale:true}]},
   tripUpdates:{...base,items:[{id:'t1',routeId:'r1',direction:'0',headsign:'B',timestamp:now,relationship:'SCHEDULED',stale:false,stops:[{stopId:'s1',stopName:'A',arrival:now+120,departure:null,delay:60,uncertainty:0,relationship:'SCHEDULED'},{stopId:'s2',stopName:'SHOULD NOT APPEAR',arrival:now+180,relationship:'NO_DATA'}]}]},
   serviceAlerts:{...base,items:[{id:'a1',header:'Stație mutată <img src=x onerror=alert(1)>',description:'Date sintetice',periods:[],selectors:[{routeId:'r1',agencyId:'1'}]},{id:'a2',header:'OTHER ROUTE',description:'Hidden',periods:[],selectors:[{routeId:'r2'}]}]}
  }};
  let offline=false,requests=0;
  await page.route('**/api/catalog',r=>r.fulfill({json:catalog}));
  await page.route('**/api/reports',r=>r.fulfill({json:[]}));
  await page.route('**/api/realtime',r=>{requests++;return offline?r.abort():r.fulfill({json:snapshot})});
  await page.goto('http://127.0.0.1:8000');await page.waitForFunction(()=>document.querySelector('#liveSummary').textContent.includes('2 vehicule afișate'));
  assert.match(await page.locator('#liveSummary').innerText(),/1 cu poziție recentă/);
  assert.equal(await page.locator('.leaflet-interactive[fill="#4189ff"]').count(),1);
  assert.equal(await page.locator('.leaflet-interactive[fill="#b4a17c"]').count(),1);
  assert.match(await page.locator('#liveArrivals').innerText(),/A → B/);
  assert(!((await page.locator('#liveArrivals').innerText()).includes('SHOULD NOT APPEAR')));
  assert.equal(await page.locator('#liveAlerts article').count(),1);
  assert.equal(await page.locator('#liveAlerts img').count(),0);
  offline=true;await page.clock.runFor(30000);
  await page.waitForFunction(()=>document.querySelector('#liveSummary').textContent.includes('pierdută'));
  assert.equal(await page.locator('.leaflet-interactive[fill="#4189ff"]').count(),0);
  assert.match(await page.locator('#liveArrivals').innerText(),/nu sunt disponibile/);
  assert.equal(requests,2);
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.deepEqual(errors,[]);console.log('PASS realtime UI: recent/stale markers, predictions, scoped alerts, safe text, offline state, polling and mobile layout');
  if(process.env.SNAPSHOT_URL){
   const replay=await browser.newPage();await replay.goto(process.env.SNAPSHOT_URL);await replay.waitForFunction(()=>document.querySelector('#liveSummary').textContent.includes('CAPTURĂ ÎNCĂRCATĂ'));
   assert.match(await replay.locator('#liveSummary').innerText(),/767 vehicule/);
   assert.equal(await replay.locator('.leaflet-interactive[fill="#4189ff"]').count(),0);
   assert.equal(await replay.locator('.leaflet-interactive[fill="#b4a17c"]').count(),767);
   await replay.screenshot({path:'/tmp/pelinie-realtime-snapshot.png',fullPage:true});
   console.log('PASS uploaded TPBI snapshot: 767 historic vehicles, no live markers');
  }
  if(process.env.LIVE_URL){
   const live=await browser.newPage();const liveErrors=[];live.on('pageerror',e=>liveErrors.push(e.message));await live.goto(process.env.LIVE_URL);
   await live.waitForSelector('.leaflet-interactive[fill="#4189ff"]',{state:'attached'});
   assert.match(await live.locator('#liveFeeds').innerText(),/Recent/);
   const api=await (await live.request.get(process.env.LIVE_URL+'/api/realtime')).json();
   assert.equal(api.mode,'live');assert.equal(api.feeds.vehiclePositions.status,'fresh');
   assert(api.feeds.vehiclePositions.items.length>0);assert.equal(api.feeds.tripUpdates.status,'fresh');assert.equal(api.feeds.serviceAlerts.status,'fresh');
   await live.locator('#lineSearch').fill('41');await live.locator('#linesList button').filter({has:live.locator('.line-box').filter({hasText:/^41$/})}).click();
   await live.locator('#allVehicles').uncheck();
   assert.match(await live.locator('#mapStatus').innerText(),/linia 41/);
   assert.deepEqual(liveErrors,[]);
   await live.screenshot({path:'/tmp/pelinie-realtime-live.png',fullPage:true});
   console.log('PASS actual TPBI live source: fresh vehicles, updates and alerts; map filtered to line 41');
  }
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
