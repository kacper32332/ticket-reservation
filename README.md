# Ticketline

System rezerwacji biletów zbudowany jako skalowalny system mikroserwisowy. Projekt powstaje w ramach
pracy inżynierskiej **„Projekt i implementacja skalowalnego systemu mikroserwisowego do obsługi procesów
o wysokim natężeniu ruchu w środowisku Kubernetes”**.

Celem jest przetrwanie nagłego skoku ruchu (*flash crowd*: od 0 do 2000 użytkowników w kilka sekund)
**bez gubienia żądań i bez overbookingu**. Służą do tego asynchroniczne kolejkowanie (Redis Streams)
i autoskalowanie horyzontalne (HPA / KEDA).

## Architektura

```
Przeglądarka :5173 (React)
   ├─ GET oferta, metryki, logowanie ──► Core API :8001 ──► PostgreSQL :5432
   └─ POST rezerwacja               ──► Booking API :8000 ──► Redis Stream :6379
                                                                  │  (consumer group)
                                              Worker ×N ◄─────────┘ ──► PostgreSQL
                                                └─ zapisuje status rezerwacji w Redisie
```

| Serwis | Rola | Skalowanie |
| --- | --- | --- |
| **Core API** (`backend/core_api`) | oferta, dodawanie wydarzeń (admin), logowanie JWT, historia rezerwacji, metryki | HPA (CPU) |
| **Booking API** (`backend/booking_api`) | przyjmuje rezerwację, dodaje ją do strumienia (`XADD`) i od razu zwraca `202 Accepted`; nie łączy się z PostgreSQL | HPA (agresywnie) |
| **Worker** (`backend/worker`) | pobiera wiadomości ze strumienia (`XREADGROUP`), rezerwuje miejsca w PostgreSQL, potwierdza (`XACK`) dopiero po zapisie | KEDA (`redis-streams`) |

### Gwarancje

- **Brak overbookingu:** rezerwacja to jeden atomowy
  `UPDATE events SET available = available - :q WHERE id = :id AND available >= :q`.
  Dodatkowo baza ma ograniczenie `CHECK (available >= 0)`.
- **Nic nie ginie:** dostarczanie *at-least-once*. Wiadomość zostaje w PEL (lista wiadomości pobranych,
  ale jeszcze niepotwierdzonych) do momentu `XACK`. Wiadomości osierocone po padzie workera przejmuje
  `XAUTOCLAIM`. Wiadomości, których nie da się przetworzyć, trafiają do strumienia `ticket:dead`.
- **Nic się nie dubluje:** konsument jest idempotentny. `bookings.request_id` ma ograniczenie `UNIQUE`,
  a zapis używa `INSERT ... ON CONFLICT DO NOTHING`.
- **Bezpieczne zmniejszanie skali:** po SIGTERM worker kończy bieżącą paczkę i wypisuje się z consumer group.

## Stos technologiczny

| Warstwa | Technologia |
| --- | --- |
| Frontend | React 19, TypeScript, Vite 7 |
| Backend | Python 3.12, FastAPI (async), Pydantic v2 |
| Baza danych | PostgreSQL 16, SQLAlchemy 2.0 (async) + asyncpg |
| Kolejka | Redis 7 (Streams + consumer group) |
| Autoryzacja | JWT (PyJWT, HS256), hasła Argon2id (pwdlib) |
| Infrastruktura | Docker, docker compose; docelowo Kubernetes, Helm, HPA, KEDA |
| Testy / monitoring | skrypt `smoke_check.py`; docelowo Locust, Prometheus, Grafana |

## Uruchomienie

Wymagany jest Docker (na Windowsie: Docker Desktop). Wszystkie polecenia uruchamiasz z katalogu głównego repo.

```bash
docker compose up --build
```

| Adres | Co |
| --- | --- |
| http://localhost:5173 | frontend |
| http://localhost:8001/docs | Swagger Core API |
| http://localhost:8000/docs | Swagger Booking API |

Konto administratora (tylko do developmentu, ustawiane w `docker-compose.yml`): `admin@ticketline.pl` / `admin12345`.
W Swaggerze Core API kliknij **Authorize** i zaloguj się tym e-mailem i hasłem.

Przydatne polecenia:

```bash
docker compose up -d --scale worker=3
```

```bash
docker compose logs -f worker
```

```bash
docker compose exec postgres psql -U tickets -d tickets -c "select status, count(*) from bookings group by status"
```

```bash
docker compose down -v
```

`down -v` usuwa wolumen bazy. Jest potrzebny po każdej zmianie `db/init.sql`, bo skrypt wykonuje się
tylko na pustym wolumenie.

## Testy

Test end-to-end obejmuje: health, ofertę, rejestrację, logowanie i uprawnienia, dodanie wydarzenia,
rezerwację z duplikatem oraz N równoległych rezerwacji. Sprawdza brak overbookingu, brak zgubionych
żądań i pusty strumień na koniec.

```bash
docker compose exec core-api python scripts/smoke_check.py --requests 200 --capacity 20 --parallel 50
```

Opcja `--stream-tests` (ok. 40 s) dodatkowo sprawdza dead letter i odzyskanie osieroconej wiadomości
przez `XAUTOCLAIM`:

```bash
docker compose exec core-api python scripts/smoke_check.py --stream-tests
```

## API

| Serwis | Endpoint | Opis |
| --- | --- | --- |
| Core | `GET /health` | połączenie z bazą |
| | `GET /api/events`, `GET /api/events/{id}` | oferta |
| | `POST /api/events` | dodanie wydarzenia (**JWT admina**) |
| | `POST /api/auth/register` | rejestracja (`email`, `password`) |
| | `POST /api/auth/login` | logowanie: form-data `username` (= e-mail) i `password`, zwraca `access_token` |
| | `GET /api/auth/me` | dane zalogowanego użytkownika |
| | `GET /api/users/me/bookings` | historia rezerwacji zalogowanego użytkownika |
| | `GET /api/metrics` | `queue_depth`, `events_processed`, `tickets_sold`, `capacity` |
| Booking | `GET /health` | połączenie z Redisem |
| | `POST /api/ticket-requests` | `event_id`, `quantity` (1–8), `email`, opcjonalnie `request_id`; zwraca `202` |
| | `GET /api/ticket-requests/{request_id}` | `queued` / `confirmed` / `rejected` + `reason` |

## Konfiguracja

| Zmienna | Domyślnie | Opis |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://tickets:tickets@localhost:5432/tickets` | PostgreSQL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | `5` / `5` | pula połączeń na pod (pody × pula ≤ `max_connections`) |
| `JWT_SECRET` | sekret deweloperski | **w produkcji obowiązkowo własny** (K8s Secret) |
| `JWT_EXPIRE_MINUTES` | `60` | ważność tokenu |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | — | konto admina tworzone przy starcie Core API |
| `WORKER_BATCH_SIZE` | `10` | liczba wiadomości przetwarzanych równolegle przez jednego workera |
| `WORKER_CLAIM_IDLE_MS` | `30000` | po jakim czasie bezczynności wiadomość uznaje się za osieroconą |
| `WORKER_CLAIM_INTERVAL` | `10` | co ile sekund uruchamiać `XAUTOCLAIM` |
| `WORKER_MAX_DELIVERIES` | `5` | limit prób, po którym wiadomość trafia do dead letter |

## Struktura repozytorium

```
├── docker-compose.yml        # postgres, redis, core-api, booking-api, worker, frontend
├── db/init.sql               # schemat bazy (źródło prawdy) + dane startowe
├── k8s/                      # manifesty Kubernetes (w przygotowaniu)
├── frontend/                 # React + Vite
└── backend/
    ├── requirements.txt      # wspólne zależności
    ├── shared/               # database, models, schemas, redis_client, security
    ├── core_api/             # main, dependencies (JWT), routers/{auth,events,users}
    ├── booking_api/          # main, producer
    ├── worker/               # main (pętla konsumenta), tasks, services (logika DB)
    └── scripts/smoke_check.py
```

## Plan prac

- [x] Monorepo, PostgreSQL, Core API, Booking API, worker z atomowym `UPDATE` i idempotencją
- [x] Redis Streams z consumer group, `XAUTOCLAIM`, dead letter, graceful shutdown
- [x] Logowanie JWT i rola admina
- [ ] Frontend: polling statusu rezerwacji, adresy API ze zmiennych `VITE_*`
- [ ] Manifesty Kubernetes / Helm (HPA, KEDA `ScaledObject`, ingress)
- [ ] Metryki Prometheus i dashboard Grafana
- [ ] Testy obciążeniowe w Locust (`LoadTestShape` 0 → 2000, tryb rozproszony): scenariusze
      A (zapis synchroniczny), B (kolejka, stała liczba podów), C (kolejka + autoskalowanie)
