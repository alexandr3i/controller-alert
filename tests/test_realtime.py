import json
from pathlib import Path
import tempfile
import unittest
from google.transit import gtfs_realtime_pb2 as gtfs
from realtime import Realtime, StaticIndex, decode, fresh, alert_active

NOW = 1800000000


def feed(kind):
    result = gtfs.FeedMessage()
    result.header.gtfs_realtime_version = '2.0'
    result.header.timestamp = NOW
    entity = result.entity.add(id='entity1')
    if kind == 'vehiclePositions':
        v = entity.vehicle
        v.trip.route_id = 'r1'
        v.trip.trip_id = 't1'
        v.timestamp = NOW - 10
        v.position.latitude = 44.43
        v.position.longitude = 26.1
    elif kind == 'tripUpdates':
        u = entity.trip_update
        u.trip.route_id = 'r1'
        u.trip.trip_id = 't1'
        u.timestamp = NOW - 5
        stop = u.stop_time_update.add(stop_id='s1', stop_sequence=1)
        stop.arrival.time = NOW + 120
        stop.arrival.delay = 60
    else:
        a = entity.alert
        a.header_text.translation.add(text='<script>not HTML</script>', language='en')
        a.header_text.translation.add(text='Stație mutată', language='ro')
        a.description_text.translation.add(text='Alege stația temporară.', language='ro')
        a.informed_entity.add(route_id='r1', agency_id='1')
        a.active_period.add(start=NOW - 60, end=NOW + 600)
    return result


class RealtimeTests(unittest.TestCase):
    def setUp(self):
        self.now = NOW
        self.index = StaticIndex()
        self.index.trips['t1'] = dict(routeId='r1', direction='1', headsign='Destinație')
        self.index.stops['s1'] = 'Stația A'
        self.fail = set()
        def fetch(url):
            name = url.rsplit('/', 1)[1]
            if name in self.fail:
                raise OSError('network down')
            return feed(name).SerializeToString()
        self.service = Realtime(self.index, clock=lambda: self.now, fetch=fetch)

    def test_decode_positions_and_static_matching(self):
        f = feed('vehiclePositions')
        f.entity[0].vehicle.trip.ClearField('route_id')
        item = decode('vehiclePositions', f.SerializeToString(), self.index)['items'][0]
        self.assertEqual(item['routeId'], 'r1')
        self.assertEqual(item['direction'], '1')
        self.assertAlmostEqual(item['latitude'], 44.43, places=4)

    def test_predictions_and_alert_translations(self):
        item = decode('tripUpdates', feed('tripUpdates').SerializeToString(), self.index)['items'][0]
        self.assertEqual(item['stops'][0]['stopName'], 'Stația A')
        self.assertEqual(item['stops'][0]['arrival'], NOW + 120)
        item = decode('serviceAlerts', feed('serviceAlerts').SerializeToString(), self.index)['items'][0]
        self.assertEqual(item['header'], 'Stație mutată')
        self.assertEqual(item['selectors'][0]['agencyId'], '1')
        self.assertTrue(alert_active(item, NOW))
        self.assertFalse(alert_active(item, NOW + 600))

    def test_missing_coordinates_timestamp_and_future(self):
        f = feed('vehiclePositions')
        f.entity[0].vehicle.ClearField('position')
        with self.assertRaises(ValueError):
            decode('vehiclePositions', f.SerializeToString(), self.index)
        self.assertFalse(fresh(None, NOW))
        self.assertFalse(fresh(NOW + 121, NOW))
        f = feed('vehiclePositions')
        f.entity[0].vehicle.ClearField('timestamp')
        self.service.fetch = lambda url: f.SerializeToString() if url.endswith('vehiclePositions') else feed(url.rsplit('/', 1)[1]).SerializeToString()
        self.service.refresh()
        self.assertTrue(self.service.snapshot()['feeds']['vehiclePositions']['items'][0]['stale'])

    def test_cache_ages_and_partial_failures(self):
        self.service.refresh()
        self.assertEqual(self.service.snapshot()['feeds']['vehiclePositions']['status'], 'fresh')
        self.now += 181
        old = self.service.snapshot()['feeds']['vehiclePositions']
        self.assertEqual(old['status'], 'stale')
        self.assertTrue(old['items'][0]['stale'])
        self.now = NOW
        self.fail.add('vehiclePositions')
        self.service.refresh()
        feeds = self.service.snapshot()['feeds']
        self.assertEqual(feeds['vehiclePositions']['status'], 'error')
        self.assertEqual(feeds['vehiclePositions']['receivedAt'], NOW)
        self.assertEqual(len(feeds['vehiclePositions']['items']), 1)
        self.assertTrue(feeds['vehiclePositions']['items'][0]['stale'])
        self.assertEqual(feeds['tripUpdates']['status'], 'fresh')
        self.fail.clear()
        self.service.refresh()
        self.assertEqual(self.service.snapshot()['feeds']['vehiclePositions']['status'], 'fresh')

    def test_invalid_and_differential_feed_rejected(self):
        for raw in [b'<html>403 forbidden</html>', b'']:
            with self.assertRaises(ValueError):
                decode('vehiclePositions', raw, self.index)
        f = feed('vehiclePositions')
        f.header.incrementality = gtfs.FeedHeader.DIFFERENTIAL
        with self.assertRaises(ValueError):
            decode('vehiclePositions', f.SerializeToString(), self.index)

    def test_empty_full_feed_clears_cache(self):
        self.service.refresh()
        f = feed('vehiclePositions')
        del f.entity[:]
        self.service.fetch = lambda url: f.SerializeToString()
        self.service.refresh_one('vehiclePositions')
        self.assertEqual(self.service.snapshot()['feeds']['vehiclePositions']['items'], [])

    def test_snapshot_never_claims_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            for kind in self.service.feeds:
                (Path(tmp) / kind).write_bytes(feed(kind).SerializeToString())
            replay = Realtime(self.index, clock=lambda: NOW, snapshots=tmp)
            replay.refresh()
            state = replay.snapshot()
            self.assertEqual(state['mode'], 'snapshot')
            self.assertEqual(state['feeds']['vehiclePositions']['status'], 'snapshot')
            self.assertTrue(state['feeds']['vehiclePositions']['items'][0]['stale'])


if __name__ == '__main__':
    unittest.main()
