import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from zipfile import ZipFile
from catalog_sync import CatalogSync
from server import Store


class CatalogTests(unittest.TestCase):
    def test_swap_preserves_reports_and_failure_preserves_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            old={'version':1,'revision':'old','lines':[{'id':'r1','stops':['A'],'stopIds':['s1'],'coordinates':[[44.43,26.1]]}]}
            new={**old,'revision':'new'}
            (root/'catalog.json').write_text(json.dumps(new))
            with ZipFile(root/'gtfs.zip','w') as z:
                z.writestr('trips.txt','route_id,service_id,trip_id,direction_id\nr1,s,t1,0\n')
                z.writestr('stops.txt','stop_id,stop_name\ns1,A\n')
                z.writestr('stop_times.txt','trip_id,stop_id,stop_sequence,departure_time\nt1,s1,1,08:00:00\n')
            store=Store(root/'reports.sqlite3',old)
            report=store.run('owner','create',{'line':'r1','direction':'forward','stop':'A','stopId':'s1'})[0]
            server=SimpleNamespace(store=store,realtime=SimpleNamespace(replace_index=lambda index:None),transit_lock=threading.RLock(),timetable=None)
            sync=CatalogSync(server,root,prepare_feed=lambda path:root)
            sync.refresh()
            self.assertEqual(server.store.catalog['revision'],'new')
            self.assertEqual(store.run('owner','list',{})[0]['id'],report['id'])
            self.assertIsNotNone(server.timetable)
            def fail(path):raise OSError('network down')
            sync.prepare_feed=fail;sync.refresh()
            self.assertIsNotNone(sync.status['error']);self.assertEqual(store.catalog['revision'],'new')
            store.db.close()


if __name__=='__main__':unittest.main()
