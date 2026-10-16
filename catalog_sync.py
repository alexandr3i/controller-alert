"""Refresh static GTFS independently of the 30-second realtime poller."""
import json
from pathlib import Path
import threading
import time
from tools.prepare_transit import prepare
from realtime import StaticIndex
from timetable import Timetable


class CatalogSync:
    def __init__(self,server,directory,*,interval=21600,prepare_feed=prepare):
        self.server=server;self.directory=Path(directory);self.interval=interval;self.prepare_feed=prepare_feed
        self.stop=threading.Event();self.thread=None
        self.status=dict(checkedAt=int(time.time()),error=None,intervalSeconds=interval)

    def refresh(self):
        try:
            version=self.prepare_feed(self.directory)
            catalog=json.loads((version/'catalog.json').read_text())
            if catalog.get('revision') != self.server.store.catalog.get('revision'):
                index=StaticIndex(version/'gtfs.zip');table=Timetable(version/'gtfs.zip')
                with self.server.transit_lock:
                    self.server.store.replace_catalog(catalog)
                    self.server.timetable=table
                    if self.server.realtime:self.server.realtime.replace_index(index)
            with self.server.transit_lock:self.status.update(checkedAt=int(time.time()),error=None)
        except Exception:
            with self.server.transit_lock:self.status.update(checkedAt=int(time.time()),error='Actualizarea GTFS a eșuat; se păstrează ultima versiune validă.')

    def start(self):
        def run():
            while not self.stop.wait(self.interval):self.refresh()
        self.thread=threading.Thread(target=run,daemon=True,name='gtfs-catalog-sync');self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread:self.thread.join(timeout=1)
