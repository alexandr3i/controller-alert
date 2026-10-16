(function(root){
'use strict';
function create(options){
 const $=id=>document.getElementById(id);
 let key='',busy=false,rerun=false,epoch=0,rows=[],generated=0,received=0,online=false;
 const time=seconds=>new Date(seconds*1000).toLocaleTimeString('ro-RO',{timeZone:'Europe/Bucharest',hour:'2-digit',minute:'2-digit'});
 $('scheduleDate').value=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Bucharest',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 function render(){
  const list=$('timetableList');list.replaceChildren();
  const now=generated+(Date.now()-received)/1000;
  for(const row of rows){
   if(!$('fullSchedule').checked&&row.expectedTime<now-60)continue;
   const card=document.createElement('article');card.className='departure-card';card.dataset.status=row.status;
   const at=document.createElement('strong');at.textContent=time(row.expectedTime);
   const details=document.createElement('span');details.textContent=row.headsign||'Cursă de transport';
   const label=document.createElement('span');label.className='departure-state';
   const isRecent=online&&row.status==='live'&&now-row.updatedAt<=180&&now-row.updatedAt>=-120;
   label.textContent=row.status==='cancelled'?'Anulată':row.status==='skipped'?'Nu oprește':isRecent?'LIVE · '+Math.max(0,Math.ceil((row.expectedTime-now)/60))+' min':row.status==='live'?'Estimare veche':'Planificat';
   if(row.status==='live'&&!isRecent)card.dataset.status='stale';
   if(row.status==='live'){const small=document.createElement('small');small.textContent='Orar '+time(row.plannedTime);details.append(document.createElement('br'),small);}
   card.append(at,details,label);list.append(card);
  }
  if(!list.childNodes.length){const p=document.createElement('p');p.textContent=key?'Nu sunt plecări pentru stația și perioada selectate.':'Selectează o stație pentru orar și sosiri.';list.append(p);}
 }
 async function refresh(){
  if(busy){rerun=true;return;}
  if(!options.isOnline()||!$('journeyStop').value){if(!options.isOnline())$('timetableStatus').textContent='Orarul complet necesită backend-ul Render. Harta și traseele rămân disponibile.';return;}
  busy=true;const token=epoch;
  const query=new URLSearchParams({line:options.getLine().id,direction:options.getDirection()||'0',stop:$('journeyStop').value});
  if($('fullSchedule').checked)query.set('date',$('scheduleDate').value);
  try{
   const response=await fetch('api/timetable?'+query,{cache:'no-store',signal:AbortSignal.timeout(15000)});if(!response.ok)throw Error();
   const result=await response.json();if(token!==epoch)return;
   rows=result.departures||[];generated=result.generatedAt||Date.now()/1000;received=Date.now();online=true;
   $('timetableStatus').textContent=result.enabled?(result.realtimeAvailable?'Orar GTFS + estimări recente TPBI. Orele sunt în fusul Bucureștiului.':'Orar planificat GTFS. Estimările live nu sunt disponibile acum.'):'Orarul nu este configurat pe acest server.';
   render();
  }catch{if(token===epoch){online=false;$('timetableStatus').textContent='Conexiune pierdută. Orele afișate sunt din ultima preluare; nu reprezintă estimări live actuale.';render();}}
  finally{busy=false;if(rerun){rerun=false;refresh();}}
 }
 function update(){
  const line=options.getLine(),direction=options.getDirection();
  const next=line.id+'|'+direction+'|'+(line.activeVariant||'')+'|'+(line.stopIds||[]).join(',')+'|'+options.isOnline();
  if(next!==key){
   key=next;epoch++;rows=[];const select=$('journeyStop');const previous=select.value;select.replaceChildren();
   const reverse=options.isReversed();const ids=reverse?line.reverseStopIds:line.stopIds,names=reverse?line.reverseStops:line.stops;
   (ids||[]).forEach((id,i)=>{const option=document.createElement('option');option.value=id;option.textContent=names[i];select.append(option)});
   if([...select.options].some(o=>o.value===previous))select.value=previous;
   $('timetableStatus').textContent='Se încarcă orarul stației…';render();refresh();
  }
 }
 function choose(stopId){if([...$('journeyStop').options].some(o=>o.value===stopId)){$('journeyStop').value=stopId;epoch++;rows=[];render();refresh();$('timetableSection').scrollIntoView({behavior:'smooth',block:'nearest'});}}
 for(const id of ['journeyStop','fullSchedule','scheduleDate'])$(id).addEventListener('change',()=>{epoch++;rows=[];render();refresh();});
 setInterval(refresh,30000);setInterval(render,15000);
 return{update,choose,refresh};
}
root.Journey={create};
})(window);
