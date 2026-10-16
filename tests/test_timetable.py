from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile
from timetable import Timetable, ZONE


class TimetableTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'feed.zip'
        with ZipFile(self.path,'w') as z:
            z.writestr('trips.txt','route_id,service_id,trip_id,direction_id,trip_headsign\nr1,weekday,t1,0,Terminal\nr1,weekday,late,0,Night\nr1,removed,removed,0,Removed\nr1,extra,extra,0,Extra\n')
            z.writestr('stop_times.txt','trip_id,stop_id,stop_sequence,arrival_time,departure_time\nt1,s1,1,08:10:00,08:10:00\nlate,s1,1,25:05:00,25:05:00\nremoved,s1,1,08:12:00,08:12:00\nextra,s1,1,08:15:00,08:15:00\n')
            z.writestr('calendar.txt','service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nweekday,1,1,1,1,1,0,0,20260101,20261231\nremoved,1,1,1,1,1,1,1,20260101,20261231\n')
            z.writestr('calendar_dates.txt','service_id,date,exception_type\nremoved,20261016,2\nextra,20261016,1\n')
        self.table=Timetable(self.path)
        self.now=datetime(2026,10,16,8,0,tzinfo=ZONE).timestamp()

    def tearDown(self):self.tmp.cleanup()

    def test_service_calendar_exceptions_and_full_day(self):
        entries=self.table.departures('r1','0','s1',now=self.now,date='2026-10-16')['departures']
        self.assertEqual([e['tripId'] for e in entries],['late','t1','extra'])
        self.assertEqual(datetime.fromtimestamp(next(e for e in entries if e['tripId']=='t1')['plannedTime'],ZONE).hour,8)
        self.assertEqual(self.table.departures('r1','1','s1',now=self.now)['departures'],[])

    def test_after_midnight_keeps_previous_service_day(self):
        now=datetime(2026,10,17,1,0,tzinfo=ZONE).timestamp()
        entry=self.table.departures('r1','0','s1',now=now)['departures'][0]
        self.assertEqual(entry['tripId'],'late');self.assertEqual(entry['serviceDate'],'20261016')
        self.assertEqual(datetime.fromtimestamp(entry['plannedTime'],ZONE).hour,1)

    def state(self,relationship='SCHEDULED',stop_relationship='SCHEDULED',stale=False,start_date='20261016'):
        return {'mode':'live','feeds':{'tripUpdates':{'status':'fresh','items':[dict(tripId='t1',routeId='r1',startDate=start_date,stale=stale,relationship=relationship,timestamp=int(self.now),stops=[dict(stopId='s1',sequence=1,arrival=None,departure=None,delay=300,relationship=stop_relationship)])]}}}

    def test_live_delay_no_data_cancellation_and_stale(self):
        live=self.table.departures('r1','0','s1',now=self.now,realtime=self.state())['departures']
        t1=next(e for e in live if e['tripId']=='t1')
        self.assertEqual(t1['status'],'live');self.assertEqual(t1['expectedTime']-t1['plannedTime'],300)
        for state in [self.state(stale=True),self.state(stop_relationship='NO_DATA'),self.state(start_date='20261015')]:
            t1=next(e for e in self.table.departures('r1','0','s1',now=self.now,realtime=state)['departures'] if e['tripId']=='t1')
            self.assertEqual(t1['status'],'planned')
        t1=self.table.departures('r1','0','s1',now=self.now,realtime=self.state(relationship='CANCELED'))['departures'][0]
        self.assertEqual(t1['status'],'cancelled')


if __name__=='__main__':unittest.main()
