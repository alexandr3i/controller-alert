#!/usr/bin/env python3
"""Prepare a versioned runtime catalog outside the checkout, without replacing data."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import urllib.request
from import_gtfs import convert

SOURCE = 'https://gtfs.tpbi.ro/regional/BUCHAREST-REGION.zip'
MAX_BYTES = 64 * 1024 * 1024


def prepare(directory, source_zip=None):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='prepare-', dir=directory) as tmp:
        staging = Path(tmp)
        target_zip = staging / 'gtfs.zip'
        if source_zip:
            with Path(source_zip).open('rb') as stream:
                body = stream.read(MAX_BYTES + 1)
        else:
            request = urllib.request.Request(SOURCE, headers={'User-Agent': 'PeLinie/0.3 (GTFS client)'})
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError('GTFS ZIP exceeds 64 MB')
        digest = hashlib.sha256(body).hexdigest()
        version = directory / digest
        if version.exists():
            if not (version / 'gtfs.zip').is_file() or hashlib.sha256((version / 'gtfs.zip').read_bytes()).hexdigest() != digest:
                raise ValueError('Existing runtime ZIP is invalid; no files were overwritten')
            catalog = json.loads((version / 'catalog.json').read_text())
            if not catalog.get('lines') or catalog.get('version') != 1:
                raise ValueError('Existing runtime catalog is invalid; no files were overwritten')
            return version
        target_zip.write_bytes(body)
        catalog = convert(target_zip, SOURCE + (' · fișier local' if source_zip else ''))
        content = json.dumps(catalog, ensure_ascii=False)
        if len(content.encode()) > 10 * 1024 * 1024:
            raise ValueError('Converted catalog exceeds 10 MB')
        (staging / 'catalog.json').write_text(content, encoding='utf-8')
        # Move completed files only, preserving previous feed versions and their databases.
        completed = staging / 'completed'
        completed.mkdir()
        target_zip.rename(completed / 'gtfs.zip')
        (staging / 'catalog.json').rename(completed / 'catalog.json')
        completed.rename(version)
        return version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--zip', type=Path, help='Use a previously downloaded GTFS ZIP without a network request')
    args = parser.parse_args()
    print(prepare(args.directory, args.zip))


if __name__ == '__main__':
    main()
