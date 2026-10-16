#!/usr/bin/env python3
"""Optional same-origin development server for shared, anonymous reports.
Run behind HTTPS in a separately managed service; GitHub Pages cannot run Python.
"""
import argparse
import hashlib
from http import cookies
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sqlite3
import threading
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).parent
TTL = 45 * 60 * 1000


class Store:
    def __init__(self, path, catalog):
        self.catalog = catalog
        self.lines = {line['id']: line for line in catalog['lines']}
        self.lock = threading.Lock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.executescript('''CREATE TABLE IF NOT EXISTS reports
            (id TEXT PRIMARY KEY, owner TEXT, line TEXT, direction TEXT, stop TEXT, created INTEGER);
            CREATE TABLE IF NOT EXISTS votes (report TEXT, voter TEXT, PRIMARY KEY(report,voter));
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT);''')
        fingerprint = hashlib.sha256(json.dumps(catalog, sort_keys=True).encode()).hexdigest()
        previous = self.db.execute("SELECT value FROM metadata WHERE key='catalog'").fetchone()
        if previous and previous[0] != fingerprint:
            self.db.close()
            raise ValueError('Catalog changed; choose a new database path. Existing reports were preserved.')
        self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('catalog',?)", (fingerprint,))
        self.db.commit()
        self.limits = {}
        self.salt = secrets.token_bytes(32)

    def run(self, owner, action, data):
        with self.lock:
            now = int(time.time() * 1000)
            self.db.execute('DELETE FROM reports WHERE created <= ?', (now - TTL,))
            self.db.execute('DELETE FROM votes WHERE report NOT IN (SELECT id FROM reports)')
            if action == 'create':
                line = self.lines.get(data.get('line'))
                direction = data.get('direction')
                names = line.get('reverseStops', []) if line and direction == 'reverse' else line.get('stops', []) if line else []
                if not line or direction not in ('forward', 'reverse') or data.get('stop') not in names:
                    raise ValueError('Linie, sens sau stație invalidă.')
                count = self.db.execute('SELECT count(*) FROM reports WHERE owner=? AND created>?', (owner, now - 600000)).fetchone()[0]
                if count >= 3:
                    raise ValueError('Maximum 3 raportări în 10 minute.')
                self.db.execute('INSERT INTO reports VALUES (?,?,?,?,?,?)', (secrets.token_urlsafe(16), owner, data['line'], direction, data['stop'], now))
            elif action in ('vote', 'delete'):
                row = self.db.execute('SELECT owner FROM reports WHERE id=?', (data.get('id'),)).fetchone()
                if not row:
                    raise ValueError('Raportarea a expirat sau nu există.')
                if action == 'delete':
                    if row[0] != owner:
                        raise PermissionError('Poți șterge doar raportările proprii.')
                    self.db.execute('DELETE FROM reports WHERE id=?', (data['id'],))
                    self.db.execute('DELETE FROM votes WHERE report=?', (data['id'],))
                elif data.get('voted') is True:
                    self.db.execute('INSERT OR IGNORE INTO votes VALUES (?,?)', (data['id'], owner))
                else:
                    self.db.execute('DELETE FROM votes WHERE report=? AND voter=?', (data['id'], owner))
            self.db.commit()
            rows = self.db.execute('''SELECT r.id,r.owner,r.line,r.direction,r.stop,r.created,
                (SELECT count(*) FROM votes WHERE report=r.id),
                (SELECT count(*) FROM votes WHERE report=r.id AND voter=?)
                FROM reports r ORDER BY r.created DESC LIMIT 1000''', (owner,)).fetchall()
            return [dict(id=r[0], canDelete=r[1] == owner, line=r[2], direction=r[3], stop=r[4], createdAt=r[5], confirmations=r[6], voted=bool(r[7]), shared=True) for r in rows]


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, *args):
        pass  # Do not log client addresses or report contents.

    def send_json(self, value, code=200):
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(body)))
        if getattr(self, 'new_cookie', False):
            secure = '; Secure' if self.server.secure else ''
            self.send_header('Set-Cookie', f'pelinie_session={self.session}; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400{secure}')
        self.end_headers()
        self.wfile.write(body)

    def identity(self):
        jar = cookies.SimpleCookie()
        try:
            jar.load(self.headers.get('Cookie', ''))
        except cookies.CookieError:
            pass
        item = jar.get('pelinie_session')
        token = item.value if item else ''
        self.new_cookie = len(token) != 43 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in token)
        self.session = secrets.token_urlsafe(32) if self.new_cookie else token
        return hashlib.sha256(self.session.encode()).hexdigest()

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/realtime':
            realtime = getattr(self.server, 'realtime', None)
            return self.send_json(realtime.snapshot() if realtime else {'enabled': False})
        if path == '/api/catalog':
            self.identity()
            return self.send_json(self.server.store.catalog)
        if path == '/api/reports':
            return self.send_json(self.server.store.run(self.identity(), 'list', {}))
        allowed = path in ('/', '/index.html', '/app.js', '/transit.js', '/styles.css', '/live.js', '/data/catalog.json') or path.startswith('/vendor/leaflet/') and '..' not in path and '%' not in path
        if not allowed:
            return self.send_json({'error': 'Not found'}, 404)
        super().do_GET()

    def do_HEAD(self):
        self.send_json({'error': 'Method not supported'}, 405)

    def do_POST(self):
        if urlsplit(self.path).path != '/api/reports':
            return self.send_json({'error': 'Not found'}, 404)
        # Browser writes must be same origin; JSON requests cannot be submitted by HTML forms.
        origin = self.headers.get('Origin')
        if origin and origin != self.server.public_origin:
            return self.send_json({'error': 'Origine nepermisă.'}, 403)
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.send_json({'error': 'JSON required'}, 415)
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 2048:
                return self.send_json({'error': 'Invalid body size'}, 413)
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict) or data.get('action') not in ('create', 'vote', 'delete'):
                raise ValueError('Acțiune invalidă.')
            if any(key in data and not isinstance(data[key], str) for key in ('id', 'line', 'direction', 'stop')):
                raise ValueError('Câmp invalid.')
            # Address hashes retained only in RAM for one minute, never logged or persisted.
            store = self.server.store
            key = hashlib.sha256(store.salt + self.client_address[0].encode()).digest()
            minute = int(time.time() // 60)
            with store.lock:
                store.limits = {k: v for k, v in store.limits.items() if v[0] == minute}
                count = store.limits.get(key, (minute, 0))[1]
                if count >= 30:
                    return self.send_json({'error': 'Prea multe cereri. Reîncearcă într-un minut.'}, 429)
                store.limits[key] = (minute, count + 1)
            return self.send_json(store.run(self.identity(), data['action'], data))
        except PermissionError as error:
            self.send_json({'error': str(error)}, 403)
        except (ValueError, TypeError, KeyError) as error:
            self.send_json({'error': str(error)}, 400)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data', type=Path, required=True, help='Converted GTFS JSON, same catalog for all clients')
    p.add_argument('--db', type=Path, default=Path('/tmp/pelinie-reports.sqlite3'))
    p.add_argument('--port', type=int, default=8000)
    p.add_argument('--bind', default='127.0.0.1')
    p.add_argument('--public-origin', help='Exact HTTPS origin of a reverse proxy; also enables Secure cookies')
    realtime_group = p.add_mutually_exclusive_group()
    realtime_group.add_argument('--realtime', action='store_true', help='Poll all three public TPBI endpoints every 30 seconds')
    realtime_group.add_argument('--realtime-snapshots', type=Path, help='Offline replay directory; always labeled snapshot, never live')
    p.add_argument('--gtfs', type=Path, help='Original GTFS ZIP for trip directions and stop names')
    p.add_argument('--poll-seconds', type=int, default=30, help='Minimum 30; respect provider limits')
    args = p.parse_args()
    catalog = json.loads(args.data.read_text(encoding='utf-8'))
    if catalog.get('version') != 1 or not catalog.get('lines'):
        p.error('Invalid catalog')
    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    server.secure = bool(args.public_origin and args.public_origin.startswith('https://'))
    server.public_origin = args.public_origin or f'http://{args.bind}:{args.port}'
    server.store = Store(args.db, catalog)
    server.realtime = None
    if args.realtime or args.realtime_snapshots:
        try:
            from realtime import Realtime, StaticIndex
        except ImportError:
            p.error('Install optional realtime dependencies: python3 -m pip install -r requirements.txt')
        server.realtime = Realtime(StaticIndex(args.gtfs), interval=args.poll_seconds, snapshots=args.realtime_snapshots)
        server.realtime.start()
    print(f'PeLinie server on port {args.port}; reports expire after 45 minutes', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if server.realtime:
            server.realtime.close()
        server.server_close()
        server.store.db.close()


if __name__ == '__main__':
    main()
