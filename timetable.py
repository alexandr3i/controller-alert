"""GTFS service-day aware planned departures, reconciled with fresh realtime updates."""
import csv
from datetime import datetime, timedelta
import io
from pathlib import Path
import sqlite3
import time
from zipfile import ZipFile
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('Europe/Bucharest')


def seconds(value):
    if not value: return None
    h,m,s = map(int,value.split(':'))
    if h < 0 or not 0 <= m < 60 or not 0 <= s < 60: raise ValueError('Invalid GTFS time')
    return h*3600+m*60+s


def service_epoch(day):
    # GTFS time is seconds after local noon minus 12 hours, including DST days.
    return datetime.combine(day,datetime.min.time().replace(hour=12),ZONE).timestamp()-43200


class Timetable:
    def __init__(self, source, database=None):
        self.path = Path(database or Path(source).with_name('timetable-v1.sqlite3'))
        if not self.path.exists():
            temporary = self.path.with_suffix('.building')
            temporary.unlink(missing_ok=True)
            db = sqlite3.connect(temporary)
            try:
                db.executescript('''CREATE TABLE trips(id TEXT PRIMARY KEY,route TEXT,direction TEXT,service TEXT,headsign TEXT);
                    CREATE TABLE times(trip TEXT,stop TEXT,seq INTEGER,seconds INTEGER);
                    CREATE TABLE calendar(service TEXT,week TEXT,start TEXT,end TEXT);
                    CREATE TABLE exceptions(service TEXT,date TEXT,type INTEGER);''')
                with ZipFile(source) as z:
                    def rows(name):
                        if name not in z.namelist(): return
                        with z.open(name) as f: yield from csv.DictReader(io.TextIOWrapper(f,encoding='utf-8-sig'))
                    db.executemany('INSERT INTO trips VALUES (?,?,?,?,?)',((r['trip_id'],r['route_id'],r.get('direction_id') or '0',r['service_id'],r.get('trip_headsign','')) for r in rows('trips.txt')))
                    db.executemany('INSERT INTO times VALUES (?,?,?,?)',((r['trip_id'],r['stop_id'],int(r['stop_sequence']),seconds(r.get('departure_time') or r.get('arrival_time'))) for r in rows('stop_times.txt')))
                    days=['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
                    db.executemany('INSERT INTO calendar VALUES (?,?,?,?)',((r['service_id'],''.join(r[d] for d in days),r['start_date'],r['end_date']) for r in rows('calendar.txt')))
                    db.executemany('INSERT INTO exceptions VALUES (?,?,?)',((r['service_id'],r['date'],int(r['exception_type'])) for r in rows('calendar_dates.txt')))
                db.executescript('CREATE INDEX by_stop ON times(stop,seconds); CREATE INDEX by_route ON trips(route,direction);')
                db.commit()
                db.close()
                temporary.rename(self.path)
            except BaseException:
                db.close();temporary.unlink(missing_ok=True);raise

    @staticmethod
    def services(db,day):
        stamp=day.strftime('%Y%m%d')
        active={sid for sid,week in db.execute('SELECT service,week FROM calendar WHERE start<=? AND end>=?',(stamp,stamp)) if week[day.weekday()]=='1'}
        for sid,kind in db.execute('SELECT service,type FROM exceptions WHERE date=?',(stamp,)):
            if kind==1: active.add(sid)
            elif kind==2: active.discard(sid)
        return active

    def departures(self,line,direction,stop,*,now=None,realtime=None,date=None):
        now = time.time() if now is None else now
        today = datetime.strptime(date,'%Y-%m-%d').date() if date else datetime.fromtimestamp(now,ZONE).date()
        lower=datetime.combine(today,datetime.min.time(),ZONE).timestamp() if date else now-60
        upper=datetime.combine(today+timedelta(days=1),datetime.min.time(),ZONE).timestamp() if date else now+86400
        output=[]
        with sqlite3.connect(self.path) as db:
            for offset in (-2,-1,0,1):
                day=today+timedelta(days=offset);base=service_epoch(day);active=self.services(db,day)
                if not active: continue
                for tid,service,headsign,seq,second in db.execute('''SELECT t.id,t.service,t.headsign,s.seq,s.seconds FROM times s JOIN trips t ON s.trip=t.id
                        WHERE t.route=? AND t.direction=? AND s.stop=? AND s.seconds>=? AND s.seconds<=?''',(line,direction,stop,lower-base-10800,upper-base)):
                    if service not in active: continue
                    planned=int(base+second)
                    output.append(dict(tripId=tid,stopId=stop,sequence=seq,headsign=headsign,serviceDate=day.strftime('%Y%m%d'),plannedTime=planned,expectedTime=planned,status='planned'))
        fresh_updates={}
        feed=(realtime or {}).get('feeds',{}).get('tripUpdates',{})
        if (realtime or {}).get('mode')=='live' and feed.get('status')=='fresh':
            for item in feed.get('items',[]):
                if not item.get('stale') and item['routeId']==line: fresh_updates.setdefault(item['tripId'],[]).append(item)
        for entry in output:
            for trip in fresh_updates.get(entry['tripId'],[]):
                if trip.get('startDate') and trip['startDate']!=entry['serviceDate']: continue
                if not trip.get('startDate') and abs(entry['plannedTime']-trip['timestamp'])>10800:continue
                if trip['relationship'] in ('CANCELED','DELETED'):
                    entry['status']='cancelled';break
                for update in trip['stops']:
                    if update['stopId']!=stop or update.get('sequence') and update['sequence']!=entry['sequence']: continue
                    if update['relationship']=='SKIPPED':entry['status']='skipped';break
                    if update['relationship']=='NO_DATA':break
                    predicted=update.get('departure') or update.get('arrival')
                    if predicted is None and update.get('delay') is not None:predicted=entry['plannedTime']+update['delay']
                    # Missing service dates must not bind a trip to a different day's run.
                    if predicted is not None and abs(predicted-entry['plannedTime'])<=10800:
                        entry.update(expectedTime=predicted,status='live',updatedAt=trip['timestamp'])
                    break
        output=[e for e in output if e['expectedTime']>=lower and e['expectedTime']<upper]
        output.sort(key=lambda e:e['expectedTime'])
        return dict(generatedAt=int(now),timezone='Europe/Bucharest',line=line,direction=direction,stopId=stop,date=date,departures=output if date else output[:40],realtimeAvailable=feed.get('status')=='fresh' and (realtime or {}).get('mode')=='live')
