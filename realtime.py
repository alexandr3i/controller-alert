"""Cached TPBI GTFS-Realtime ingestion. No client-supplied URLs or credentials."""
import concurrent.futures
import copy
import csv
import io
import math
from pathlib import Path
import threading
import time
import urllib.error
import urllib.request
from zipfile import ZipFile

from google.protobuf.message import DecodeError
from google.transit import gtfs_realtime_pb2 as gtfs

ENDPOINTS = {name: 'https://gtfs.tpbi.ro/api/gtfs-rt/' + name for name in
             ('vehiclePositions', 'tripUpdates', 'serviceAlerts')}
MAX_BYTES = 16 * 1024 * 1024
STALE_SECONDS = 180
FUTURE_TOLERANCE = 120


def fresh(timestamp, now):
    return bool(timestamp and -FUTURE_TOLERANCE <= now - timestamp <= STALE_SECONDS)


def translation(value):
    choices = list(value.translation)
    for language in ('ro', 'en'):
        for item in choices:
            if item.language.split('-')[0].lower() == language:
                return item.text[:4000]
    return choices[0].text[:4000] if choices else ''


class StaticIndex:
    def __init__(self, path=None):
        self.trips = {}
        self.stops = {}
        if path:
            with ZipFile(path) as archive:
                if sum(i.file_size for i in archive.infolist()) > 512 * 1024 * 1024:
                    raise ValueError('GTFS decompressed size exceeds 512 MB')
                def rows(name):
                    with archive.open(name) as stream:
                        yield from csv.DictReader(io.TextIOWrapper(stream, encoding='utf-8-sig'))
                self.trips = {r['trip_id']: dict(routeId=r['route_id'], direction=r.get('direction_id') or None,
                                               headsign=r.get('trip_headsign', '')) for r in rows('trips.txt')}
                self.stops = {r['stop_id']: r['stop_name'] for r in rows('stops.txt')}

    def trip(self, value):
        reference = self.trips.get(value.trip_id, {})
        return dict(tripId=value.trip_id, routeId=value.route_id or reference.get('routeId', ''),
                    direction=str(value.direction_id) if value.HasField('direction_id') else reference.get('direction'),
                    headsign=reference.get('headsign', ''),
                    relationship=gtfs.TripDescriptor.ScheduleRelationship.Name(value.schedule_relationship))


def decode(name, payload, index):
    feed = gtfs.FeedMessage()
    try:
        feed.ParseFromString(payload)
    except DecodeError as error:
        raise ValueError('Răspuns GTFS-Realtime invalid.') from error
    if not feed.IsInitialized() or feed.header.gtfs_realtime_version not in ('1.0', '2.0'):
        raise ValueError('Antet GTFS-Realtime invalid sau nesuportat.')
    if feed.header.incrementality != gtfs.FeedHeader.FULL_DATASET:
        raise ValueError('Flux diferențial nesuportat; este necesar FULL_DATASET.')
    items, rejected, ignored = [], 0, 0
    for entity in feed.entity:
        if entity.is_deleted:
            continue
        if name == 'vehiclePositions' and entity.HasField('vehicle'):
            vehicle = entity.vehicle
            if not vehicle.HasField('position') or not all(math.isfinite(v) for v in (vehicle.position.latitude, vehicle.position.longitude)) or not (43 <= vehicle.position.latitude <= 46 and 24 <= vehicle.position.longitude <= 28):
                rejected += 1
                continue
            items.append(dict(id=entity.id, **index.trip(vehicle.trip), latitude=vehicle.position.latitude,
                              longitude=vehicle.position.longitude, timestamp=int(vehicle.timestamp) or None))
        elif name == 'tripUpdates' and entity.HasField('trip_update'):
            update = entity.trip_update
            stops = []
            for stop in update.stop_time_update:
                arrival = int(stop.arrival.time) if stop.HasField('arrival') and stop.arrival.HasField('time') else None
                departure = int(stop.departure.time) if stop.HasField('departure') and stop.departure.HasField('time') else None
                event = stop.arrival if arrival else stop.departure
                stops.append(dict(stopId=stop.stop_id, stopName=index.stops.get(stop.stop_id, stop.stop_id),
                                  sequence=int(stop.stop_sequence), arrival=arrival, departure=departure,
                                  delay=int(event.delay) if event.HasField('delay') else None,
                                  uncertainty=int(event.uncertainty) if event.HasField('uncertainty') else None,
                                  relationship=gtfs.TripUpdate.StopTimeUpdate.ScheduleRelationship.Name(stop.schedule_relationship)))
            items.append(dict(id=entity.id, **index.trip(update.trip),
                              timestamp=int(update.timestamp) or int(feed.header.timestamp) or None, stops=stops))
        elif name == 'serviceAlerts' and entity.HasField('alert'):
            alert = entity.alert
            # Keep each selector intact: fields inside one selector intersect, selectors unite.
            selectors = [dict(routeId=s.route_id or s.trip.route_id or index.trips.get(s.trip.trip_id, {}).get('routeId', ''),
                              tripId=s.trip.trip_id, stopId=s.stop_id, agencyId=s.agency_id,
                              routeType=int(s.route_type) if s.HasField('route_type') else None,
                              direction=str(s.direction_id) if s.HasField('direction_id') else None)
                         for s in alert.informed_entity]
            items.append(dict(id=entity.id, header=translation(alert.header_text), description=translation(alert.description_text),
                              cause=gtfs.Alert.Cause.Name(alert.cause), effect=gtfs.Alert.Effect.Name(alert.effect),
                              periods=[dict(start=int(p.start) if p.HasField('start') else None,
                                            end=int(p.end) if p.HasField('end') else None) for p in alert.active_period],
                              selectors=selectors))
        else:
            ignored += 1
    if feed.entity and not items and (rejected or ignored):
        raise ValueError('Fluxul nu conține entități utilizabile pentru acest endpoint.')
    return dict(timestamp=int(feed.header.timestamp) or None, items=items, rejected=rejected, ignored=ignored)


def download(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'PeLinie/0.3 (GTFS-Realtime client)',
                                                  'Accept': 'application/x-protobuf, application/octet-stream'})
    with urllib.request.urlopen(request, timeout=10) as response:
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError('Fluxul depășește limita de 16 MB.')
    return body


def alert_active(item, now):
    return not item['periods'] or any((p['start'] is None or p['start'] <= now) and
                                    (p['end'] is None or now < p['end']) for p in item['periods'])


class Realtime:
    def __init__(self, index=None, *, interval=30, fetch=download, clock=time.time, snapshots=None):
        self.index = index or StaticIndex()
        self.interval = max(30, interval)
        self.fetch = fetch
        self.clock = clock
        self.snapshots = Path(snapshots) if snapshots else None
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.thread = None
        self.feeds = {name: dict(timestamp=None, items=[], rejected=0, ignored=0, error=None,
                                 attemptedAt=None, receivedAt=None) for name in ENDPOINTS}

    def refresh_one(self, name):
        attempted = int(self.clock())
        try:
            payload = (self.snapshots / name).read_bytes() if self.snapshots else self.fetch(ENDPOINTS[name])
            if len(payload) > MAX_BYTES:
                raise ValueError('Fluxul depășește limita de 16 MB.')
            decoded = decode(name, payload, self.index)
            result = dict(**decoded, error=None, attemptedAt=attempted, receivedAt=int(self.clock()))
            with self.lock:
                self.feeds[name] = result
        except (OSError, ValueError, urllib.error.URLError) as error:
            message = f'HTTP {error.code}' if isinstance(error, urllib.error.HTTPError) else 'Sursa nu răspunde sau datele sunt invalide.'
            with self.lock:
                self.feeds[name].update(error=message, attemptedAt=attempted)

    def refresh(self):
        # Three requests per cycle, shared by every browser; GET /api/realtime never calls TPBI.
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(self.refresh_one, ENDPOINTS))

    def start(self):
        def run():
            while not self.stop.is_set():
                began = time.monotonic()
                self.refresh()
                if self.snapshots:
                    return
                self.stop.wait(max(0, self.interval - (time.monotonic() - began)))
        self.thread = threading.Thread(target=run, name='tpbi-realtime', daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=12)

    def snapshot(self):
        now = int(self.clock())
        with self.lock:
            feeds = copy.deepcopy(self.feeds)
        for name, value in feeds.items():
            if value['receivedAt'] is None:
                value['status'] = 'error' if value['error'] else 'loading'
            elif self.snapshots:
                value['status'] = 'snapshot'
            elif value['error']:
                value['status'] = 'error'
            else:
                value['status'] = 'fresh' if fresh(value['timestamp'], now) else 'stale'
            for item in value['items']:
                item['stale'] = value['status'] != 'fresh' or not fresh(item.get('timestamp', value['timestamp']), now)
                if name == 'serviceAlerts':
                    item['active'] = alert_active(item, now)
        return dict(enabled=True, mode='snapshot' if self.snapshots else 'live', generatedAt=now,
                    pollSeconds=self.interval, staleSeconds=STALE_SECONDS, feeds=feeds)
