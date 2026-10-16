import importlib.util
import json
import tempfile
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path

spec = importlib.util.spec_from_file_location('gtfs', Path(__file__).parents[1] / 'tools/import_gtfs.py')
gtfs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gtfs)


class GTFSConversion(unittest.TestCase):
    def fixture(self, path, latitude='44.43'):
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('routes.txt', 'route_id,route_short_name,route_long_name,route_type\nr1,41,Test route,0\n')
            z.writestr('stops.txt', f'stop_id,stop_name,stop_lat,stop_lon\na,Stația A,{latitude},26.10\nb,"Stația B, test",44.44,26.11\nc,Stația C,44.45,26.12\n')
            z.writestr('trips.txt', 'route_id,trip_id,direction_id\nr1,t1,0\nr1,t2,1\n')
            z.writestr('stop_times.txt', 'trip_id,stop_id,stop_sequence\nt1,b,2\nt1,a,1\nt2,c,1\nt2,a,2\n')

    def test_directions_and_csv_quoting(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'feed.zip'
            self.fixture(path)
            result = gtfs.convert(path, 'Synthetic test fixture, not official')
            line = result['lines'][0]
            self.assertEqual(line['stops'], ['Stația A', 'Stația B, test'])
            self.assertEqual(line['reverseStops'], ['Stația C', 'Stația A'])
            self.assertEqual(line['coordinates'][0], [44.43, 26.1])
            self.assertEqual(line['number'], '41')
            self.assertEqual(line['type'], 'tram')

    def test_outside_region_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'feed.zip'
            self.fixture(path, '0')
            with self.assertRaises(ValueError):
                gtfs.convert(path, 'Test')

    def test_return_not_invented(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'feed.zip'
            self.fixture(path)
            with zipfile.ZipFile(path) as original:
                members = {name: original.read(name) for name in original.namelist()}
            members['trips.txt'] = b'route_id,trip_id,direction_id\nr1,t1,0\n'
            with zipfile.ZipFile(path, 'w') as z:
                for name, data in members.items():
                    z.writestr(name, data)
            self.assertNotIn('reverseStops', gtfs.convert(path, 'Test')['lines'][0])

    def test_runtime_preparation_is_repeatable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source.zip'
            self.fixture(source)
            script = Path(__file__).parents[1] / 'tools/prepare_transit.py'
            command = [sys.executable, str(script), '--directory', str(root / 'runtime'), '--zip', str(source)]
            first = subprocess.check_output(command, text=True).strip()
            catalog = (Path(first) / 'catalog.json').read_bytes()
            second = subprocess.check_output(command, text=True).strip()
            self.assertEqual(first, second)
            self.assertEqual(catalog, (Path(second) / 'catalog.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
