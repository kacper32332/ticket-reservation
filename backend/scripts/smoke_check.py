"""Szybki test całej ścieżki rezerwacji.

Uruchomienie (jedna linijka, z folderu projektu):
    docker compose exec core-api python scripts/smoke_check.py
Opcje:
    --requests 200 --capacity 20 --parallel 50
    --stream-tests   dodatkowo: odzyskiwanie osieroconej wiadomości (XAUTOCLAIM,
                     trwa ~40 s) i dead letter. Wymaga pakietu redis (jest w obrazie).

Podstawowa część używa tylko biblioteki standardowej.
"""

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

CORE = os.getenv("CORE_URL", "http://core-api:8000")
BOOKING = os.getenv("BOOKING_URL", "http://booking-api:8000")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@ticketline.pl")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin12345")


def parse(raw):
    try:
        return json.loads(raw or "null")
    except ValueError:
        return {"raw": raw.decode(errors="replace")[:200]}


def call(method, url, body=None, token=None, form=None):
    headers = {}
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, parse(resp.read())
    except urllib.error.HTTPError as err:
        return err.code, parse(err.read())
    except (urllib.error.URLError, OSError) as err:
        return 0, {"error": str(err)}


def login(email, password):
    status, data = call("POST", f"{CORE}/api/auth/login", form={"username": email, "password": password})
    return status, (data or {}).get("access_token")


def check(name, ok, detail=""):
    print(f"[{'OK ' if ok else 'BŁĄD'}] {name} {detail}")
    return ok


def wait_for_status(request_id, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        _, data = call("GET", f"{BOOKING}/api/ticket-requests/{request_id}")
        if data and data.get("status") != "queued":
            return data
        time.sleep(0.2)
    return {"status": "timeout"}


def stream_tests(run, event_id):
    """Symulacja padu workera i wiadomości-trucizny bezpośrednio na strumieniu."""
    import sys

    import redis  # tylko tutaj - reszta skryptu działa na samej stdlib

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from shared.redis_client import (CONSUMER_GROUP, DEAD_LETTER_KEY, STREAM_FIELD,
                                     STREAM_KEY, status_key)
    r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)
    results = []

    print("== 7. Dead letter: wiadomość w złym formacie")
    dead_before = r.xlen(DEAD_LETTER_KEY)
    r.xadd(STREAM_KEY, {STREAM_FIELD: "to nie jest JSON"})
    deadline = time.time() + 10
    while time.time() < deadline and r.xlen(DEAD_LETTER_KEY) == dead_before:
        time.sleep(0.2)
    results.append(check("trafiła do ticket:dead", r.xlen(DEAD_LETTER_KEY) == dead_before + 1))

    print("== 8. Pad workera: wiadomość pobrana i nigdy niepotwierdzona (XAUTOCLAIM)")
    request_id = f"{run}-orphan"
    ghost = f"ghost-{run}"
    message = {"request_id": request_id, "event_id": event_id, "quantity": 1,
               "email": "orphan@ticketline.pl", "created_at": "2027-01-01T10:00:00Z"}
    # Jedna transakcja: XADD + natychmiastowe pobranie przez "martwego" konsumenta,
    # zanim zdąży je zobaczyć prawdziwy worker. Prawdziwe workery mogą jednak
    # wyprzedzić ghosta - wtedy test nie ma sensu, więc to sprawdzamy.
    r.hset(status_key(request_id), mapping={"status": "queued"})
    with r.pipeline(transaction=True) as pipe:
        pipe.xadd(STREAM_KEY, {STREAM_FIELD: json.dumps(message)})
        pipe.xreadgroup(CONSUMER_GROUP, ghost, {STREAM_KEY: ">"}, count=1000)
        message_id, claimed = pipe.execute()
    claimed_ids = [mid for _, msgs in claimed for mid, _ in msgs]
    if message_id not in claimed_ids:
        results.append(check("ghost pobrał wiadomość", False, "(worker był szybszy - uruchom ponownie)"))
        return results
    print(f"   ghost trzyma {len(claimed_ids)} wiadomości; czekam na XAUTOCLAIM (do ~60 s)...")
    start = time.time()
    final = wait_for_status(request_id, timeout=90)
    # Wydarzenie może być już wyprzedane po kroku 6 - liczy się, że wiadomość
    # została przetworzona (confirmed albo rejected/sold_out), a nie zgubiona.
    processed = final["status"] in ("confirmed", "rejected") and final.get("reason") != "processing_failed"
    results.append(check("osierocona wiadomość przetworzona", processed,
                         f"({final}, po {time.time() - start:.0f} s)"))
    ghost_pending = r.xpending_range(STREAM_KEY, CONSUMER_GROUP, "-", "+", 10, consumername=ghost)
    results.append(check("PEL ghosta pusty", not ghost_pending))
    r.xgroup_delconsumer(STREAM_KEY, CONSUMER_GROUP, ghost)
    return results


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--requests", type=int, default=50)
    p.add_argument("--capacity", type=int, default=10)
    p.add_argument("--parallel", type=int, default=20)
    p.add_argument("--stream-tests", action="store_true")
    a = p.parse_args()
    run = uuid4().hex[:6]
    results = []

    print("== 1. Health")
    core_health, booking_health = call("GET", f"{CORE}/health")[1], call("GET", f"{BOOKING}/health")[1]
    healthy = [check("Core API + PostgreSQL", core_health.get("status") == "healthy", str(core_health)),
               check("Booking API + Redis", booking_health.get("status") == "healthy", str(booking_health))]
    if not all(healthy):
        print("Serwisy nie są gotowe - sprawdź: docker compose ps / docker compose logs")
        raise SystemExit(1)

    print("== 2. Oferta")
    status, events = call("GET", f"{CORE}/api/events")
    results.append(check("GET /api/events", status == 200, f"({len(events)} wydarzeń)"))

    print("== 3. Logowanie i uprawnienia")
    user_email, user_password = f"smoke-{run}@ticketline.pl", f"haslo-{run}"
    event_id = f"evt-{run}"
    new_event = {"id": event_id, "name": f"Smoke {run}", "venue": "Aula", "city": "Kraków",
                 "starts_at": "2027-01-01T10:00:00Z", "capacity": a.capacity, "price": 0}
    status, _ = call("POST", f"{CORE}/api/auth/register", {"email": user_email, "password": user_password})
    results.append(check("rejestracja (201)", status == 201))
    status, _ = call("POST", f"{CORE}/api/auth/register", {"email": user_email, "password": user_password})
    results.append(check("ponowna rejestracja (409)", status == 409))
    status, _ = login(user_email, "zle-haslo")
    results.append(check("złe hasło (401)", status == 401))
    status, user_token = login(user_email, user_password)
    results.append(check("logowanie użytkownika", status == 200 and bool(user_token)))
    status, me = call("GET", f"{CORE}/api/auth/me", token=user_token)
    results.append(check("GET /api/auth/me", status == 200 and me.get("email") == user_email))
    status, _ = call("GET", f"{CORE}/api/auth/me", token="zly.token.jwt")
    results.append(check("fałszywy token (401)", status == 401))
    status, _ = call("POST", f"{CORE}/api/events", new_event)
    results.append(check("POST /api/events bez tokenu (401)", status == 401))
    status, _ = call("POST", f"{CORE}/api/events", new_event, token=user_token)
    results.append(check("POST /api/events jako użytkownik (403)", status == 403))
    status, admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    results.append(check("logowanie admina", status == 200 and bool(admin_token)))

    print("== 4. Nowe wydarzenie (admin)")
    status, _ = call("POST", f"{CORE}/api/events", new_event, token=admin_token)
    results.append(check("POST /api/events", status == 201, f"({event_id}, {a.capacity} miejsc)"))

    print("== 5. Pojedyncza rezerwacja + idempotencja")
    body = {"event_id": event_id, "quantity": 1, "email": user_email, "request_id": f"{run}-single"}
    status, _ = call("POST", f"{BOOKING}/api/ticket-requests", body)
    results.append(check("POST zwraca 202", status == 202))
    results.append(check("status = confirmed", wait_for_status(body["request_id"])["status"] == "confirmed"))
    call("POST", f"{BOOKING}/api/ticket-requests", body)
    dup = wait_for_status(body["request_id"])
    results.append(check("duplikat rozpoznany", dup.get("reason") == "duplicate", str(dup)))
    status, mine = call("GET", f"{CORE}/api/users/me/bookings", token=user_token)
    results.append(check("GET /api/users/me/bookings", status == 200 and len(mine) == 1, f"({len(mine or [])} szt.)"))

    print(f"== 6. Flash crowd: {a.requests} żądań, {a.parallel} równolegle")
    def book(i):
        rid = f"{run}-{i}"
        status, _ = call("POST", f"{BOOKING}/api/ticket-requests",
                         {"event_id": event_id, "quantity": 1, "email": f"u{i}@test.pl", "request_id": rid})
        return rid, status
    start = time.time()
    with ThreadPoolExecutor(a.parallel) as pool:
        sent = list(pool.map(book, range(a.requests)))
    print(f"   wysłano w {time.time() - start:.2f} s")
    results.append(check("wszystkie przyjęte (202)", all(s == 202 for _, s in sent)))
    with ThreadPoolExecutor(a.parallel) as pool:
        final = [r["status"] for r in pool.map(lambda x: wait_for_status(x[0]), sent)]
    print(f"   kolejka opróżniona po {time.time() - start:.2f} s od startu")
    confirmed, rejected = final.count("confirmed"), final.count("rejected")
    print(f"   potwierdzone: {confirmed}, odrzucone: {rejected}, inne: {len(final) - confirmed - rejected}")
    expected = min(a.capacity - 1, a.requests)  # 1 miejsce zajęła rezerwacja z kroku 5
    results.append(check("brak overbookingu", confirmed == expected, f"(oczekiwano {expected})"))
    results.append(check("nic nie zgubione", confirmed + rejected == a.requests))
    _, ev = call("GET", f"{CORE}/api/events/{event_id}")
    results.append(check("available = 0" if a.requests >= a.capacity - 1 else "available",
                         ev["available"] == a.capacity - 1 - expected, f"(available={ev['available']})"))
    time.sleep(0.5)  # XACK + XDEL następują chwilę po zapisaniu statusu
    _, metrics = call("GET", f"{CORE}/api/metrics")
    results.append(check("strumień pusty (XACK + XDEL)", metrics.get("queue_depth") == 0,
                         f"(queue_depth={metrics.get('queue_depth')})"))

    if a.stream_tests:
        results.extend(stream_tests(run, event_id))

    print(f"\nWynik: {sum(results)}/{len(results)} OK")
    raise SystemExit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
