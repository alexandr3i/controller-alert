const test = require('node:test');
const assert = require('node:assert/strict');
const {validate} = require('../transit.js');
const data = () => ({version:1,source:'Synthetic test fixture',importedAt:'2026-10-16T12:00:00Z',lines:[{id:'r1',number:'41',label:'Test',type:'tram',stops:['A','B'],coordinates:[[44.43,26.1],[44.44,26.11]]}]});
test('valid imported stops and optional return',()=>assert.equal(validate(data()).lines[0].typeName,'Tramvai'));
test('malformed imports rejected',()=>{
 for (const mutate of [d=>delete d.lines[0].stops,d=>d.lines.push({...d.lines[0]}),d=>d.lines[0].coordinates[0]=[0,0],d=>d.lines[0].reverseStops=['A'],d=>d.importedAt='bad']) {
  const d=data();mutate(d);assert.throws(()=>validate(d));
 }
});
