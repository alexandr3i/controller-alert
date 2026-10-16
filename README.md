# PeLinie — București · v0.3

Aplicație web pentru transportul public din București–Ilfov: hartă, poziții de vehicule, estimări, alerte de transport și raportări comunitare privind prezența unui control. Nu identifică și nu urmărește individual angajați. Experiment independent, neafiliat STB/TPBI; nu înlocuiește validarea titlului de călătorie.

## Ce include

- Hartă Leaflet / OpenStreetMap și catalogul de **196 de linii de suprafață** convertit din ZIP-ul TPBI furnizat de utilizator. Cele cinci linii demonstrative sunt accesibile prin „Revino la exemple”. Catalogul inclus este o captură, nu o actualizare automată a traseelor pe GitHub Pages.
- Integrare backend pentru cele trei endpoint-uri GTFS-Realtime TPBI: vehicule, actualizări de curse și alerte.
- Vehicule pentru toate liniile din catalog sau numai pentru linia selectată. Popup-ul indică destinația, ora și vechimea poziției. Nu se solicită locația utilizatorului.
- Estimări pentru linia/sensul selectate, cu stație, destinație, abatere și incertitudine când sursa le furnizează. Nu se calculează estimări fictive din orarul static. Stațiile omise sau fără date nu sunt prezentate ca sosiri estimate.
- Alerte filtrate după câmpurile furnizate de TPBI (linie, operator, tip, stație și sens); intervalele de valabilitate sunt respectate. Textele sunt afișate ca text, fără interpretare HTML.
- Raportări locale în modul static sau comune utilizatorilor aceluiași backend, cu confirmări, ștergerea raportărilor proprii și expirare după 45 de minute.

Stațiile importate sunt unite pe hartă prin linii punctate; acestea **nu reprezintă geometria reală a străzilor**. Convertorul alege cursa cu cele mai multe stații pentru fiecare sens. Alte variante și calendarul de circulație nu sunt încă afișate. Metroul nu este inclus în catalogul interfeței. Datele și sursele sunt etichetate separat de exemple și de raportările neverificate ale utilizatorilor.

## Rulare statică — fără build sau instalări

Din rădăcina repository-ului:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

GitHub Pages poate servi această interfață, catalogul inclus și raportările numai locale. **Nu rulează backend-ul Python.** La absența backend-ului, pagina indică explicit că realtime nu este conectat; nu înlocuiește pozițiile lipsă cu vehicule demonstrative.

Leaflet 1.9.4 este inclus în `vendor/leaflet`, cu licența upstream; tarball-ul npm a fost verificat SHA-512. Fundalul hărții necesită `tile.openstreetmap.org`. Respectă [politica tile-urilor OSM](https://operations.osmfoundation.org/policies/tiles/); pentru trafic mare trebuie ales un furnizor adecvat. Nu descărcăm harta pentru utilizare offline.

## Rulare cu date live

Python 3.12 și dependențele din `requirements.txt` sunt suficiente. Nu este necesar un framework sau un build pentru interfață.

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
sh tools/start_live.sh
```

Scriptul descarcă ZIP-ul regional TPBI, îl validează, pregătește catalogul și indexul de curse/stații, apoi pornește interfața și API-ul la același server. Fișierele runtime sunt păstrate în `${TMPDIR:-/tmp}/pelinie-transit/<sha256>/`, în afara checkout-ului. Un ZIP identic reutilizează catalogul și baza de date existente; o versiune nouă primește propriul director și propria bază, fără ștergerea datelor anterioare. Catalogul static este descărcat la pornire, nu la fiecare ciclu realtime. Pentru actualizări de traseu, repornește serviciul; operatorul trebuie să verifice politica de retenție și curățarea versiunilor vechi.

Poți folosi și un ZIP descărcat anterior:

```sh
sh tools/start_live.sh /cale/BUCHAREST-REGION.zip
```

Variabile opționale de găzduire: `PORT` (implicit 8000), `PELINIE_BIND` (implicit `127.0.0.1`), `PELINIE_PUBLIC_ORIGIN` (originea HTTPS exactă). Pe Render sunt folosite automat portul și `RENDER_EXTERNAL_URL`; cookie-urile primesc atributul Secure. Nu există CORS deschis pentru raportări; interfața și API-ul trebuie servite la aceeași origine.

Alternativ, cu un catalog pregătit manual:

```sh
python3 server.py --data data/catalog.json --gtfs /cale/BUCHAREST-REGION.zip --db /tmp/pelinie.sqlite3 --realtime --port 8001
```

`--gtfs` permite rezolvarea destinațiilor, sensurilor curselor și numelor de stații. Dacă lipsește, unele informații rămân indisponibile sau apar ca identificatori. `server.py` poate rula și fără `--realtime`, doar pentru raportări comune.

## Sursele și starea datelor

| Date | Endpoint |
|---|---|
| Trasee/orare GTFS | https://gtfs.tpbi.ro/regional/BUCHAREST-REGION.zip |
| Poziții vehicule | https://gtfs.tpbi.ro/api/gtfs-rt/vehiclePositions |
| Actualizări curse | https://gtfs.tpbi.ro/api/gtfs-rt/tripUpdates |
| Alerte | https://gtfs.tpbi.ro/api/gtfs-rt/serviceAlerts |

Backend-ul decodează Protocol Buffers și expune JSON la `/api/realtime`. Un singur worker preia fiecare flux o dată la **30 de secunde**, comun tuturor browserelor; cererile browserelor către API citesc numai cache-ul. `--poll-seconds` permite un interval mai mare (minimum 30). Aceasta este frecvența aplicației, nu o garanție despre frecvența sau acoperirea TPBI. Respectă termenii sursei și eventualele limite comunicate de operator.

Fiecare flux are stare independentă: conectare, recent, vechi, eroare sau captură. Timestamp-urile sursei sunt păstrate; o descărcare nouă nu face un timestamp vechi să pară recent. Pragul de prospețime este de **180 de secunde**, iar timestamp-urile cu peste 120 de secunde în viitor nu sunt considerate recente. Pozițiile fără timestamp sau mai vechi de 15 minute sunt ascunse în modul live. Pozițiile recente sunt albastre, cele vechi sunt ocru. La pierderea sursei, cache-ul este marcat vechi; estimările curente sunt oprite. Lipsa alertelor și indisponibilitatea fluxului sunt stări distincte. Vechimea se actualizează în browser chiar și când conexiunea se întrerupe.

Sunt acceptate snapshot-uri FULL_DATASET GTFS-Realtime 1.0/2.0; răspunsurile HTML, fluxurile diferențiale și datele invalide sunt refuzate. Conexiunile folosesc verificarea TLS normală, timeout de 10 secunde și limită de 16 MB per flux. Alertele și estimările nu reprezintă garanții de sosire sau de circulație a tuturor vehiculelor.

În validarea din 16 octombrie 2026, toate cele trei surse au răspuns cu date recente, iar toate vehiculele preluate au avut linii care corespund catalogului. Au existat și răspunsuri 403 în timpul verificărilor inițiale; integrarea tratează explicit această situație. Răspunsul TPBI verificat nu includea `Access-Control-Allow-Origin`, deci nu ne bazăm pe acces direct din browserul GitHub Pages.

### Capturi pentru testare, fără a pretinde că sunt live

Un director poate conține fișierele binare `vehiclePositions`, `tripUpdates`, `serviceAlerts`:

```sh
python3 server.py --data data/catalog.json --gtfs /cale/BUCHAREST-REGION.zip --db /tmp/pelinie-replay.sqlite3 --realtime-snapshots /cale/capturi --port 8001
```

Capturile sunt încărcate o singură dată, sunt afișate cu eticheta **CAPTURĂ**, iar toate vehiculele lor sunt istorice/ocru, indiferent de momentul importului. Aceste fișiere binare nu sunt incluse în repository. Testarea cu fișierele furnizate a decodat 767 vehicule, 1.308 actualizări și 25 alerte.

## Publicare pe Render

`render.yaml` conține o configurație Blueprint pentru un singur serviciu Python, plan `free`, cu instalarea dependențelor și pornirea prin `tools/start_live.sh`. În Render:

1. Conectează repository-ul `alexandr3i/controller-alert` și creează un **Blueprint** folosind `render.yaml`.
2. Verifică planul și creează serviciul. Nu sunt necesare chei TPBI în configurația actuală.
3. Folosește adresa HTTPS generată de Render pentru aplicația completă: interfață, realtime și raportări comune pe aceeași origine.
4. Verifică `/api/realtime`: fiecare flux trebuie să aibă `status: fresh`. Un health check HTTP 200 arată că procesul răspunde, nu că TPBI furnizează date recente.

Configurația este pregătită și pașii de pornire sunt testați local; **nu s-a creat un serviciu în contul Render**. Planul gratuit poate opri serviciul când nu este folosit și folosește stocare temporară: raportările pot fi pierdute la restart/deploy. Pentru retenție garantată și disponibilitate continuă sunt necesare un plan/disk sau o bază de date persistentă și configurarea lor explicită. Nu sunt create automat resurse plătite.

GitHub Pages rămâne o variantă statică separată. Workflow-ul `Publish static website` publică numai interfața, catalogul inclus și `vendor`. Activează **Settings → Pages → Source: GitHub Actions**, apoi rulează workflow-ul sau împinge un commit pe `main`. Push-ul codului nu dovedește succesul deployment-ului Pages sau Render.

## Raportări comune

Raportările sunt anonime și neverificate. Nu sunt solicitate nume, fotografii, text liber, GPS sau identitatea angajaților. O sesiune cookie `HttpOnly; SameSite=Strict` permite ștergerea propriilor raportări și o singură confirmare per raportare. Limite: 3 raportări/10 minute/sesiune și 30 scrieri/minut/adresă. Pentru această limită, un hash al adresei este păstrat numai în RAM timp de un minut; adresele și cookie-urile nu sunt jurnalizate. Pierderea cookie-ului pierde accesul la ștergerea proprie. Datele expirate sunt eliminate la următoarea cerere API.

Resetarea datelor locale nu șterge raportările publicate; acestea se șterg individual. Importarea manuală a altui catalog sau revenirea la exemple dezactivează modul comunitar și realtime în acel tab, pentru a evita amestecarea identificatorilor. Reîncărcarea reconectează catalogul serverului.

Backend-ul de raportări rămâne un prototip: limitele pe sesiune pot fi ocolite, iar autentificarea și moderarea nu sunt implementate. Înainte de o lansare largă sunt necesare moderare și protecție anti-abuz la infrastructură. Rulează un singur proces, cu SQLite în afara directorului public.

## Import GTFS manual

```sh
python3 tools/import_gtfs.py /cale/transport.zip --source 'URL-ul sau numele sursei reale' --output /tmp/trasee.json
```

Importă JSON-ul prin controlul de deasupra hărții. Importul este local, fără upload, și se repetă după reîncărcare. Limite: ZIP decomprimat 512 MB, JSON 10 MB, 1000 linii și 500 stații pe sens. Un sens lipsă nu este inventat. Coordonatele sunt limitate la regiunea București–Ilfov. Convertorul nu suprascrie fișiere existente.

## Teste

Cu mediul virtual activ și dependențele instalate:

```sh
python3 -m unittest discover -s tests -v
node --test tests/*.test.cjs
node --check app.js
node --check live.js
```

Teste browser opționale, cu serverul static pe 8000 și Chromium instalat:

```sh
npm install --prefix /tmp/pelinie-browser playwright
NODE_PATH=/tmp/pelinie-browser/node_modules node tests/browser.cjs
NODE_PATH=/tmp/pelinie-browser/node_modules node tests/realtime-browser.cjs
```

Variabilele opționale `COMMUNITY_URL`, `SNAPSHOT_URL` și `LIVE_URL` activează verificări pe servere pornite separat. `CHROMIUM_PATH` poate selecta executabilul (implicit `/usr/bin/chromium`). Testele realtime verifică prospețimea, timestamp-urile absente/viitoare, cache-ul, erorile parțiale, recuperarea, feed-urile goale, validarea protobuf, alertele, estimările și separarea capturilor de live. Fluxul mock din browser este marcat ca test; verificarea cu `LIVE_URL` folosește sursa reală. Workflow-ul `Checks` rulează testele unitare la push și pull request.

Aplicațiile native iOS/Android și PWA nu sunt încă implementate.
