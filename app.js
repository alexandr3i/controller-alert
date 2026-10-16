    "use strict";
    // IMPORTANT: toate liniile, stațiile și raportările de mai jos sunt demonstrative.
    // Nu reprezintă date STB verificate sau controale reale.
    let LINES = [
      { id: "41", type: "tram", typeName: "Tramvai", label: "Ghencea – Piața Presei", stops: ["Ghencea", "Brașov", "Lujerului", "Crângași", "Cașin", "Agronomie", "Piața Presei"] },
      { id: "104", type: "bus", typeName: "Autobuz", label: "Centru – Pantelimon", stops: ["Piața Operei", "Izvor", "Universitate", "Piața Unirii", "Piața Alba Iulia", "Piața Muncii", "Pantelimon"] },
      { id: "168", type: "bus", typeName: "Autobuz", label: "Drumul Taberei – Centru", stops: ["Valea Ialomiței", "Orizont", "Eroilor", "Calea Victoriei", "Piața Romană"] },
      { id: "1", type: "tram", typeName: "Tramvai", label: "Sud – Nord-Est", stops: ["Șura Mare", "Piața Sudului", "Timpuri Noi", "Piața Iancului", "Obor"] },
      { id: "69", type: "trolley", typeName: "Troleibuz", label: "Vest – Est", stops: ["Valea Argeșului", "Orizont", "Eroilor", "Universitate", "Baicului"] }
    ];
    const DEMO_LINES = LINES;
    let importedData = null;
    let catalogRevision = 0;
    let sharedMode = false;
    let sharedReports = [];
    const now = Date.now();
    const DEMOS = [
      { id: "demo-1", line: "41", direction: "forward", stop: "Crângași", createdAt: now - 6 * 60000, demo: true, confirmations: 2 },
      { id: "demo-2", line: "41", direction: "forward", stop: "Cașin", createdAt: now - 18 * 60000, demo: true, confirmations: 1 },
      { id: "demo-3", line: "104", direction: "forward", stop: "Universitate", createdAt: now - 11 * 60000, demo: true, confirmations: 3 },
      { id: "demo-4", line: "168", direction: "reverse", stop: "Eroilor", createdAt: now - 21 * 60000, demo: true, confirmations: 1 }
    ];
    const STORAGE_REPORTS = "pelinie_reports_v1";
    const STORAGE_VOTES = "pelinie_votes_v1";
    const EXPIRY_MS = 45 * 60 * 1000;
    const $ = id => document.getElementById(id);
    const safeRead = (key, fallback) => { try { const data = JSON.parse(localStorage.getItem(key)); return data === null ? fallback : data; } catch { return fallback; } };
    const safeWrite = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { return false; } };
    let localReports = safeRead(STORAGE_REPORTS, []);
    if (!Array.isArray(localReports)) localReports = [];
    let votes = safeRead(STORAGE_VOTES, {});
    if (!votes || typeof votes !== "object" || Array.isArray(votes)) votes = {};
    let selectedId = "41";
    let selectedVariant=null;
    let filter = "all";
    let searchTerm = "";
    let reversed = false;
    let toastTimer;
    const icon = name => `<svg width="17" height="17" aria-hidden="true"><use href="#i-${name}"/></svg>`;
    const routeSort = Transit.compareLines;
    const getLine = id => {
      const line=LINES.find(line=>line.id===id)||LINES[0];
      const variant=id===selectedId&&line.variants?.find(v=>v.id===selectedVariant);
      if(!variant)return line;
      const reverse=variant.direction===line.directionIds?.[1];
      return {...line,activeVariant:variant.id,[reverse?'reverseStops':'stops']:variant.stops,[reverse?'reverseStopIds':'stopIds']:variant.stopIds,[reverse?'reverseCoordinates':'coordinates']:variant.coordinates,[reverse?'reverseGeometry':'geometry']:variant.geometry};
    };
    const getDirection = () => reversed ? "reverse" : "forward";
    const currentStops = () => reversed ? (getLine(selectedId).reverseStops || [...getLine(selectedId).stops].reverse()) : getLine(selectedId).stops;
    const validLocal = report => report && (report.dataset || null) === (importedData ? importedData.importedAt + importedData.source : null) && typeof report === "object" && typeof report.id === "string" && LINES.some(line => line.id === report.line && [...line.stops,...(line.reverseStops||[]),...(line.variants||[]).flatMap(v=>v.stops)].includes(report.stop)) && ["forward", "reverse"].includes(report.direction) && Number.isFinite(report.createdAt) && report.createdAt <= Date.now() && Date.now() - report.createdAt < EXPIRY_MS;
    const allReports = () => sharedMode ? sharedReports : [...(importedData ? [] : DEMOS), ...localReports.filter(validLocal)];
    const selectedReports = () => allReports().filter(report => report.line === selectedId && report.direction === getDirection()).sort((a, b) => b.createdAt - a.createdAt);
    const formatAge = time => { const mins = Math.max(0, Math.floor((Date.now() - time) / 60000)); return mins < 1 ? "chiar acum" : `acum ${mins} min`; };
    const notify = message => { const t = $("toast"); t.textContent = message; t.classList.add("show"); clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove("show"), 2800); };
    function renderLines() {
      const matching = [...LINES].sort(routeSort).filter(line => (filter === "all" || line.type === filter) && ((line.number || line.id).includes(searchTerm) || line.label.toLocaleLowerCase("ro").includes(searchTerm) || [...line.stops, ...(line.reverseStops || [])].some(stop => stop.toLocaleLowerCase("ro").includes(searchTerm))));
      const root = $("linesList"); root.replaceChildren();
      $("linesCount").textContent = `${matching.length} ${matching.length === 1 ? "linie" : "linii"}`;
      if (matching.length === 0) { const p = document.createElement("p"); p.className = "empty-results"; p.textContent = "Nu am găsit linii. Încearcă altă căutare."; root.append(p); return; }
      matching.forEach(line => {
        const btn = document.createElement("button");
        btn.type = "button"; btn.className = `line-choice${line.id === selectedId ? " is-selected" : ""}`; btn.setAttribute("aria-pressed", String(line.id === selectedId));
        const badge = document.createElement("span"); badge.className = `line-box ${line.type}`; badge.textContent = line.number || line.id;
        const body = document.createElement("span"); body.className = "line-copy";
        const strong = document.createElement("strong"); strong.textContent = line.label;
        const small = document.createElement("small"); small.textContent = line.typeName;
        body.append(strong, small);
        const arrow = document.createElement("span"); arrow.className = "choice-arrow"; arrow.innerHTML = icon("arrow");
        btn.append(badge, body, arrow);
        btn.addEventListener("click", () => { selectedId = line.id; selectedVariant=null; reversed = false; renderAll(); if (window.innerWidth < 740) $("routeSection").scrollIntoView({ behavior: "smooth", block: "start" }); });
        root.append(btn);
      });
    }
    function renderRoute() {
      const line = getLine(selectedId);
      $("statLine").textContent = line.number || line.id;
      $("statType").textContent = line.typeName;
      $("statReports").textContent = selectedReports().length;
      $("statStops").textContent = currentStops().length;
      $("routeBadge").textContent = line.number || line.id;
      $("routeBadge").className = `route-badge ${line.type}`;
      $("routeTitle").textContent = `Linia ${line.number || line.id}`;
      $("routeSubtitle").textContent = `${line.typeName} · ${importedData ? "date importate" : "traseu demonstrativ"}`;
      $("reverseButton").disabled = Boolean(importedData && !line.reverseStops);
      const variantSelect=$('variantSelect');variantSelect.replaceChildren();
      for(const variant of line.variants||[]){const opt=document.createElement('option');opt.value=variant.id;opt.textContent=(variant.headsign||variant.stops.at(-1))+' · '+variant.stops.length+' stații';variantSelect.append(opt);}
      variantSelect.disabled=!line.variants?.length;
      const active=line.variants?.find(v=>v.id===selectedVariant)||line.variants?.find(v=>v.direction===line.directionIds?.[reversed?1:0]);
      if(active)variantSelect.value=active.id;
      journeyUI.update();
      drawMap();
      const stops = currentStops();
      $("directionText").textContent = `${stops[0]} → ${stops[stops.length - 1]}`;
      const hasReport = new Set(selectedReports().map(report => report.stop));
      const list = $("stopsList"); list.replaceChildren();
      stops.forEach((stop,stopIndex) => {
        const row = document.createElement("div"); row.className = "stop";
        const dot = document.createElement("span"); dot.className = "stop-dot";
        const body = document.createElement("div"); body.className = "stop-body";
        const label = document.createElement("div");
        const name = document.createElement("span"); name.className = "stop-name stop-link"; name.tabIndex=0; name.setAttribute("role","button"); const choose=()=>journeyUI.choose((reversed?line.reverseStopIds:line.stopIds)?.[stopIndex]); name.addEventListener("click",choose); name.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();choose();}}); name.textContent = stop; label.append(name);
        if (hasReport.has(stop)) { const tag = document.createElement("span"); tag.className = "stop-tag"; tag.textContent = "● Control raportat · neverificat"; label.append(tag); }
        const button = document.createElement("button"); button.type = "button"; button.className = "stop-add"; button.setAttribute("aria-label", `Raportează la stația ${stop}`); button.textContent = "+ Raportează";
        button.addEventListener("click", () => openReportDialog(stop));
        body.append(label, button); row.append(dot, body); list.append(row);
      });
    }
    function renderFeed() {
      const reports = selectedReports();
      const root = $("reportsList"); root.replaceChildren();
      if (reports.length === 0) { const empty = document.createElement("div"); empty.className = "empty-feed"; empty.innerHTML = '<span class="big">◎</span>Nicio observație pe acest sens.<br/>Poți adăuga una pentru a testa aplicația.'; root.append(empty); return; }
      reports.forEach(report => {
        const wrap = document.createElement("article"); wrap.className = "report"; wrap.dataset.reportId=report.id;
        const top = document.createElement("div"); top.className = "report-top";
        const marker = document.createElement("span"); marker.className = "report-icon"; marker.innerHTML = icon("alert");
        const body = document.createElement("div"); body.className = "report-body";
        const title = document.createElement("div"); title.className = "report-title"; title.textContent = "Control semnalat";
        const place = document.createElement("span"); place.className = "report-place"; place.textContent = `Stația ${report.stop}`;
        body.append(title, place);
        const time = document.createElement("time"); time.className = "report-time"; time.dateTime = new Date(report.createdAt).toISOString(); time.textContent = formatAge(report.createdAt);
        top.append(marker, body, time);
        const actions = document.createElement("div"); actions.className = "report-actions";
        const origin = document.createElement("span"); origin.className = `report-origin${report.demo ? "" : " me"}`; origin.textContent = report.shared ? "COMUNITATE · NEVERIFICAT" : report.demo ? "EXEMPLU" : "DOAR LOCAL";
        const confirmation = document.createElement("button"); confirmation.type = "button";
        const wasVoted = report.shared ? report.voted : Boolean(votes[report.id]);
        confirmation.className = `action-mini${wasVoted ? " is-voted" : ""}`;
        confirmation.setAttribute("aria-pressed", String(wasVoted));
        confirmation.textContent = `${wasVoted ? "✓ Confirmat" : "✓ Confirmă"} · ${(report.confirmations || 0) + (!report.shared && wasVoted ? 1 : 0)}`;
        confirmation.addEventListener("click", () => { if (report.shared) { sendShared({action:"vote",id:report.id,voted:!report.voted}); return; } votes[report.id] = !votes[report.id]; safeWrite(STORAGE_VOTES, votes); renderFeed(); notify("Confirmarea a fost salvată doar local."); });
        actions.append(origin, confirmation);
        if (!report.demo && (!report.shared || report.canDelete)) {
          const del = document.createElement("button"); del.type = "button"; del.className = "action-mini delete"; del.textContent = "Șterge";
          del.setAttribute("aria-label", `Șterge raportarea de la ${report.stop}`);
          del.addEventListener("click", () => { if (report.shared) { sendShared({action:"delete",id:report.id}); return; } localReports = localReports.filter(item => item.id !== report.id); safeWrite(STORAGE_REPORTS, localReports); delete votes[report.id]; safeWrite(STORAGE_VOTES, votes); renderAll(); notify("Raportarea locală a fost ștearsă."); });
          actions.append(del);
        }
        wrap.append(top, actions); root.append(wrap);
      });
    }
    function renderAll() { renderLines(); renderRoute(); renderFeed(); }
    function fillReportLine() {
      const select = $("formLine"); select.replaceChildren();
      LINES.forEach(line => { const opt = document.createElement("option"); opt.value = line.id; opt.textContent = `${line.number || line.id} · ${line.typeName}`; select.append(opt); });
    }
    function fillReportStops(preferredStop) {
      const line = getLine($("formLine").value);
      const select = $("formStop"); select.replaceChildren();
      const reverseOption = $("formDirection").querySelector('[value="reverse"]');
      reverseOption.disabled = Boolean(importedData && !line.reverseStops);
      if (reverseOption.disabled) $("formDirection").value = "forward";
      const stops = $("formDirection").value === "reverse" ? (line.reverseStops || [...line.stops].reverse()) : line.stops;
      stops.forEach(stop => { const opt = document.createElement("option"); opt.value = stop; opt.textContent = stop; select.append(opt); });
      if (preferredStop && stops.includes(preferredStop)) select.value = preferredStop;
    }
    function openReportDialog(preferredStop) {
      $("formLine").value = selectedId;
      $("formDirection").value = getDirection();
      fillReportStops(preferredStop);
      const dlg = $("reportDialog");
      if (typeof dlg.showModal === "function") dlg.showModal(); else dlg.setAttribute("open", "");
    }
    function closeReportDialog() { const dlg = $("reportDialog"); if (typeof dlg.close === "function") dlg.close(); else dlg.removeAttribute("open"); }
    document.querySelectorAll("[data-filter]").forEach(button => button.addEventListener("click", () => {
      filter = button.dataset.filter;
      document.querySelectorAll("[data-filter]").forEach(btn => { const active = btn === button; btn.classList.toggle("is-active", active); btn.setAttribute("aria-pressed", String(active)); });
      renderLines();
    }));
    $("lineSearch").addEventListener("input", event => { searchTerm = event.target.value.trim().toLocaleLowerCase("ro"); renderLines(); });
    $("reverseButton").addEventListener("click", () => { reversed = !reversed; selectedVariant=null; renderRoute(); renderFeed(); });
    $("newReportButton").addEventListener("click", () => openReportDialog());
    $("formLine").addEventListener("change", () => fillReportStops());
    $("formDirection").addEventListener("change", () => fillReportStops());
    $("closeModalButton").addEventListener("click", closeReportDialog);
    $("cancelModalButton").addEventListener("click", closeReportDialog);
    $("reportDialog").addEventListener("click", event => { if (event.target === $("reportDialog")) closeReportDialog(); });
    $("reportForm").addEventListener("submit", async event => {
      event.preventDefault();
      const line = $("formLine").value; const direction = $("formDirection").value; const stop = $("formStop").value;
      const route = getLine(line);
      if (!route || (importedData && direction === "reverse" && !route.reverseStops) || !(direction === "reverse" && route.reverseStops ? route.reverseStops : route.stops).includes(stop) || !["forward", "reverse"].includes(direction)) { notify("Selectează o linie și o stație validă."); return; }
      if (sharedMode) {
        const button=$("reportForm").querySelector('[type="submit"]'); button.disabled=true;
        try { if (await sendShared({action:"create",line,direction,stop,stopId:(direction==="reverse"?route.reverseStopIds:route.stopIds)?.[(direction==="reverse"?route.reverseStops:route.stops).indexOf(stop)]})) {selectedId=line; reversed=direction==="reverse"; closeReportDialog(); renderAll();} }
        finally {button.disabled=false;}
        return;
      }
      const id = typeof crypto !== "undefined" && typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `local-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      localReports.push({ id, line, direction, stop, stopId:(direction==="reverse"?route.reverseStopIds:route.stopIds)?.[(direction==="reverse"?route.reverseStops:route.stops).indexOf(stop)], dataset: importedData ? importedData.importedAt + importedData.source : null, createdAt: Date.now(), demo: false, confirmations: 0 });
      const persisted = safeWrite(STORAGE_REPORTS, localReports);
      selectedId = line; reversed = direction === "reverse";
      closeReportDialog(); renderAll();
      notify(persisted ? "Raportare adăugată doar pe dispozitivul tău." : "Raportare adăugată doar pentru această sesiune.");
      $("reportsSection").scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
    $("aboutButton").addEventListener("click", () => notify("PeLinie v0.4 — experiment independent. Sursele și modul de raportare sunt indicate în pagină."));
    $("resetButton").addEventListener("click", () => { localReports = []; votes = {}; try { localStorage.removeItem(STORAGE_REPORTS); localStorage.removeItem(STORAGE_VOTES); } catch {} renderAll(); notify("Datele locale de test au fost șterse."); });
    document.querySelectorAll("[data-scroll]").forEach(button => button.addEventListener("click", () => $(button.dataset.scroll).scrollIntoView({ behavior: "smooth", block: "start" })));
    const map = typeof L === "undefined" ? null : L.map("map", {scrollWheelZoom:false}).setView([44.435,26.102],12);
    const journeyUI=Journey.create({getLine:()=>getLine(selectedId),getDirection:()=>getLine(selectedId).directionIds?.[reversed?1:0]??null,isReversed:()=>reversed,isOnline:()=>sharedMode});
    const mapLayer = map ? L.layerGroup().addTo(map) : null;
    const realtimeUI = LiveTransit.create({map,getLine:()=>getLine(selectedId),getLines:()=>LINES,getDirection:()=>getLine(selectedId).directionIds?.[reversed?1:0] ?? null});
    const reportLayer=map?L.layerGroup().addTo(map):null;
    let mappedKey = "";
    $('variantSelect').addEventListener('change',()=>{selectedVariant=$('variantSelect').value;const v=getLine(selectedId).variants.find(v=>v.id===selectedVariant);reversed=v.direction===getLine(selectedId).directionIds?.[1];renderAll();});
    function reportPoint(report){
      if(report.coordinates)return report.coordinates;
      const line=LINES.find(l=>l.id===report.line);if(!line)return null;
      const reverse=report.direction==='reverse';const direction=line.directionIds?.[reverse?1:0];
      const variants=line.variants?.filter(v=>v.direction===direction)||[{stops:reverse?line.reverseStops:line.stops,coordinates:reverse?line.reverseCoordinates:line.coordinates,stopIds:reverse?line.reverseStopIds:line.stopIds}];
      for(const v of variants){const i=report.stopId?v.stopIds?.indexOf(report.stopId):v.stops?.indexOf(report.stop);if(i>=0)return v.coordinates?.[i];}return null;
    }
    function drawReports(){
      if(!reportLayer)return;reportLayer.clearLayers();if(!$('showReports').checked)return;
      const all=$('allVehicles').checked;
      for(const report of allReports()){
        if(report.demo||Date.now()-report.createdAt>=EXPIRY_MS)continue;
        const point=reportPoint(report);if(!point)continue;
        const content=document.createElement('div'),title=document.createElement('strong'),body=document.createElement('p'),confirm=document.createElement('button');
        title.textContent='Control raportat · neverificat';body.textContent='Linia '+(getLine(report.line).number||report.line)+' · '+(report.direction==='reverse'?'sens retur':'sens tur')+' · '+report.stop+' · '+formatAge(report.createdAt)+' · '+(report.shared?'Comunitate':'Doar local');
        confirm.textContent='Confirmă';confirm.type='button';confirm.addEventListener('click',()=>{if(report.shared)sendShared({action:'vote',id:report.id,voted:!report.voted});else{votes[report.id]=!votes[report.id];safeWrite(STORAGE_VOTES,votes);renderAll();}});
        const routeButton=document.createElement('button');routeButton.type='button';routeButton.textContent='Deschide linia';routeButton.addEventListener('click',()=>{selectedId=report.line;reversed=report.direction==='reverse';selectedVariant=null;renderAll();});
        content.append(title,body,confirm,routeButton);
        const pin=L.marker(point,{icon:L.divIcon({className:'control-pin',html:'<span aria-hidden="true">!</span>',iconSize:[32,38],iconAnchor:[16,38]}),title:'Control raportat la '+report.stop}).bindPopup(content).addTo(reportLayer);pin.getElement().dataset.controlReport=report.id;
      }
    }
    $('allVehicles').addEventListener('change',drawReports);$('showReports').addEventListener('change',drawReports);
    if (map) {
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {maxZoom:19, attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).on("tileerror",()=>{$("tileStatus").textContent="Fundalul hărții nu poate fi încărcat. Verifică accesul la tile.openstreetmap.org. Traseele importate rămân disponibile.";}).addTo(map);
    } else $("mapStatus").textContent = "Harta nu a putut fi inițializată.";
    function drawMap() {
      realtimeUI.render();
      drawReports();
      if (!map) return;
      const key = (importedData ? importedData.importedAt : "demo") + selectedId + reversed + selectedVariant;
      if (key === mappedKey) return;
      mappedKey = key; mapLayer.clearLayers();
      const line = getLine(selectedId);
      const points = reversed ? line.reverseCoordinates : line.coordinates;
      if (!points) { map.setView([44.435,26.102],12); return; }
      const names = currentStops();
      L.polyline((reversed?line.reverseGeometry:line.geometry)||points,{color:"#168660",weight:5,dashArray:(reversed?line.reverseGeometry:line.geometry)?undefined:"6 7"}).addTo(mapLayer);
      points.forEach((point,i)=>{
        const content=document.createElement("div"); content.textContent=names[i];const at=document.createElement("button");at.textContent="Vezi sosiri";at.addEventListener("click",()=>journeyUI.choose((reversed?line.reverseStopIds:line.stopIds)?.[i]));content.append(document.createElement("br"),at);
        L.circleMarker(point,{radius:6,color:"#075d3a",fillColor:"#77edb6",fillOpacity:1}).bindPopup(content).addTo(mapLayer);
      });
      map.fitBounds(L.latLngBounds(points),{padding:[24,24],maxZoom:15});
    }
    function useData(data) {
      catalogRevision++;
      realtimeUI.setActive(false);
      sharedMode=false; sharedReports=[];
      document.querySelector(".feed-foot").textContent="Raportările sunt salvate doar în acest browser. Importul trebuie repetat după reîncărcare.";
      document.querySelector(".modal-help").textContent="Salvare doar în acest browser; expirare după 45 de minute. Fără GPS, fotografii sau identitatea persoanelor.";
      $("reportForm").querySelector('[type="submit"]').textContent="Salvează local";
      importedData = data; LINES = [...(data ? data.lines : DEMO_LINES)].sort(routeSort);selectedVariant=null;
      selectedId=LINES[0].id; reversed=false; filter="all"; searchTerm=""; $("lineSearch").value="";
      document.querySelectorAll("[data-filter]").forEach(b=>{b.classList.toggle("is-active",b.dataset.filter==="all");b.setAttribute("aria-pressed",String(b.dataset.filter==="all"));});
      $("modeStatus").textContent=data ? "DATE IMPORTATE — sursă declarată de utilizator, fără vehicule live; raportări doar locale" : "MOD DEMONSTRAȚIE — date fictive, fără raportări publice sau poziții în timp real";
      $("dataStatus").textContent=data ? `Sursă declarată: ${data.source} · Import: ${new Date(data.importedAt).toLocaleString("ro-RO",{timeZone:"Europe/Bucharest"})} · ${data.lines.length} linii. Variante și geometrie GTFS când sunt disponibile. Linia punctată indică lipsa geometriei.` : "Trasee demonstrative. Nu sunt desenate pe hartă deoarece nu au coordonate verificate.";
      $("mapStatus").textContent="Hartă OpenStreetMap · fără vehicule live conectate.";
      document.querySelector(".route-footer").textContent=data ? "Stații din fișierul importat. Lipsa sensului retur în date dezactivează inversarea. Pozițiile vehiculelor apar separat pe hartă." : "Schemă demonstrativă; fără coordonate sau vehicule live.";
      fillReportLine(); renderAll();
    }
    $("transitFile").addEventListener("change",async event=>{
      const file=event.target.files[0]; if(!file)return;
      try { if(file.size>10*1024*1024)throw Error("Fișierul depășește limita de 10 MB."); const data=Transit.validate(JSON.parse(await file.text())); useData(data); }
      catch(error) { $("dataStatus").textContent="Import nereușit: "+error.message; }
      event.target.value="";
    });
    $("demoDataButton").addEventListener("click",()=>useData(null));
    fillReportLine(); renderAll();
    // Elimină automat raportările locale expirate și actualizează timpii din interfață.
    setInterval(() => {
      const current = localReports.filter(report => report && Number.isFinite(report.createdAt) && report.createdAt <= Date.now() && Date.now() - report.createdAt < EXPIRY_MS);
      if (current.length !== localReports.length) { localReports = current; safeWrite(STORAGE_REPORTS, localReports); }
      renderRoute(); renderFeed();
    }, 60 * 1000);

    async function sendShared(payload) {
      try {
        const response=await fetch("api/reports",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
        const result=await response.json(); if(!response.ok)throw Error(result.error || "Serviciu indisponibil");
        sharedReports=result; renderAll(); notify("Raportările comunității au fost actualizate."); return true;
      } catch(error) { notify("Salvarea nu a reușit: "+error.message); return false; }
    }
    async function refreshShared() {
      if(!sharedMode)return;
      const requestedCatalog=importedData;
      try {
        const response=await fetch("api/reports",{cache:"no-store"}); if(!response.ok)throw Error();
        const reports=await response.json();if(!sharedMode||importedData!==requestedCatalog)return;sharedReports=reports; renderAll();
        document.querySelector(".feed-foot").textContent="Raportări comunitare neverificate · expiră în 45 min · actualizare la 30 sec. Ultima sincronizare: "+new Date().toLocaleTimeString("ro-RO",{timeZone:"Europe/Bucharest"});
      } catch { if(!sharedMode||importedData!==requestedCatalog)return; sharedReports=[]; renderAll(); document.querySelector(".feed-foot").textContent="Serviciul comunitar nu răspunde. Raportările nu pot fi verificate; reîncercăm automat."; }
    }
    async function connectCommunity() {
      const initialRevision=catalogRevision;
      try {
        const response=await fetch("api/catalog",{cache:"no-store",signal:AbortSignal.timeout(12000)}); if(!response.ok)throw Error();
        const data=Transit.validate(await response.json()); if(catalogRevision!==initialRevision)return; useData(data); sharedMode=true;
        $("modeStatus").textContent="TRASEE IMPORTATE · raportări comunitare neverificate · verifică starea realtime pe hartă";
        document.querySelector(".modal-help").textContent="Raportarea devine vizibilă tuturor utilizatorilor acestui serviciu și expiră după 45 min. Fără GPS, nume sau fotografii. Maximum 3 raportări în 10 minute pe sesiune.";
        $("reportForm").querySelector('[type="submit"]').textContent="Publică raportarea";
        realtimeUI.setActive(true);
        await refreshShared();
      } catch {
        try {
          const response=await fetch("data/catalog.json",{signal:AbortSignal.timeout(12000)});if(!response.ok)return;
          const data=Transit.validate(await response.json());if(catalogRevision!==initialRevision)return;useData(data);
        } catch { /* Static examples remain usable without the bundled catalog. */ }
      }
    }
    connectCommunity();
    setInterval(refreshShared,30000);

    setInterval(async()=>{
      if(!sharedMode)return;
      const revision=catalogRevision,previous=importedData;
      try{
        const response=await fetch('api/catalog',{cache:'no-store',headers:previous.revision&&!previous.sync?.error?{'If-None-Match':'"'+previous.revision+'"'}:{},signal:AbortSignal.timeout(12000)});if(response.status===304)return;if(!response.ok)return;
        const data=Transit.validate(await response.json());if(revision!==catalogRevision||!sharedMode)return;
        if(data.sync?.error)$('dataStatus').textContent=data.sync.error;
        else if(previous.sync?.error)$('dataStatus').textContent='Catalog TPBI sincronizat · '+data.lines.length+' linii.';
        previous.sync=data.sync;
        if(data.revision&&data.revision!==previous.revision){const line=selectedId,reverse=reversed;useData(data);selectedId=LINES.some(l=>l.id===line)?line:LINES[0].id;reversed=reverse&&!!getLine(selectedId).reverseStops;sharedMode=true;realtimeUI.setActive(true);renderAll();await refreshShared();notify('Traseele și orarele TPBI au fost actualizate.');}
      }catch{/* Preserve the last validated catalog and report the independent live state. */}
    },300000);
