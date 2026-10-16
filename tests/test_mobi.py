from datetime import datetime, timezone
import json
import unittest
from mobi import decode, URL
from realtime import Realtime, StaticIndex, ENDPOINTS
from test_realtime import NOW, feed


def sample(point_time=NOW-5,vehicle_id=1,plate='B-001-STB',route='r1'):
    iso=datetime.fromtimestamp(point_time,timezone.utc).isoformat() if point_time else None
    return dict(id=123,timestamp=datetime.fromtimestamp(NOW,timezone.utc).isoformat(),src=4,vehicle=dict(
        trip=dict(route_id=route,trip_id='None',direction_id=0),vehicle=dict(id=vehicle_id,license_plate=plate),
        position=dict(latitude=44.43,longitude=26.1,timestamp=iso),passenger_info=dict(on_board=99)))


class MobiTests(unittest.TestCase):
    def setUp(self):
        self.index=StaticIndex();self.index.routes={'r1':{}};self.index.headsigns[('r1','0')]='Terminal'

    def test_fields_deduplication_and_no_occupancy(self):
        result=decode(json.dumps([sample(NOW-120),sample(NOW-5,vehicle_id=2,plate='B001STB')]),self.index,NOW)
        self.assertEqual(len(result['items']),1)
        item=result['items'][0]
        self.assertEqual(item['timestamp'],NOW-5);self.assertEqual(item['headsign'],'Terminal')
        self.assertEqual(item['direction'],'0');self.assertEqual(result['source'],'mobi')
        self.assertNotIn('passenger',json.dumps(result));self.assertNotIn('on_board',json.dumps(result))

    def test_conflicting_trip_direction_is_not_assigned(self):
        self.index.trips['t1']=dict(routeId='r1',direction='1',headsign='Other end')
        record=sample();record['vehicle']['trip']['trip_id']='t1'
        result=decode(json.dumps([record]),self.index,NOW)
        self.assertEqual(result['items'],[]);self.assertEqual(result['ignored'],1)

    def test_outer_timestamp_does_not_refresh_old_position(self):
        result=decode(json.dumps([sample(NOW-1000)]),self.index,NOW)
        self.assertEqual(result['timestamp'],NOW-1000)
        result=decode(json.dumps([sample(None)]),self.index,NOW)
        self.assertIsNone(result['timestamp'])

    def test_bad_route_coordinates_and_future_duplicates(self):
        invalid=sample();invalid['vehicle']['position']['latitude']=0
        result=decode(json.dumps([sample(NOW+1000),sample(NOW-5),sample(route='unknown'),invalid]),self.index,NOW)
        self.assertEqual(len(result['items']),1);self.assertEqual(result['items'][0]['timestamp'],NOW-5)
        self.assertEqual(result['ignored'],1);self.assertEqual(result['rejected'],1)
        for raw in [b'{}',b'<html>403</html>']:
            with self.assertRaises(ValueError):decode(raw,self.index,NOW)

    def test_primary_fallback_and_recovery(self):
        mode='good'
        def fetch(url):
            if url==URL:
                if mode=='error':raise OSError('offline')
                return json.dumps([sample(NOW-1000 if mode=='old' else NOW-5)]).encode()
            return feed(url.rsplit('/',1)[-1]).SerializeToString()
        service=Realtime(self.index,clock=lambda:NOW,fetch=fetch,mobi=True)
        service.refresh();state=service.snapshot()
        self.assertEqual(state['feeds']['vehiclePositions']['source'],'mobi')
        self.assertEqual(state['feeds']['tripUpdates']['status'],'fresh')
        for mode in ['error','old']:
            service.refresh();state=service.snapshot()
            self.assertEqual(state['feeds']['vehiclePositions']['source'],'gtfs')
            self.assertIn('fallbackReason',state['feeds']['vehiclePositions'])
        mode='good';service.refresh();self.assertEqual(service.snapshot()['feeds']['vehiclePositions']['source'],'mobi')


if __name__=='__main__':unittest.main()
