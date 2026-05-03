# MHD Banská Bystrica

Mobile-first PWA na zobrazenie odchodov autobusov MHD v Banskej Bystrici.

Dáta sú parsované z verejne dostupných PDF cestovných poriadkov SAD Zvolen
([sadzv.sk](https://sadzv.sk/cestovne-poriadky/mestska-hromadna-doprava/mhd-banska-bystrica/))
a uložené ako statické JSON súbory — appka funguje plne offline po prvom načítaní.

## Funkcie

- Zoznam všetkých 30 liniek MHD BB s možnosťou označiť obľúbené (uložené v
  `localStorage`, zobrazia sa navrchu)
- Výber smeru a zastávky
- Veľký countdown na najbližší odchod (auto-update každú sekundu)
- Rozbalený zoznam ďalších odchodov, zbalená história
- Záložky **Pracovný deň / Víkend** s automatickou detekciou podľa dňa v
  týždni (sviatky sa nedetekujú — na sviatok prepne používateľ ručne)
- PWA — inštalovateľná na home screen, funguje offline

## Stack

- **Frontend**: Vite + React + TypeScript + Tailwind CSS, PWA cez `vite-plugin-pwa`
- **Dáta**: 30 statických JSON súborov v `web/public/data/lines/` + index v
  `web/public/data/lines.json`
- **Parser PDFov**: Python + `pdfplumber` (char-level extrakcia s
  midpoint-based binning). Spúšťa sa raz pri zmene PDFov.

## Štruktúra repozitára

```
.
├── scripts/                  # Python parser pipeline
│   ├── lines.json           # zoznam URL na PDF zdroje
│   ├── download.py          # stiahne PDFka do scripts/pdfs/
│   ├── parse_pdf.py         # konverzia PDF → JSON (DPMBB + SADZV)
│   ├── build_data.py        # všetky linky naraz, zápis do web/public/data/
│   ├── validate.py          # cross-check parsed dát voči PDFom
│   └── make_icons.py        # generácia PWA ikon
└── web/                     # frontend
    ├── public/data/         # parsované JSON dáta (commitované)
    ├── src/
    │   ├── screens/         # LineList, DirectionPicker, StopPicker, Departures
    │   ├── components/      # Header
    │   └── lib/             # data fetch, localStorage, time utils
    └── ...
```

## Lokálne spustenie

### Frontend

```bash
cd web
npm install
npm run dev          # http://localhost:5173
npm run build        # produkčný build do web/dist/
```

### Aktualizácia dát z PDFov

```bash
python3 -m venv .venv
.venv/bin/pip install pdfplumber requests beautifulsoup4 pillow
.venv/bin/python scripts/download.py     # stiahne PDFka
.venv/bin/python scripts/build_data.py   # parsuje + uloží JSON
.venv/bin/python scripts/validate.py     # overí dáta voči PDF
```

## Parser — dôležité konvencie

Skripty pre parsovanie odhalili niekoľko univerzálnych konvencií, ktoré držia
naprieč všetkými 30 linkami MHD BB:

1. **Smer cez paritu čísla spoja** — nepárne čísla (1, 3, 5, …) idú v jednom
   smere, párne (2, 4, 6, …) v opačnom. Toto je spoľahlivejšie než parsovanie
   `opačný smer` markerov, ktoré sa môžu na rôznych stranách opakovať.
2. **DPMBB víkend** — čísla spojov >= 300 sú víkendové.
3. **SADZV víkend/pracovný** — určuje sa cez symbolové markery v hlavičke
   stĺpca: `•` (cid:1) = pracovný, `6` = sobota, `†` = nedeľa/sviatok.
4. **SADZV stredové binning** — pre tesno rozostúpené stĺpce treba hranicu
   medzi stĺpcami počítať ako stred medzi *stredmi* trip čísel (nie medzi
   ľavými hranami), inak časy s viacerými ciframi unikajú do susedného stĺpca.

## Licencia

Kód: MIT. Dáta o cestovných poriadkoch sú vlastníctvom prevádzkovateľov MHD BB
(DPMBB, SAD Zvolen).
