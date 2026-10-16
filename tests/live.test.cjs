const test=require('node:test');
const assert=require('node:assert/strict');
const {fresh,selectorMatches}=require('../live.js');
const line={id:'r1',agencyId:'1',routeType:3,stopIds:['s1'],reverseStopIds:['s2']};
test('freshness rejects old, absent and future timestamps',()=>{
 assert(fresh(1000,1100));for(const t of [null,undefined,0,800,1230])assert(!fresh(t,1100));
});
test('alert selectors intersect their fields and preserve scope',()=>{
 assert(selectorMatches({routeId:'r1',stopId:'s1',agencyId:'1'},line,'0'));
 assert(!selectorMatches({routeId:'r1',agencyId:'other'},line,'0'));
 assert(!selectorMatches({tripId:'unknown'},line,'0'));
 assert(!selectorMatches({stopId:'s3'},line,'0'));
 assert(!selectorMatches({routeType:0},line,'0'));
 assert(!selectorMatches({routeId:'r1',direction:'1'},line,'0'));
 assert(selectorMatches({},line,'0'));
});
