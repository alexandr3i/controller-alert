"""Normalize the public mo-bi API without copying upstream application code.
Data terms: https://mo-bi.ro/node/17. Fetch only in the shared backend cache.
Passenger information is intentionally not read or exposed.
"""
from datetime import datetime
import json
import math
import re

URL = 'https://mo-bi.ro/python_api'


def identifier(value):
    if isinstance(value,bool) or not isinstance(value,(str,int)):return None
    value=str(value).strip()
    return value if value.lower() not in ('','none','null','unknown','n/a') and len(value)<=150 else None


def timestamp(value):
    if not isinstance(value,str):return None
    try:
        parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
        return int(parsed.timestamp()) if parsed.tzinfo else None
    except (ValueError,OverflowError):return None


def decode(payload,index,now):
    try:records=json.loads(payload)
    except (ValueError,UnicodeError) as error:raise ValueError('Invalid mo-bi JSON') from error
    if not isinstance(records,list) or len(records)>20000:raise ValueError('Invalid mo-bi dataset')
    items={};rejected=0;unmatched=0
    for record in records:
        if not isinstance(record,dict) or not isinstance(record.get('vehicle'),dict):rejected+=1;continue
        vehicle=record['vehicle'];trip=vehicle.get('trip') or {};position=vehicle.get('position') or {};meta=vehicle.get('vehicle') or {}
        if not all(isinstance(v,dict) for v in (trip,position,meta)):rejected+=1;continue
        latitude,longitude=position.get('latitude'),position.get('longitude')
        if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in (latitude,longitude)) or not (43<=latitude<=46 and 24<=longitude<=28):rejected+=1;continue
        vehicle_id=identifier(meta.get('id'));plate=identifier(meta.get('license_plate'))
        canonical_plate=re.sub(r'[^A-Z0-9]','',plate.upper()) if plate else None
        if canonical_plate and canonical_plate in ('NA','NONE','UNKNOWN','0'):canonical_plate=None
        if not vehicle_id and not canonical_plate:rejected+=1;continue
        trip_id=identifier(trip.get('trip_id'));route=identifier(trip.get('route_id'))
        reference=index.trips.get(trip_id,{})
        if reference and route and route!=reference['routeId']:unmatched+=1;continue
        route=route or reference.get('routeId')
        if not route or index.routes and route not in index.routes:unmatched+=1;continue
        raw_direction=trip.get('direction_id')
        direction=str(raw_direction) if not isinstance(raw_direction,bool) and str(raw_direction) in ('0','1') else reference.get('direction')
        if reference.get('direction') is not None and direction is not None and direction!=reference['direction']:unmatched+=1;continue
        point_time=timestamp(position.get('timestamp'))
        key='mobi:'+('plate:'+canonical_plate if canonical_plate else 'id:'+vehicle_id)
        item=dict(id=key,vehicleId=vehicle_id,licensePlate=plate,routeId=route,tripId=trip_id or '',direction=direction,
                  headsign=reference.get('headsign') or index.headsigns.get((route,direction),''),latitude=latitude,longitude=longitude,
                  timestamp=point_time,source='mobi',relationship='SCHEDULED',startDate=None,startTime=trip.get('start_time') if isinstance(trip.get('start_time'),str) else None)
        old=items.get(key)
        # A record timestamp describes the envelope, not the GPS observation.
        # Ignore future timestamps when choosing between duplicates.
        def rank(value):
            t=value.get('timestamp')
            return t if t and t<=now+120 else -1
        if old is None or rank(item)>rank(old):items[key]=item
    if records and not items and rejected:raise ValueError('No usable mo-bi positions')
    valid_times=[v['timestamp'] for v in items.values() if v['timestamp'] and v['timestamp']<=now+120]
    return dict(timestamp=max(valid_times) if valid_times else None,items=list(items.values()),rejected=rejected,ignored=unmatched,source='mobi',sourceLabel='TPBI / mo-bi',sourceUrl=URL)
