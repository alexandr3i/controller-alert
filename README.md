# PeLinie — prototip v0.1

Prototip web **100% static** pentru o posibilă platformă de observații comunitare privind transportul public din București. Este un exercițiu de interfață și flux de utilizare, nu o aplicație operațională.

## Ce poți testa

- Selectarea liniilor demonstrative 41, 104, 168, 1 și 69
- Căutarea liniilor și stațiilor și filtrarea după tipul mijlocului de transport
- Schimbarea sensului de mers și afișarea stațiilor într-o schemă
- Vizualizarea câtorva **raportări fictive, marcate EXEMPLU**
- Adăugarea, confirmarea și ștergerea unor raportări **locale**
- Expirarea automată a raportărilor locale după 45 de minute
- Interfața adaptată pentru desktop și telefon

**Important:** Nu există bază de date, conturi, GPS, hărți reale, date STB în timp real sau partajarea raportărilor. Informațiile introduse de un utilizator nu se văd pe alte dispozitive. Datele sunt salvate exclusiv în `localStorage` pe browserul în care testezi. Exemplele de stații și trasee sunt ilustrative și nu trebuie considerate actuale sau exacte.

## Testare locală

Deschide `index.html` direct într-un browser modern. Nu sunt necesare instalări. Dacă browserul restricționează `localStorage` pe fișiere locale, verifică salvarea după ce publici proiectul pe GitHub Pages (HTTPS).

## Publicare pe GitHub Pages

1. Creează un repository nou pe GitHub (de exemplu `pelinie`).
2. Încarcă fișierele `index.html`, `README.md` și `AGENTS.md` în rădăcina repository-ului.
3. Mergi la **Settings → Pages**.
4. La **Build and deployment**, alege **Deploy from a branch**.
5. Selectează branch-ul `main` și folderul `/(root)` apoi apasă **Save**.
6. După publicare, GitHub îți va afișa adresa site-ului în secțiunea Pages. Pentru un repository obișnuit de proiect URL-ul urmează forma `https://UTILIZATOR.github.io/pelinie/` dacă repository-ul se numește `pelinie`.

GitHub Pages publică fișiere statice; **nu este** un backend și nu sincronizează raportările între utilizatori.

## Continuare în Codex

După publicarea codului în repository, conectează repository-ul în Codex și începe cu cererea:

> Citește `AGENTS.md` și `README.md`. Păstrează proiectul static și compatibil cu GitHub Pages. Mai întâi analizează structura prototipului și propune următorii trei pași, fără să implementezi încă un backend.

## Teste manuale rapide

1. Caută `41` și selectează linia.
2. Schimbă sensul cu butonul de săgeți și verifică inversarea stațiilor.
3. Apasă „+ Raportează” lângă o stație, salvează și verifică apariția raportării.
4. Reîncarcă pagina: raportarea locală ar trebui să rămână.
5. Apasă „Confirmă” și verifică schimbarea stării.
6. Șterge raportarea, apoi încearcă „Șterge datele mele de test”.
7. Testează pe ecran îngust și în mod mobil.

## Pașii următori, când vrem o versiune reală

1. Importul și validarea datelor de traseu și stații din surse oficiale și verificarea condițiilor de reutilizare.
2. Backend cu autentificare, permisiuni, moderare și măsuri anti-spam.
3. Sistem de raportări comunitare cu politici clare de confidențialitate și siguranță, fără identificarea sau urmărirea angajaților.
4. Politică de retenție, termeni de utilizare și analiză juridică înainte de lansare.
5. PWA și ulterior aplicație mobilă (de exemplu React Native/Expo), cu reutilizarea logicii și a API-ului.

Acesta este un experiment independent, neafiliat STB sau TPBI. Aplicația nu este destinată evitării obligațiilor de plată a călătoriei.
