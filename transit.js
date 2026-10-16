/* Transit imports are user supplied; validation does not establish official provenance. */
(function (root) {
  'use strict';
  function validate(data) {
    if (!data || data.version !== 1 || typeof data.source !== 'string' || !data.source.trim() || data.source.length > 500 || !Number.isFinite(Date.parse(data.importedAt)) || !Array.isArray(data.lines) || !data.lines.length || data.lines.length > 1000) throw Error('Fișier de trasee invalid. Folosește convertorul GTFS.');
    const ids = new Set();
    for (const line of data.lines) {
      if (!line || typeof line.id !== 'string' || !line.id || line.id.length > 150 || ids.has(line.id) || typeof line.label !== 'string' || line.label.length > 500 || !['tram','bus','trolley'].includes(line.type)) throw Error('Linie invalidă sau duplicată.');
      if (line.number !== undefined && (typeof line.number !== 'string' || line.number.length > 50)) throw Error('Număr de linie invalid.');
      ids.add(line.id);
      for (const [index,[names,coords]] of [[line.stops,line.coordinates], [line.reverseStops,line.reverseCoordinates]].entries()) {
        if (index === 1 && names === undefined && coords === undefined) continue;
        if (!Array.isArray(names) || !names.length || names.length > 500 || !Array.isArray(coords) || coords.length !== names.length || names.some(n=>typeof n!=='string'||!n||n.length>250) || coords.some(p=>!Array.isArray(p)||p.length!==2||!Number.isFinite(p[0])||!Number.isFinite(p[1])||p[0]<43||p[0]>46||p[1]<24||p[1]>28)) throw Error('Stații sau coordonate invalide pentru zona București–Ilfov.');
      }
      line.typeName = {tram:'Tramvai',bus:'Autobuz',trolley:'Troleibuz'}[line.type];
    }
    return data;
  }
  root.Transit = {validate};
  if (typeof module !== 'undefined') module.exports = root.Transit;
})(typeof window !== 'undefined' ? window : globalThis);
