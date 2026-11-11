# MASTER.md — system wizualny Ticketline

Jedyne źródło prawdy dla frontendu. Każdy kolor, krój, odstęp, promień, cień i czas animacji
w kodzie pochodzi stąd (`src/styles/tokens.css`). Wartość spoza tego pliku to błąd.

## Tezy (zatwierdzone 2026-11-11)

**Teza wizualna.** Ciemny, chłodny świat spokojnej kasy po zmroku: tło z głęboką zieloną nutą
`#101716` (nie czysta czerń), jasny szarozielony tekst `#E6ECEA` i jeden stonowany morski akcent
`#5DBFB2`, zarezerwowany dla działania i potwierdzenia, bez neonowej poświaty. Typografia: Public
Sans — krój zaprojektowany dla serwisów publicznych, z cyframi tabelarycznymi, bo ceny, liczniki
i pozycje w kolejce muszą stać w równych kolumnach. Sklep przestronny (siatka 8 px), zaplecze
gęstsze na tej samej skali. Komponenty płaskie, ramka 1 px, promień 6 px; głębię dają trzy poziomy
tła (strona, karta, kwit). Jedyny element z cieniem to kwit rezerwacji z perforacją. Pełny
redesign: dawna paleta i fonty Manrope / DM Mono znikają.

**Teza interakcji.** Spokojnie i pewnie, 160–320 ms, jedna krzywa `cubic-bezier(0.2, 0, 0, 1)`.
Hover: 160 ms, wyłącznie kolor ramki lub tła, bez skalowania i unoszenia. Przewijanie: nic.
Zmiana stanu kwitu: 240 ms, przenikanie z przesunięciem 4 px. Potwierdzenie: 320 ms rysowanie
znacznika (opóźnienie 80 ms). Oczekiwanie w kolejce: pasek 1600 ms liniowo, tylko gdy status to
`queued`. Zakazane: odliczanie czasu, migające „zostały 3 bilety!”, ponaglająca czerwień, sprężyny
i odbicia, konfetti, parallax, przejmowanie przewijania, liczniki nabijane animacją.

**Allowed patterns:** cienkie linie 1 px, perforowana krawędź kwitu, krój monospace wyłącznie dla
identyfikatorów technicznych na zapleczu, zapętlony pasek postępu podczas oczekiwania w kolejce,
cyfry tabelaryczne.

**Założenia:** tylko ciemny motyw w v1 (bez przełącznika); ceny w złotych; Public Sans i IBM Plex
Mono z Google Fonts z `display=swap` i zapasowym krojem.

## Kolory

| Token | Wartość | Rola | Kontrast |
| --- | --- | --- | --- |
| `--ground` | `#101716` | tło strony | — |
| `--surface` | `#18211F` | karty, panele, pola formularzy | — |
| `--raised` | `#1F2A28` | kwit rezerwacji, menu | — |
| `--ink` | `#E6ECEA` | tekst główny | 15,2 : 1 na ground |
| `--muted` | `#94A3A0` | tekst drugorzędny, etykiety | 7,0 na ground, 6,3 na surface |
| `--line` | `#2B3836` | ramki, linie podziału | (dekoracyjne) |
| `--line-strong` | `#5E706C` | ramka pola, hover karty | 3,1 : 1 na surface (granica UI) |
| `--track` | `#24302E` | tor paska, tło wyłączonego przycisku | — |
| `--accent` | `#5DBFB2` | działanie, potwierdzenie, link | 7,5 na surface |
| `--accent-hover` | `#74CEC2` | hover akcentu | — |
| `--accent-ink` | `#0B1312` | tekst na akcencie | 8,6 : 1 |
| `--accent-soft` | `rgba(93,191,178,.14)` | tło znacznika „potwierdzone” | — |
| `--refuse` | `#E08A74` | odrzucenie, wyprzedane, błąd | 6,3 na surface |
| `--refuse-soft` | `rgba(224,138,116,.14)` | tło znacznika „odrzucone” | — |

Kolor semantyczny „w kolejce” to `--ink` na `--track` (neutralny — czekanie nie jest ani dobre,
ani złe). Brak koloru ostrzegawczego żółtego: system nie ponagla.

## Typografia

- UI: `"Public Sans", "Segoe UI", Roboto, system-ui, sans-serif` — wagi 400, 600, 700.
- Identyfikatory techniczne (tylko zaplecze): `"IBM Plex Mono", ui-monospace, Consolas, monospace`, 400.
- `font-variant-numeric: tabular-nums` globalnie.
- Skala: 13 / 15 / 17 / 22 / 30 / 44 px (`--t-13` … `--t-44`); 44 tylko nagłówek strony wydarzenia
  i liczba-bohater na zapleczu.
- Interlinia: 1,55 tekst, 1,2 nagłówki. Długość wiersza tekstu ≤ 68 znaków.
- Etykiety: 13 px, 600, wersaliki, odstęp liter 0,04 em.

## Odstępy, układ

- Skala: 4, 8, 12, 16, 24, 32, 48, 64 px (`--s-4` … `--s-64`).
- Sklep: kontener `--w-shop: 1120px`, odstępy sekcji `--s-48`/`--s-64`, wnętrze kart `--s-24`.
- Zaplecze: kontener `--w-backstage: 1280px`, wnętrze komórek `--s-12`/`--s-16`.
- Margines boczny: `max(16px, env(safe-area-inset-*))`. Siatki zwijają się do jednej kolumny < 760 px.

## Promienie, głębia

- `--r-2` (znaczniki statusu), `--r-6` (przyciski, karty, pola, kwit), `--r-full` (tylko wycięcia perforacji).
- Głębia przez poziomy tła: ground → surface → raised.
- `--elev-stub: 0 0 0 1px var(--line), 0 12px 32px rgba(0,0,0,.45)` — wyłącznie kwit.

## Ruch

| Token | Wartość | Użycie |
| --- | --- | --- |
| `--dur-fast` | 160 ms | hover, focus, zmiana ramki |
| `--dur-base` | 240 ms | zmiana stanu (kwit, komunikaty, wejście/wyjście) |
| `--dur-slow` | 320 ms | rysowanie znacznika potwierdzenia |
| `--dur-loop` | 1600 ms | pasek „w kolejce”, `linear` |
| `--ease-calm` | `cubic-bezier(0.2, 0, 0, 1)` | wszystko poza pętlą |

- Wejście: `opacity 0→1` + `translateY(4px→0)`. Wyjście: odwrotnie, ten sam czas.
- Animowane są tylko `opacity`, `transform`, kolory i `stroke-dashoffset`. Nigdy wymiary.
- `prefers-reduced-motion: reduce`: wszystkie czasy 0 ms, pasek kolejki zastąpiony nieruchomą,
  przerywaną kreską.

## Komponenty bazowe (pięć stanów)

| Komponent | Domyślny | Hover | Focus | Wciśnięty | Wyłączony |
| --- | --- | --- | --- | --- | --- |
| Przycisk główny | tło accent, tekst accent-ink | accent-hover | obrys 2 px ink, odsunięcie 2 px | `translateY(1px)` | tło track, tekst muted, `not-allowed` |
| Przycisk cichy | przezroczysty, ramka line | tło surface, ramka line-strong | jw. | jw. | tekst muted, ramka line |
| Pole tekstowe | tło surface, ramka line-strong | ramka muted | ramka accent + obrys 2 px accent (30%) | — | tło ground, tekst muted |
| Karta wydarzenia (link) | surface, ramka line | ramka line-strong | obrys 2 px ink | — | wyprzedane: tekst muted, etykieta refuse |
| Link | accent, podkreślenie 1 px | accent-hover | obrys 2 px ink | — | — |
| Znacznik statusu | `confirmed` accent/accent-soft · `rejected` refuse/refuse-soft · `queued` ink/track | — | — | — | — |

Błąd pola: ramka refuse + komunikat pod polem (13 px, refuse), opisujący co poprawić.

## Powierzchnia sygnaturowa: kwit rezerwacji

Tło raised, cień `--elev-stub`, perforacja: przerywana linia 2 px `--line` z wycięciami w kolorze
`--ground`. Góra: wydarzenie, liczba biletów, `request_id` (mono, muted). Dół: stan.
`queued` → pasek pętli + „Zgłoszenie przyjęte. Wynik pojawi się tutaj, zwykle w ciągu kilku sekund.”
`confirmed` → znacznik rysowany 320 ms + „Potwierdzone”. `rejected` → „Wyprzedane” / „Nie znaleziono
wydarzenia” w refuse, z wyjaśnieniem, że nic nie zostało zarezerwowane.

## Mapa stron

Sklep: Oferta `/`, Wydarzenie i rezerwacja `/wydarzenie/:id`, Moje bilety `/moje-bilety`,
Logowanie i rejestracja `/logowanie`, Dodaj wydarzenie `/admin` (tylko admin).
Od kulis: Jak to działa `/od-kulis`, Kolejka na żywo `/od-kulis/kolejka`.

## Pisanie

Po polsku, zwykłym językiem kupującego. Przyciski mówią, co się stanie („Zarezerwuj 2 bilety”).
Błędy mówią, co poszło nie tak i co zrobić. Żadnej presji czasu, żadnych wymyślonych liczb:
każda liczba na stronie pochodzi z API. Na zapleczu nazwy techniczne (XLEN, PEL) są dozwolone,
zawsze z opisem po polsku obok.
