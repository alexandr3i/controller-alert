# PeLinie — București

Aplicație web pentru explorarea transportului și raportări comunitare privind prezența unui control, fără identificarea sau urmărirea individuală a angajaților. Interfață în română, adaptată pentru telefon. Experiment independent, neafiliat STB/TPBI; nu înlocuiește validarea titlului de călătorie.

## Ce funcționează în v0.2

- Hartă interactivă Leaflet / OpenStreetMap, cu atribuire; fără solicitarea locației utilizatorului.
- Cinci linii **demonstrative**. Nu sunt desenate pe hartă deoarece coordonatele nu au fost verificate.
- Import local al unui catalog convertit din GTFS: stații cu coordonate și sensuri separate. Liniile punctate **unesc stațiile**, nu reprezintă geometria reală a străzilor. Convertorul alege cursa cu cele mai multe stații pentru fiecare sens; alte variante și calendarul de circulație nu sunt afișate.
- Căutare, filtre, schimbarea sensului, raportare, confirmare, ștergere și expirare după 45 de minute.
- Două moduri: static (raportări numai în browser) sau server opțional (raportări comune utilizatorilor acelui server).
- CSS și JavaScript separate, teste de conversie, validare și raportări.

**Nu există încă poziții live ale vehiculelor.** În mediul de dezvoltare, accesul la STB/TPBI a răspuns cu 403 de la proxy. Nu am verificat un endpoint oficial de poziții, licența, frecvența, acoperirea sau dreptul de republicare. Nu folosim endpoint-uri private și nu prezentăm date demonstrative ca date live. Sursa dintr-un fișier importat este declarată de operator/utilizator, nu certificată de aplicație.

## Rulare statică — fără instalări sau build

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Rulează din rădăcina repository-ului, apoi deschide pagina servită în browser. Python este doar serverul local; GitHub Pages nu are nevoie de el. Leaflet 1.9.4 este inclus în `vendor/leaflet`, cu licența upstream; tarball-ul npm a fost verificat SHA-512. Fundalul hărții necesită acces la `tile.openstreetmap.org`; la eroare apare un mesaj, iar datele importate rămân accesibile. Respectă [politica tile-urilor OSM](https://operations.osmfoundation.org/policies/tiles/); pentru trafic mare trebuie ales un furnizor adecvat. Nu descărcăm harta pentru utilizare offline.

## Import GTFS

Obține legal un ZIP GTFS pentru București–Ilfov și verifică termenii sursei. Aplicația nu descarcă automat date de la STB/TPBI și nu include date oficiale neverificate.

```sh
python3 tools/import_gtfs.py /cale/transport.zip --source 'URL-ul sau numele sursei reale' --output /tmp/trasee.json
```

Convertorul folosește numai biblioteca standard Python și `routes.txt`, `stops.txt`, `trips.txt`, `stop_times.txt`. Nu suprascrie un fișier existent. Importă apoi JSON-ul prin controlul de deasupra hărții. Importul rămâne în memorie și se repetă după reîncărcare. Fișierele nu sunt trimise unui server. Limite: ZIP decomprimat 512 MB, JSON 10 MB, 1000 linii și 500 stații pe sens. Sunt acceptate tramvaie, autobuze și troleibuze; nu există rutare sau estimări de sosire. Un sens lipsă nu este inventat prin inversarea celuilalt. Coordonatele sunt limitate la regiunea București–Ilfov.

## Raportări comune — server opțional

GitHub Pages **nu rulează backend-ul**. Pentru a testa partajarea pe același serviciu:

```sh
python3 server.py --data /tmp/trasee.json --db /tmp/pelinie.sqlite3 --port 8001
```

Serverul servește aceeași interfață și catalogul comun; aplicația detectează API-ul și schimbă explicit salvarea locală în publicarea comunitară. Poți testa cu două browsere sau contexte independente. Importarea manuală a altui catalog sau revenirea la exemple dezactivează modul comunitar în acel tab. Reîncărcarea reconectează catalogul serverului.

Raportările sunt anonime și neverificate. Nu sunt solicitate nume, fotografii, text liber, GPS sau identitatea angajaților. O sesiune cookie `HttpOnly; SameSite=Strict` permite ștergerea propriilor raportări și o singură confirmare per raportare. Limite: 3 raportări/10 minute/sesiune și 30 operații de scriere/minut/adresă. Pentru această limită, un hash al adresei este păstrat doar în RAM timp de un minut; adresele și cookie-urile nu sunt jurnalizate. Pierderea cookie-ului pierde accesul la ștergerea proprie. Datele expirate sunt eliminate la următoarea cerere API. Resetarea datelor locale nu șterge raportările publicate; acestea se șterg individual. Raportările și confirmările sunt păstrate în SQLite la repornire și expiră normal. Schimbarea catalogului necesită o bază de date separată; serverul refuză asocierea unei baze existente cu alt catalog, fără să șteargă datele.

Acesta este un backend de prototip, cu limite ocolibile prin sesiuni noi; nu are autentificare, moderare, administrare sau protecție anti-abuz suficientă pentru o lansare largă. Pentru găzduire publică sunt necesare un serviciu Python separat, HTTPS, limite la proxy și moderare. Rulează un singur proces, cu baza de date în afara directorului public. În spatele unui reverse proxy folosește `--public-origin https://domeniul-tau` pentru verificarea originii și cookie Secure. Nu există CORS deschis; interfața și API-ul trebuie servite de la aceeași origine. Nu este încă configurat un hosting public al backend-ului.

## Testare

```sh
python3 -m unittest discover -s tests -v
node --test tests/transit.test.cjs
node --check app.js
```

Teste browser opționale, cu serverul static pe portul 8000 și Chromium instalat:

```sh
npm install --prefix /tmp/pelinie-browser playwright
NODE_PATH=/tmp/pelinie-browser/node_modules node tests/browser.cjs
# Cu server.py pornit separat pe 8001, folosind un catalog de test:
COMMUNITY_URL=http://127.0.0.1:8001 NODE_PATH=/tmp/pelinie-browser/node_modules node tests/browser.cjs
```

`CHROMIUM_PATH` poate selecta executabilul Chromium (implicit `/usr/bin/chromium`). Testele browser folosesc date sintetice, nu validează conectivitatea sau corectitudinea datelor STB. Testarea manuală include căutare 41, filtre, inversare, creare/reîncărcare/confirmare/ștergere, resetare locală și ecran îngust.

## Publicare

Codul se păstrează în acest repository. Workflow-ul `Checks` rulează testele unitare la push și pull request. Workflow-ul `Publish static website` publică numai interfața și `vendor`, fără server, baze de date sau teste.

Pentru prima publicare, selectează **Settings → Pages → Build and deployment → Source: GitHub Actions**. Apoi rulează workflow-ul manual sau împinge un commit pe `main`. Adresa publicată apare în rezultatul jobului; un push Git reușit nu dovedește că Pages este activ sau că deployment-ul a trecut. Dacă folosești în schimb publicarea din branch, selectează `main` și `/(root)`; nu sunt necesare build-uri.

## Următoarea integrare live și mobil

Este necesară verificarea sursei oficiale GTFS/GTFS-Realtime ori a unui API autorizat, a licenței și a condițiilor de reutilizare. Pozițiile trebuie să includă timestamp, stare de prospețime, identificatori care corespund catalogului și tratarea indisponibilității. Nu sunt simulate în această versiune. După conectarea unei surse verificate și găzduirea backend-ului, urmează PWA și distribuția iOS/Android; nu există încă aplicații native.
