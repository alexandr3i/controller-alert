/* Same-origin JSON API; TPBI protobuf requests are centralized in the backend. */
(function (root) {
  'use strict';
  function fresh(timestamp, now, limit=180) {
    return Number.isFinite(timestamp) && timestamp > 0 && now-timestamp >= -120 && now-timestamp <= limit;
  }
  function selectorMatches(selector, line, direction) {
    if (selector.routeId && selector.routeId !== line.id) return false;
    // A trip/stop-specific selector must not become a global alert when metadata is absent.
    if (selector.tripId && !selector.routeId) return false;
    if (selector.agencyId && selector.agencyId !== line.agencyId) return false;
    if (selector.routeType !== null && selector.routeType !== undefined && selector.routeType !== line.routeType) return false;
    if (selector.direction !== null && selector.direction !== undefined && selector.direction !== direction) return false;
    if (selector.stopId && ![...(line.stopIds||[]), ...(line.reverseStopIds||[])].includes(selector.stopId)) return false;
    return true;
  }
  function create(options) {
    const $ = id => document.getElementById(id);
    const layer = options.map ? L.layerGroup().addTo(options.map) : null;
    let active=false, state=null, received=0, generation=0, busy=false, failed=false;
    const names={vehiclePositions:'Poziții vehicule',tripUpdates:'Actualizări curse',serviceAlerts:'Alerte transport'};
    const labels={fresh:'Recent',stale:'Date vechi',error:'Sursă indisponibilă',loading:'Se conectează',snapshot:'Captură · fără actualizare'};
    const time = seconds => new Date(seconds*1000).toLocaleTimeString('ro-RO',{timeZone:'Europe/Bucharest',hour:'2-digit',minute:'2-digit'});
    const age = (timestamp,now) => !timestamp ? 'moment necunoscut' : now < timestamp-120 ? 'timestamp în viitor' : `${Math.max(0,Math.floor((now-timestamp)/60))} min în urmă`;
    function message(target,text) {const p=document.createElement('p');p.textContent=text;target.append(p);}
    function render() {
      layer?.clearLayers();
      const statuses=$('liveFeeds'), arrivals=$('liveArrivals'), alerts=$('liveAlerts');
      statuses.replaceChildren();arrivals.replaceChildren();alerts.replaceChildren();
      if(!active || !state?.enabled) {
        $('liveSummary').textContent=failed ? 'Serviciul realtime nu răspunde. Nu sunt afișate poziții live.' : 'Realtime neconectat. Este necesar backend-ul PeLinie cu integrarea TPBI activată.';
        $('mapStatus').textContent='Hartă OpenStreetMap · fără vehicule live conectate.';
        message(arrivals,'Estimările de sosire vor apărea după conectarea serviciului realtime.');
        message(alerts,'Alertele TPBI vor apărea după conectare.');
        return;
      }
      const now=state.generatedAt+(Date.now()-received)/1000;
      const snapshot=state.mode==='snapshot';
      const line=options.getLine(), direction=options.getDirection();
      const feeds=state.feeds;
      const isFresh=(feed,item)=>!failed&&!snapshot&&feed.status==='fresh'&&!item?.stale&&fresh(feed.timestamp,now,state.staleSeconds)&&(!item||fresh(item.timestamp||feed.timestamp,now,state.staleSeconds));
      for(const [key,name] of Object.entries(names)) {
        const feed=feeds[key];const p=document.createElement('p');p.className='live-feed-status';
        const status=failed ? 'error' : feed.status==='fresh'&&!fresh(feed.timestamp,now,state.staleSeconds) ? 'stale' : feed.status;
        p.dataset.status=status;
        p.textContent=`${name}: ${labels[status]}${feed.timestamp ? ' · '+age(feed.timestamp,now) : ''}${feed.error ? ' · '+feed.error : ''}`;
        statuses.append(p);
      }
      const all=$('allVehicles').checked, known=new Map(options.getLines().map(l=>[l.id,l]));
      let count=0,recent=0,oldHidden=0;
      for(const item of feeds.vehiclePositions.items) {
        if(!known.has(item.routeId)||(!all&&item.routeId!==line.id))continue;
        const current=isFresh(feeds.vehiclePositions,item);
        // Limit live cache display to 15 minutes; explicit offline snapshots retain historic markers.
        if(!snapshot&&(!item.timestamp||now-item.timestamp>900||item.timestamp-now>120)){oldHidden++;continue;}
        count++; if(current)recent++;
        if(!layer)continue;
        const vehicleLine=known.get(item.routeId);
        const popup=document.createElement('div');
        popup.textContent=`Linia ${vehicleLine.number||item.routeId}${item.headsign ? ' → '+item.headsign : ''} · ${snapshot?'CAPTURĂ':current?'poziție recentă':'POZIȚIE VECHE'} · ${age(item.timestamp,now)} (${item.timestamp?time(item.timestamp):'fără oră'})`;
        const marker=L.circleMarker([item.latitude,item.longitude],{radius:9,color:current?'#103f90':'#685e48',fillColor:current?'#4189ff':'#b4a17c',fillOpacity:0.95,weight:3});
        marker.bindPopup(popup);marker.addTo(layer);
      }
      $('liveSummary').textContent=`${snapshot?'CAPTURĂ ÎNCĂRCATĂ — fără actualizare automată':failed?'Conexiune cu backend-ul pierdută': 'TPBI · interogare la '+state.pollSeconds+' secunde'} · ${count} vehicule afișate${snapshot?'':', '+recent+' cu poziție recentă'}${oldHidden ? ' · '+oldHidden+' poziții prea vechi sau fără timestamp ascunse' : ''}.`;
      $('mapStatus').textContent=`Hartă OpenStreetMap · ${all?'toate liniile din catalog':'linia '+(line.number||line.id)} · albastru: recent; ocru: captură/date vechi. Cercurile mici verzi sunt stații.`;
      if(!options.map) $('mapStatus').textContent='Harta nu a putut fi inițializată. Datele realtime sunt disponibile în panourile de mai jos.';
      const updates=feeds.tripUpdates;
      if(!snapshot && !isFresh(updates)) {
        message(arrivals,'Estimările curente nu sunt disponibile: sursă indisponibilă sau date vechi.');
      } else {
        const candidates=[];
        for(const update of updates.items) {
          if(update.routeId!==line.id || (update.direction!==null && direction!==null && update.direction!==direction) || (!snapshot&&!isFresh(updates,update)))continue;
          if(update.relationship==='CANCELED'||update.relationship==='DELETED'){message(arrivals,'Cursă anulată'+(update.headsign?' spre '+update.headsign:'.'));continue;}
          if(update.relationship==='DUPLICATED')continue;
          for(const stop of update.stops) {
            const when=stop.arrival||stop.departure;
            if(['SKIPPED','NO_DATA'].includes(stop.relationship)||!when||!snapshot&&(when<now-30||when>now+10800))continue;
            candidates.push({update,stop,when});
          }
        }
        candidates.sort((a,b)=>a.when-b.when);
        for(const {update,stop,when} of candidates.slice(0,8)){
          const delay=Number.isFinite(stop.delay)?` · abatere ${stop.delay>=0?'+':''}${Math.round(stop.delay/60)} min`:'';
          const uncertainty=stop.uncertainty ? ` · incertitudine ±${stop.uncertainty} sec`:'';
          const directionLabel=update.direction===null||direction===null?' · sens neconfirmat':'';
          message(arrivals,`${snapshot?'CAPTURĂ · ':''}${time(when)} · ${stop.stopName||'stație '+stop.stopId}${update.headsign?' → '+update.headsign:''}${directionLabel}${delay}${uncertainty}`);
        }
        if(!arrivals.childNodes.length)message(arrivals,'Nu sunt estimări disponibile pentru această linie și acest sens.');
      }
      const alertFeed=feeds.serviceAlerts;
      if(!isFresh(alertFeed))message(alerts,snapshot?'Alerte din captura încărcată; pot să nu mai fie valabile.':'Fluxul de alerte nu este actual. Informațiile din cache pot să nu mai fie valabile.');
      const reference=snapshot?(alertFeed.timestamp||now):now;
      for(const alert of alertFeed.items) {
        const activePeriod=!alert.periods.length||alert.periods.some(p=>(p.start===null||p.start<=reference)&&(p.end===null||reference<p.end));
        if(!activePeriod||alert.selectors.length&&!alert.selectors.some(s=>selectorMatches(s,line,direction)))continue;
        const article=document.createElement('article'),heading=document.createElement('strong'),body=document.createElement('p');
        article.className='transit-alert';heading.textContent=alert.header||'Alertă de transport';body.textContent=alert.description;
        article.append(heading,body);alerts.append(article);
      }
      if(!alerts.querySelector('article'))message(alerts,isFresh(alertFeed)?'Nicio alertă activă primită pentru linia selectată.':'Nu sunt alerte curente confirmate pentru linia selectată.');
    }
    async function refresh() {
      if(!active||busy)return;
      const token=generation;busy=true;
      try {
        const response=await fetch('api/realtime',{cache:'no-store',signal:AbortSignal.timeout(12000)});
        if(!response.ok)throw Error();
        const result=await response.json();
        if(token!==generation)return;
        state=result;received=Date.now();failed=false;render();
      }catch{if(token===generation){failed=true;render();}}
      finally{busy=false;}
    }
    function setActive(value) {
      generation++;active=value;state=null;failed=false;render();if(active)refresh();
    }
    $('allVehicles').addEventListener('change',render);
    setInterval(refresh,30000);setInterval(render,15000);render();
    return {render,setActive};
  }
  root.LiveTransit={fresh,selectorMatches,create};
  if(typeof module!=='undefined')module.exports=root.LiveTransit;
})(typeof window!=='undefined'?window:globalThis);
