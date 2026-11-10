ticket-system-monorepo/
├── docker-compose.yml          # Konfiguracja środowiska lokalnego (Postgres, Redis, serwisy)
├── README.md                   # Dokumentacja projektu
│
├── k8s/                        # Manifesty Kubernetes
│   ├── ingress.yaml            # Routing ruchu (API Gateway)
│   ├── postgres.yaml           # Deployment i Service bazy danych
│   ├── redis.yaml              # Deployment i Service kolejki
│   ├── core-api.yaml           # Deployment i HPA dla Core API
│   ├── booking-api.yaml        # Deployment i HPA dla Booking API
│   └── worker.yaml             # Deployment i skalowanie Workera (np. KEDA)
│
├── db/
│   └── init.sql                # Schemat PostgreSQL + dane startowe (ładowany przez docker-compose)
│
├── frontend/                   # Aplikacja React
│   ├── package.json
│   └── src/                    # Kod źródłowy frontendu
│
└── backend/                    # Cały kod w języku Python
    ├── requirements.txt        # Wspólna lista zależności (np. fastapi, sqlalchemy, arq)
    │
    ├── shared/                 # KOD WSPÓŁDZIELONY (Importowany przez wszystkie serwisy)
    │   ├── __init__.py
    │   ├── database.py         # Konfiguracja połączenia z PostgreSQL (np. SQLAlchemy)
    │   ├── models.py           # Definicje tabel w bazie (np. User, Event, Ticket)
    │   ├── schemas.py          # Modele Pydantic (walidacja danych wejściowych/wyjściowych)
    │   └── redis_client.py     # Konfiguracja połączenia z pulą Redisa
    │
    ├── core_api/               # MIKROSERWIS 1: Zarządzanie i Odczyt
    │   ├── Dockerfile          # Instrukcja budowania kontenera dla Core API
    │   ├── main.py             # Inicjalizacja FastAPI
    │   └── routers/            # Podział na logiczne ścieżki (Endpoints)
    │       ├── auth.py         # Logowanie / JWT
    │       ├── events.py       # Dodawanie i pobieranie listy wydarzeń
    │       └── users.py        # Profil użytkownika i historia biletów
    │
    ├── booking_api/            # MIKROSERWIS 2: Lejek / Producent (Zderzak)
    │   ├── Dockerfile          # Instrukcja budowania kontenera dla Booking API
    │   ├── main.py             # Inicjalizacja FastAPI (tylko /book)
    │   └── producer.py         # Logika tworzenia zadań i wysyłania ich do Redisa
    │
    └── worker/                 # MIKROSERWIS 3: Konsument w tle
        ├── Dockerfile          # Instrukcja budowania kontenera dla Workera
        ├── main.py             # Plik startowy dla biblioteki Arq (nie ma tu FastAPI!)
        ├── tasks.py            # Funkcje wykonujące zadania (np. process_booking)
        └── services.py         # Ciężka logika biznesowa (sprawdzanie blokad, zapis do DB)