#!/usr/bin/env python3
"""Convert a lawfully obtained GTFS ZIP to the browser's local import format.
No network requests; no claim of official provenance. Python standard library only.
"""
import argparse
import csv
import io
import json
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from zipfile import BadZipFile, ZipFile


def convert(path, source):
    with ZipFile(path) as archive:
        if sum(i.file_size for i in archive.infolist()) > 512 * 1024 * 1024:
            raise ValueError('GTFS decompressed size exceeds 512 MB')

        def rows(name):
            with archive.open(name) as stream:
                yield from csv.DictReader(io.TextIOWrapper(stream, encoding='utf-8-sig', newline=''))

        stops = {r['stop_id']: r for r in rows('stops.txt')}
        routes = {r['route_id']: r for r in rows('routes.txt') if r['route_type'] in ('0', '1', '3', '11', '700', '800', '900')}
        trip_rows = {r['trip_id']: r for r in rows('trips.txt') if r['route_id'] in routes}
        trips = {key: (r['route_id'], r.get('direction_id', '0') or '0') for key,r in trip_rows.items()}
        sequences = {}
        for row in rows('stop_times.txt'):
            if row['trip_id'] in trips and row['stop_id'] in stops:
                sequences.setdefault(row['trip_id'], []).append((int(row['stop_sequence']), row['stop_id']))
        # Pick one longest trip for each route/direction, never infer a return path.
        patterns = {}
        variants = {}
        for trip_id, seq in sequences.items():
            key = trips[trip_id]
            seq = sorted(seq)
            signature = (key[0], key[1], tuple(sid for _,sid in seq))
            variants.setdefault(signature, (seq, trip_rows[trip_id].get('shape_id'), trip_rows[trip_id].get('trip_headsign','')))
            if key not in patterns or len(seq) > len(patterns[key]):
                patterns[key] = sorted(seq)

        def pattern(seq):
            items = [stops[stop_id] for _, stop_id in seq]
            points = [[float(r['stop_lat']), float(r['stop_lon'])] for r in items]
            if any(not (43 <= lat <= 46 and 24 <= lon <= 28) for lat, lon in points):
                raise ValueError('Coordinates outside Bucharest–Ilfov region')
            return [r['stop_name'] for r in items], points

        needed_shapes = {shape for _,shape,_ in variants.values() if shape}
        shapes = {}
        if 'shapes.txt' in archive.namelist():
            for row in rows('shapes.txt'):
                if row['shape_id'] in needed_shapes:
                    point = [round(float(row['shape_pt_lat']),6),round(float(row['shape_pt_lon']),6)]
                    if 43 <= point[0] <= 46 and 24 <= point[1] <= 28:
                        shapes.setdefault(row['shape_id'], []).append((int(row['shape_pt_sequence']),point))
        shapes = {key:[p for _,p in sorted(value)] for key,value in shapes.items()}
        lines = []
        for route_id, route in sorted(routes.items()):
            available = sorted((direction, seq) for (rid, direction), seq in patterns.items() if rid == route_id)
            if not available:
                continue
            names, points = pattern(available[0][1])
            kind = 'metro' if route['route_type']=='1' else 'tram' if route['route_type'] in ('0', '900') else 'trolley' if route['route_type'] in ('11', '800') else 'bus'
            line = dict(id=route_id, agencyId=route.get('agency_id', ''), routeType=int(route['route_type']), directionIds=[d for d, _ in available[:2]], stopIds=[sid for _, sid in available[0][1]], number=route.get('route_short_name') or route_id, label=f"{route.get('route_short_name') or route_id} · {route.get('route_long_name') or names[0] + ' → ' + names[-1]}", type=kind, stops=names, coordinates=points)
            if len(available) > 1:
                line['reverseStops'], line['reverseCoordinates'] = pattern(available[1][1])
                line['reverseStopIds'] = [sid for _, sid in available[1][1]]
            line['variants'] = []
            for (rid,direction,ids),(seq,shape,headsign) in variants.items():
                if rid != route_id: continue
                vn,vc = pattern(seq)
                geometry = shapes.get(shape, [])
                # Keep source geometry; Leaflet simplifies rendering without changing the data.
                variant = dict(id=hashlib.sha256((direction+'|'+','.join(ids)).encode()).hexdigest()[:16],direction=direction,headsign=headsign,stops=vn,stopIds=list(ids),coordinates=vc)
                if len(geometry) > 1: variant['geometry'] = geometry
                line['variants'].append(variant)
            line['variants'].sort(key=lambda v:(v['direction'],-len(v['stops']),v['id']))
            for slot,direction in enumerate(line['directionIds']):
                chosen = next(v for v in line['variants'] if v['direction']==direction)
                if chosen.get('geometry'): line['reverseGeometry' if slot else 'geometry'] = chosen['geometry']
            lines.append(line)
        if not lines:
            raise ValueError('No supported transit routes with stops found')
        if len(lines) > 1000:
            raise ValueError('More than 1000 routes; select a regional feed')
        if any(len(line['stops']) > 500 or len(line.get('reverseStops', [])) > 500 for line in lines):
            raise ValueError('Route exceeds 500 stops')
        lines.sort(key=lambda line:[(0,int(x)) if x.isdigit() else (1,x.casefold()) for x in re.split(r'(\d+)',line['number']) if x])
        return dict(schemaVersion=2,version=1, source=source, importedAt=datetime.now(timezone.utc).isoformat(), lines=lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('zip', type=Path)
    parser.add_argument('--source', required=True, help='Source URL/name; check reuse terms yourself')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if not args.source.strip() or len(args.source) > 500:
        parser.error('source must contain 1–500 characters')
    try:
        data = convert(args.zip, args.source)
        text = json.dumps(data, ensure_ascii=False)
        if len(text.encode()) > 10 * 1024 * 1024:
            raise ValueError('Output exceeds browser import limit (10 MB)')
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(text)
    except (ValueError, KeyError, OSError, BadZipFile) as error:
        parser.exit(1, f'Import failed: {error}\n')
    print(f"Converted {len(data['lines'])} routes to {args.output}")


if __name__ == '__main__':
    main()
