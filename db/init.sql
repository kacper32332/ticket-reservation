-- Schemat bazy danych systemu rezerwacji (wzorzec Shared Database).
-- Plik jest wykonywany automatycznie przez obraz postgres przy PIERWSZYM
-- starcie kontenera (pusty wolumen). Po zmianie schematu: docker compose down -v.

CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_admin      BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE events (
    id         VARCHAR(32)   PRIMARY KEY,
    name       VARCHAR(255)  NOT NULL,
    venue      VARCHAR(255)  NOT NULL,
    city       VARCHAR(128)  NOT NULL,
    starts_at  TIMESTAMPTZ   NOT NULL,
    capacity   INTEGER       NOT NULL CHECK (capacity > 0),
    -- Licznik wolnych miejsc. Worker zmniejsza go jednym atomowym UPDATE,
    -- a CHECK gwarantuje, że nigdy nie zejdzie poniżej zera (brak overbookingu).
    available  INTEGER       NOT NULL CHECK (available >= 0 AND available <= capacity),
    price      NUMERIC(10,2) NOT NULL CHECK (price >= 0),
    accent     VARCHAR(16)   NOT NULL DEFAULT 'coral',
    created_at TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE TABLE bookings (
    id         BIGSERIAL   PRIMARY KEY,
    -- Klucz idempotencji: to samo żądanie przetworzone dwa razy
    -- (retry, ponowne dostarczenie z kolejki) nie utworzy drugiej rezerwacji.
    request_id VARCHAR(64) NOT NULL UNIQUE,
    event_id   VARCHAR(32) NOT NULL REFERENCES events(id),
    user_id    INTEGER     REFERENCES users(id),
    email      VARCHAR(255) NOT NULL,
    quantity   INTEGER     NOT NULL CHECK (quantity BETWEEN 1 AND 8),
    status     VARCHAR(16) NOT NULL CHECK (status IN ('confirmed', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_bookings_event_id ON bookings(event_id);
CREATE INDEX idx_bookings_email    ON bookings(email);

-- Dane startowe
INSERT INTO events (id, name, venue, city, starts_at, capacity, available, price, accent) VALUES
    ('evt-001', 'The Weeknd',       'National Stadium',        'Warsaw', '2027-06-24 20:00+02', 30000, 11580,  89.00, 'coral'),
    ('evt-002', 'Open''er Festival', 'Gdynia-Kosakowo Airport', 'Gdynia', '2027-07-01 16:00+02', 60000, 18400, 149.00, 'mint'),
    ('evt-003', 'Formula E Berlin', 'Tempelhof Circuit',       'Berlin', '2027-09-12 14:00+02', 22000,  2250, 119.00, 'yellow');
