# CLAUDE.md — Ticketline (praca inżynierska)

> Kontekst projektu dla Claude Code. Język projektu: **polski** (komentarze w kodzie, dokumentacja,
> rozmowa z autorem). Nazwy w kodzie (zmienne, endpointy) po angielsku.

## 1. Temat i cel

**Temat pracy:** „Projekt i implementacja skalowalnego systemu mikroserwisowego do obsługi procesów
o wysokim natężeniu ruchu w środowisku Kubernetes”.

**Cel:** system rezerwacji biletów (analogicznie: zapisy na zajęcia na uczelni), który przetrwa nagły
skok ruchu (**Flash Crowd**, 0 → 2000 użytkowników w kilka sekund) dzięki asynchronicznemu kolejkowaniu
i autoskalowaniu — **bez gubienia żądań i bez overbookingu**.

**Cel badawczy:** studium przypadku w Locust — porównanie czasów odpowiedzi i wydajności systemu
ze statyczną liczbą podów vs z dynamicznym skalowaniem horyzontalnym (HPA/KEDA) pod nagłym skokiem ruchu.

## 2. Stos technologiczny

| Warstwa | Technologia |
| --- | --- |
| Frontend | React 19 + TypeScript, Vite 7 (SPA) |
| Backend | Python 3.12, FastAPI (ASGI, async) — wszystkie serwisy; **Django odrzucone** na rzecz unifikacji |
| ORM / DB | SQLAlchemy 2.0 (async) + asyncpg, PostgreSQL 16 (wzorzec **Shared Database**) |
| Kolejka | Redis 7 |
| Infrastruktura | Docker, docker compose (lokalnie), Kubernetes, Helm |
| Skalowanie | HPA (CPU) dla API, **KEDA** dla workera (decyzja podjęta — wchodzi do pracy) |
| Testy / monitoring | Locust (load testing), Prometheus + Grafana |

## 3. Architektura

```
Przeglądarka :5173 (React)
   ├─ GET oferta, metryki ──► Core API :8001 ──► PostgreSQL :5432
   └─ POST rezerwacja     ──► Booking API :8000 ──► Redis :6379 (kolejka)
                                                        │
                                     Worker ◄───────────┘ ──► PostgreSQL
                                       └─ zapisuje wynik (status) w Redisie
```

Podział wg **charakterystyki obciążenia**:

- **Core API** (`backend/core_api`) — odczyt i zarządzanie: oferta, dodawanie wydarzeń (admin),
  historia rezerwacji, metryki, docelowo logowanie (JWT). Rozmawia z PostgreSQL. Skalowane po CPU (HPA).
- **Booking API** (`backend/booking_api`) — „amortyzator”/producent. Przyjmuje rezerwację, wkłada JSON
  do Redisa i **natychmiast zwraca `202 Accepted`**. **Nigdy nie odpytuje PostgreSQL** (nawet nie sprawdza,
  czy wydarzenie istnieje — robi to worker). Skalowane agresywnie (HPA).
- **Worker** (`backend/worker`) — konsument. Pobiera zadania z Redisa, sprawdza dostępność i zapisuje
  rezerwację w PostgreSQL. Bez FastAPI. Skalowany po długości kolejki (KEDA).

### Kluczowe decyzje (nie zmieniać bez uzgodnienia)

1. **Rezerwacja miejsc = jeden atomowy `UPDATE`** zamiast `SELECT ... FOR UPDATE`:
   `UPDATE events SET available = available - :q WHERE id = :id AND available >= :q RETURNING available`.
   Blokada wiersza trwa minimalnie; `CHECK (available >= 0)` w bazie dodatkowo chroni przed overbookingiem.
   (Porównanie z `FOR UPDATE` może być osobnym wątkiem w pracy.)
2. **Idempotencja:** `bookings.request_id` jest `UNIQUE` (klucz idempotencji, generowany przez klienta
   lub przez Booking API). Worker robi `INSERT ... ON CONFLICT DO NOTHING`; przy duplikacie transakcja jest
   wycofywana (razem ze zmniejszeniem licznika) i zwracany jest wynik z pierwszego przetworzenia.
   Docelowo: dostarczanie *at-least-once* + idempotentny konsument = „nic nie zgubione, nic nie zdublowane”.
3. **Kolejka = Redis Streams z consumer group** (zrobione): strumień `ticket:stream`, grupa
   `booking-workers` (tworzona od id `0`), Booking API: `XADD` (bez `MAXLEN`). Worker: `XREADGROUP`,
   po COMMIT `XACK` + `XDEL` (więc `XLEN` = czekające + w trakcie), co 10 s `XAUTOCLAIM` wiadomości
   bezczynnych > 30 s, po > 5 próbach albo przy złym formacie → strumień `ticket:dead`
   (status `rejected`/`processing_failed`). Nazwa konsumenta = hostname (nazwa poda). SIGTERM: dokończenie
   paczki + `XGROUP DELCONSUMER`, jeśli PEL pusty. Parametry: `WORKER_BATCH_SIZE`, `WORKER_CLAIM_IDLE_MS`,
   `WORKER_CLAIM_INTERVAL`, `WORKER_MAX_DELIVERIES`. Skalowanie: **KEDA scaler `redis-streams`**
   (`lagCount`/`pendingEntriesCount`). **Arq odrzucony** — sorted set, którego KEDA nie widzi.
4. **Status rezerwacji w Redisie:** hash `booking:{request_id}` (`status`, opcjonalnie `reason`, TTL 1 h).
   Klient odpytuje `GET /api/ticket-requests/{id}` w Booking API (czyta tylko Redisa).
5. **Schemat bazy: źródłem prawdy jest `db/init.sql`.** Modele SQLAlchemy w `shared/models.py` tylko go
   mapują — **nie używamy `create_all`**. Zmiana schematu = zmiana `init.sql` + modelu + `docker compose down -v`.
6. **Monorepo z `backend/shared/`:** wszystkie serwisy importują `shared.*`; każdy serwis ma własny
   `Dockerfile` budowany z kontekstem `backend/`. Serwisy uruchamiane z `backend/` jako katalogu roboczego
   (`uvicorn core_api.main:app`, `python -m worker.main`).
7. **Limit połączeń do Postgresa:** pula konfigurowalna (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, domyślnie 5+5),
   bo liczba podów × pula łatwo przekracza `max_connections`. Przy skalowaniu: ograniczyć `maxReplicas`
   albo dodać PgBouncer.

## 4. Struktura repo

```
fastapi/                          # C:\Users\Kacper\Desktop\fastapi (Windows)
├── CLAUDE.md
├── plan.md                       # docelowa struktura monorepo
├── docker-compose.yml            # postgres, redis, core-api, booking-api, worker, frontend
├── .dockerignore                 # ważne: wyklucza node_modules z Windowsa z kontekstu frontendu
├── Dockerfile.frontend           # node:25-alpine, vite dev server
├── db/init.sql                   # schemat + dane startowe (3 wydarzenia)
├── k8s/                          # PUSTE — manifesty do zrobienia
├── frontend/                     # React + Vite; src/App.tsx (adresy API wpisane na sztywno)
└── backend/
    ├── requirements.txt          # wspólne: fastapi[standard], redis[hiredis], sqlalchemy[asyncio], asyncpg
    ├── .dockerignore
    ├── shared/                   # database.py, models.py, schemas.py, redis_client.py, security.py (JWT, Argon2)
    ├── core_api/                 # Dockerfile, main.py, dependencies.py (JWT), routers/{auth,events,users}.py
    ├── booking_api/              # Dockerfile, main.py, producer.py
    ├── worker/                   # Dockerfile, main.py (pętla), tasks.py, services.py (logika DB)
    └── scripts/smoke_check.py    # test end-to-end (tylko stdlib)
```

### Baza danych (`db/init.sql`)

- `users` (id, email UNIQUE, password_hash, is_admin, created_at)
- `events` (id VARCHAR np. `evt-001`, name, venue, city, starts_at TIMESTAMPTZ, capacity, **available**,
  price NUMERIC, accent, created_at) — `CHECK (available >= 0 AND available <= capacity)`
- `bookings` (id, **request_id UNIQUE**, event_id FK, user_id FK nullable, email, quantity 1–8,
  status `confirmed`|`rejected`, created_at)

Wszystkie kolumny dat to `TIMESTAMPTZ` (`Base.type_annotation_map` w `shared/database.py`).

## 5. Endpointy

Swagger: http://localhost:8001/docs (Core), http://localhost:8000/docs (Booking).

| Serwis | Endpoint | Opis |
| --- | --- | --- |
| Core :8001 | `GET /health` | połączenie z bazą |
| | `GET /api/events`, `GET /api/events/{id}` | oferta (pola zgodne z frontendem: `date`, `status`, `sold`, ...) |
| | `POST /api/events` | dodanie wydarzenia — **wymaga JWT admina** (401 / 403) |
| | `POST /api/auth/register` | body JSON `email`, `password` (min. 8) → 201, 409 przy duplikacie |
| | `POST /api/auth/login` | OAuth2 form-data `username` (= e-mail), `password` → `access_token` (HS256, 60 min) |
| | `GET /api/auth/me` | dane zalogowanego użytkownika |
| | `GET /api/users/me/bookings` | historia rezerwacji zalogowanego (po e-mailu konta) |
| | `GET /api/users/bookings?email=` | **deprecated**, bez logowania — do usunięcia po zmianie frontendu |
| | `GET /api/metrics` | `queue_depth`, `events_processed`, `tickets_sold`, `capacity` |
| Booking :8000 | `GET /health` | połączenie z Redisem |
| | `POST /api/ticket-requests` | body: `event_id`, `quantity` (1–8), `email`, opcjonalnie `request_id` → 202 |
| | `GET /api/ticket-requests/{request_id}` | `queued` / `confirmed` / `rejected` + `reason` (`sold_out`, `event_not_found`, `duplicate`) |

## 6. Uruchamianie i testowanie

```
docker compose up --build
docker compose exec core-api python scripts/smoke_check.py
docker compose exec core-api python scripts/smoke_check.py --requests 200 --capacity 20 --parallel 50
docker compose up -d --scale worker=3
docker compose logs -f worker
docker compose exec postgres psql -U tickets -d tickets -c "select status, count(*) from bookings group by status"
docker compose down -v            # reset bazy (init.sql wykonuje się tylko na pustym wolumenie)
```

- `smoke_check.py`: health → oferta → rejestracja/logowanie/uprawnienia (401/403) → nowe wydarzenie
  (admin) → pojedyncza rezerwacja + duplikat + `me/bookings` → N równoległych rezerwacji (brak overbookingu,
  nic nie zgubione, strumień pusty). `--stream-tests` (~40 s): dead letter + osierocona wiadomość
  odzyskana przez `XAUTOCLAIM`. Każde uruchomienie tworzy nowe wydarzenie. Ostatni wynik: 23/23 OK
  (200 żądań, 3 workery, `--stream-tests`).
- Auth (dev): `JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` w `docker-compose.yml`; konto admina tworzy
  Core API przy starcie (`ensure_admin_account`, `ON CONFLICT DO NOTHING`). Hasła: Argon2id (`pwdlib`).
- Hot reload: backend przez bind mount `./backend:/app` + `--reload`; frontend przez bind mount
  + `VITE_USE_POLLING=true` (Docker na Windowsie nie przekazuje zdarzeń plików).
- Frontend woła `http://localhost:8001` (oferta, metryki) i `http://localhost:8000` (rezerwacje) — adresy
  wpisane na sztywno w `frontend/src/App.tsx`; CORS w obu API zezwala na `http://localhost:5173`.

## 7. Stan prac i aktywne cele

**Zrobione:** struktura monorepo wg `plan.md`, PostgreSQL + schemat, `shared/`, Core API (oferta, metryki,
historia), Booking API (producent + status), worker z atomowym UPDATE i idempotencją, docker compose
z frontendem, skrypt testowy.

**Do zrobienia (w kolejności):**
1. [x] Worker na Redis Streams + consumer group (`XADD` / `XREADGROUP` / `XACK`+`XDEL` / `XAUTOCLAIM`,
       dead letter, graceful shutdown).
2. [x] Logowanie / JWT (`core_api/routers/auth.py`, `core_api/dependencies.py`, `shared/security.py`)
       + `POST /api/events` tylko dla admina. Otwarte: Booking API nie wiąże rezerwacji z kontem
       (`bookings.user_id` puste) — można weryfikować JWT w Booking API bez bazy (`shared/security.py`).
3. [ ] Frontend: polling statusu rezerwacji, adresy API z env (`VITE_*`) zamiast na sztywno.
4. [ ] Manifesty K8s / Helm (`k8s/` puste): postgres, redis, core-api, booking-api (HPA), worker
       (KEDA ScaledObject, scaler `redis-streams`), ingress. Wymagane `resources.requests` i metrics-server.
5. [ ] Metryki Prometheus (np. `prometheus-fastapi-instrumentator`, głębokość kolejki) + dashboard Grafana.
6. [ ] Locust: `LoadTestShape` dla skoku 0 → 2000, tryb rozproszony (master + workerzy).
7. [ ] (opcjonalnie) PgBouncer.

## 8. Metodologia badania (ustalenia)

Porównanie „monolit vs HPA” miesza dwie zmienne, więc planowane są **trzy scenariusze**:

| Scenariusz | Zapis rezerwacji | Skalowanie | Co pokazuje |
| --- | --- | --- | --- |
| A | synchroniczny zapis do bazy | stała liczba podów | punkt odniesienia |
| B | kolejka (Redis) | stała liczba podów | zysk z samej kolejki |
| C | kolejka (Redis) | HPA / KEDA | zysk z autoskalowania |

Scenariusz A wymaga dodatkowego, synchronicznego endpointu rezerwacji (do zrobienia).

**Mierzyć:** p50/p95/p99 czasu odpowiedzi, odsetek błędów, RPS, głębokość kolejki w czasie, czas
opróżnienia kolejki, liczba podów w czasie, czas end-to-end (202 → potwierdzenie), bilans końcowy:
`liczba 202 = confirmed + rejected`.

**Uwaga:** HPA reaguje wolniej niż skok ruchu (metryki co ~15 s + start poda + opóźnienie CPU) —
pierwsze sekundy przyjmuje kolejka. To wynik do opisania, nie błąd.

## 9. Wytyczne dla Claude

- **Odpowiadaj po polsku.** Komentarze w kodzie po polsku, identyfikatory po angielsku.
- Środowisko autora: **Windows + Docker Desktop + PowerShell**. Polecenia podawaj jako **pojedyncze linie**
  (wklejanie wieloliniowych komend do PowerShella sprawia problemy) albo jako skrypt w repo uruchamiany
  jedną komendą (najlepiej `docker compose exec ...`, bez zależności od Pythona na hoście).
- Zachowuj zasady architektury z sekcji 3 — w szczególności: Booking API bez dostępu do PostgreSQL,
  idempotencja po `request_id`, atomowy UPDATE, `init.sql` jako źródło schematu.
- Kod async (FastAPI, SQLAlchemy async, `redis.asyncio`), typowanie, Pydantic v2, SQLAlchemy 2.0 (`Mapped[...]`).
- Nowe zależności dodawaj do `backend/requirements.txt` (wspólny dla wszystkich serwisów).
- Po zmianach backendu uruchom `scripts/smoke_check.py` i rozszerzaj go o nowe przypadki.
- **Nie commituj ani nie pushuj bez prośby.** Nie usuwaj plików autora bez pytania.
- `.gitignore` zawiera wzorce typu `*test`, `*tests`, `*testing` — folder `tests/` byłby ignorowany przez git;
  przy dodawaniu testów sprawdź `git check-ignore` lub dostosuj `.gitignore`.
- Każda decyzja projektowa jest też materiałem do pracy dyplomowej — przy istotnych wyborach krótko
  uzasadnij je (alternatywy, kompromisy), żeby dało się to przenieść do tekstu pracy.
