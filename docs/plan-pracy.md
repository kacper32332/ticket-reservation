# Plan pracy inżynierskiej

**Temat:** „Projekt i implementacja skalowalnego systemu mikroserwisowego do obsługi procesów
o wysokim natężeniu ruchu w środowisku Kubernetes”

Ten plan powstał z przeglądu punktu 5 („Wstępny plan realizacji”) sprawozdania z pracowni dyplomowej
w zestawieniu z faktycznym stanem projektu. Część uwag do sprawozdania jest na końcu pliku.

## Teza (propozycja)

> Asynchroniczne kolejkowanie żądań w połączeniu z niezależnym skalowaniem horyzontalnym komponentów
> pozwala obsłużyć skok ruchu od 0 do 2000 użytkowników bez utraty żądań i bez overbookingu, przy stabilnym
> p95 czasu odpowiedzi. Synchroniczny monolit dysponujący tym samym budżetem zasobów tego nie zapewnia.

Teza musi być mierzalna. Nie stawiamy „mikroserwisy są wydajniejsze”, bo przy małym ruchu monolit ma
krótszy czas end-to-end, co wyjdzie w pomiarach i należy to opisać.

## Proporcje

Rdzeń pracy, czyli rozdziały 4–8 (projekt, mechanizmy gwarancji, wdrożenie, weryfikacja i badania),
powinien zajmować około 2/3 objętości. Teoria i przegląd technologii są krótkie i podporządkowane
decyzjom projektowym.

---

## Spis treści z opisem zawartości

### Streszczenie / Abstract
Po polsku i angielsku: problem, rozwiązanie, najważniejszy wynik liczbowy. Słowa kluczowe.

### 1. Wstęp
- **1.1 Motywacja: zjawisko flash crowd w systemach rezerwacyjnych.** Przykłady: sprzedaż biletów,
  zapisy na zajęcia. Dlaczego statyczna infrastruktura zawodzi.
- **1.2 Cel i teza pracy.** Teza w wersji mierzalnej (patrz wyżej).
- **1.3 Zakres pracy.** Co obejmuje: system, wdrożenie w K8s, badania. Czego nie obejmuje: płatności,
  wieloregionowość, Kafka/Istio, klaster bazy danych. Krótkie uzasadnienie.
- **1.4 Układ pracy.** Jedno zdanie na rozdział.

### 2. Podstawy teoretyczne
- **2.1 Architektura monolityczna i mikroserwisowa.** Zalety i koszty obu podejść. Monolit też da się
  skalować horyzontalnie, co ma znaczenie dla uczciwości porównania.
- **2.2 Komunikacja asynchroniczna i wzorzec producent–konsument.** Buforowanie, odsprzęganie,
  kaskadowe awarie przy komunikacji synchronicznej.
- **2.3 Gwarancje dostarczania wiadomości i idempotencja.** At-most-once, at-least-once, exactly-once.
  Dlaczego w praktyce stosuje się at-least-once z idempotentnym konsumentem.
- **2.4 Współbieżny dostęp do danych i problem overbookingu.** Transakcje i ACID, wyścigi
  (lost update), blokady pesymistyczne (`SELECT ... FOR UPDATE`) i warunkowy atomowy `UPDATE`.
- **2.5 Konteneryzacja i orkiestracja w Kubernetes.** Pod, Deployment, Service, deklaratywny model
  i pętla uzgadniania stanu.
- **2.6 Skalowanie horyzontalne: HPA i KEDA.** Skalowanie po metrykach zasobów (CPU) i po metrykach
  zdarzeń (długość kolejki). Opóźnienia reakcji.
- **2.7 Metody badania wydajności systemów webowych.** Percentyle zamiast średniej, przepustowość,
  modele obciążenia otwarte i zamknięte oraz ich wpływ na wyniki (coordinated omission).

### 3. Analiza rozwiązań i dobór technologii
- **3.1 Modele infrastruktury dla ruchu skokowego.** VPS ze skalowaniem pionowym, IaaS z Auto Scaling
  Groups, Serverless/FaaS, Kubernetes. Jedna tabela porównawcza (czas reakcji, koszt, kontrola,
  vendor lock-in, obsługa połączeń do bazy) plus wniosek. Maksymalnie około 2 strony.
- **3.2 Dobór stosu technologicznego.** Tabela „wybrane / alternatywy / uzasadnienie”: Python +
  FastAPI (vs Django, Flask, Go), PostgreSQL (vs NoSQL), Kubernetes (vs Swarm, Nomad), Locust
  (vs JMeter, k6), Prometheus + Grafana.
- **3.3 Wybór brokera wiadomości.** Redis Streams vs RabbitMQ vs Apache Kafka. Argumenty: consumer
  group z potwierdzeniami (`XACK`), odzyskiwanie wiadomości (`XAUTOCLAIM`), gotowy skaler KEDA
  `redis-streams`, prostota utrzymania. Dlaczego odrzucono kolejkę na liście (`BLPOP` gubi żądania)
  i Arq (sorted set niewidoczny dla KEDA).

### 4. Wymagania i projekt systemu
- **4.1 Wymagania funkcjonalne.** Przeglądanie oferty, rezerwacja, sprawdzanie statusu, konto
  i logowanie, historia rezerwacji, dodawanie wydarzeń przez administratora.
- **4.2 Wymagania niefunkcjonalne.** Brak overbookingu, brak utraty przyjętych żądań, brak duplikatów,
  docelowa liczba użytkowników i dopuszczalne p95, skalowalność, odporność na awarię pojedynczego poda.
- **4.3 Architektura systemu: podział według charakterystyki obciążenia.** Core API (odczyt
  i zarządzanie), Booking API (producent, bez dostępu do bazy), Worker (konsument). Diagram komponentów
  i diagram wdrożenia (UML).
- **4.4 Przepływ procesu rezerwacji.** Diagram sekwencji: `POST` → `XADD` → `202 Accepted` → worker →
  zapis w bazie → status w Redisie → odpytywanie klienta.
- **4.5 Model danych i ograniczenia integralności.** Tabele `users`, `events`, `bookings`.
  `CHECK (available >= 0)` i `UNIQUE (request_id)` jako ostatnia linia obrony poprawności. `init.sql`
  jako źródło prawdy schematu.
- **4.6 Cykl życia wiadomości w kolejce.** Diagram stanów: w strumieniu → w PEL → potwierdzona
  i usunięta / przejęta przez `XAUTOCLAIM` / dead letter.
- **4.7 Kompromisy projektowe.** Wzorzec Shared Database (spójność transakcji vs niezależność serwisów),
  spójność ostateczna (klient czeka na status), pojedyncze instancje Postgresa i Redisa (ograniczenie
  i ścieżka rozwoju), status w Redisie z TTL.

### 5. Implementacja
- **5.1 Struktura repozytorium i kod współdzielony.** Monorepo, pakiet `shared/`, wspólne zależności.
- **5.2 Core API: oferta, uwierzytelnianie i autoryzacja.** JWT (HS256), Argon2id, rola administratora,
  ochrona przed enumeracją kont.
- **5.3 Booking API: przyjmowanie żądań.** Atomowe `MULTI/EXEC` (status + `XADD`), klucz idempotencji,
  brak `MAXLEN` i jego uzasadnienie.
- **5.4 Worker: atomowa rezerwacja miejsc i idempotencja.** Warunkowy `UPDATE ... RETURNING`,
  `INSERT ... ON CONFLICT DO NOTHING`, wycofanie transakcji przy duplikacie.
- **5.5 Odzyskiwanie wiadomości, dead letter i bezpieczne wyłączanie.** `XACK` po COMMIT,
  `XAUTOCLAIM`, limit prób, `ticket:dead`, obsługa SIGTERM i wyrejestrowanie konsumenta.
- **5.6 Wariant monolityczny do badań porównawczych.** Ta sama logika rezerwacji wywoływana
  synchronicznie. Dlaczego to uczciwy punkt odniesienia.
- **5.7 Interfejs użytkownika.** Krótko: SPA w React, odpytywanie statusu z backoffem. Zrzuty ekranu.

### 6. Wdrożenie w środowisku Kubernetes
- **6.1 Obrazy kontenerów.** Jeden akapit: wspólny kontekst budowania, obraz `slim`.
- **6.2 Definicja wdrożenia (Helm).** Deployment, Service, ConfigMap, Secret, Ingress.
  `resources.requests/limits`, sondy readiness i liveness, `terminationGracePeriodSeconds`.
  Limit `maxReplicas × pula połączeń < max_connections`.
- **6.3 Autoskalowanie API (HPA) i workera (KEDA).** Dlaczego HPA po CPU nie nadaje się do workera
  (worker głównie czeka na bazę, CPU nie odzwierciedla zaległości). `ScaledObject` z `lagCount`.
  Parametry: `minReplicas`, `behavior.scaleUp`, `pollingInterval`.
- **6.4 Monitoring: Prometheus i Grafana.** Metryki HTTP, metryki kolejki (XLEN, lag, PEL), liczba podów.
  Dashboard użyty w badaniach.

### 7. Weryfikacja poprawności
- **7.1 Testy end-to-end.** `smoke_check.py`: uprawnienia, idempotencja, równoległe rezerwacje, bilans,
  brak overbookingu, dead letter, osierocona wiadomość.
- **7.2 Testy odporności na awarie.** Usuwanie podów workera i Booking API w trakcie skoku ruchu.
  Bilans `202 = confirmed + rejected` i brak overbookingu po awarii.

### 8. Badania wydajnościowe
- **8.1 Metodyka.** Scenariusze A (monolit, stałe repliki), A+ (monolit, HPA), B (mikroserwisy,
  kolejka, stałe pody), C (mikroserwisy, kolejka, HPA + KEDA). Ten sam budżet zasobów, te same dane
  startowe, generator poza klastrem, rozgrzewka, reset bazy, 3–5 powtórzeń. Profil obciążenia
  (`LoadTestShape`, poziomy 100/500/1000/2000) i mieszany ruch (~80% oferta, ~20% rezerwacje). Środowisko
  sprzętowe. Lista metryk.
- **8.2 Czasy odpowiedzi i odsetek błędów.** p50/p95/p99 osobno dla przeglądania, przyjęcia rezerwacji
  i statusu. Punkt przecięcia w funkcji liczby użytkowników.
- **8.3 Izolacja obciążenia między komponentami.** p95 `GET /api/events` pod ruchem rezerwacji:
  monolit vs mikroserwisy.
- **8.4 Dynamika autoskalowania.** Liczba podów, głębokość kolejki i CPU w czasie. Czas reakcji HPA
  i KEDA, czas opróżnienia kolejki, efektywność (sekundy CPU na 1000 potwierdzonych rezerwacji).
- **8.5 Wąskie gardło bazy danych i jego ograniczenie.** Wypłaszczenie przepustowości w funkcji liczby
  workerów (gorący wiersz `events`). Paczkowanie w workerze, z pomiarem przed i po.
- **8.6 Dyskusja wyników i zagrożenia ich trafności.** Tabela „co zyskujemy / co płacimy”.
  Ograniczenia środowiska (laptop vs klaster), model zamknięty w Locuście, pojedyncze instancje
  Postgresa i Redisa.

### 9. Podsumowanie
- **9.1 Weryfikacja tezy i wnioski.**
- **9.2 Ograniczenia.**
- **9.3 Kierunki rozwoju.** PgBouncer, repliki do odczytu, osobni użytkownicy bazy dla serwisów,
  wstępne odrzucanie „wyprzedane” w Redisie, powiązanie rezerwacji z kontem w Booking API.

### Bibliografia · Spis rysunków i tabel · Załączniki
Instrukcja uruchomienia, adres repozytorium, pełne wyniki pomiarów.

---

## Uwagi do sprawozdania z pracowni (do poprawienia w tekście pracy)

**Punkt 5 (plan realizacji):**
- Etap 2: „skrypty migracyjne” nie istnieją. Schemat to `db/init.sql`, bez Alembica: nazwać to wprost
  albo uzasadnić. Docker Compose to tylko środowisko developerskie, nie osobny rozdział.
- Etap 3: system ma trzy serwisy, a nie dwa podsystemy. Autoryzacja jest w Core API. Workery nie używają
  FastAPI. Brakuje opisu gwarancji poprawności (atomowy `UPDATE`, idempotencja, at-least-once,
  `XAUTOCLAIM`, dead letter, graceful shutdown) i wariantu monolitu.
- Etap 4: HPA po CPU dla workerów to błąd koncepcyjny, bo workera skaluje KEDA po długości kolejki.
  Lista obiektów K8s jest niepełna: Secret, Ingress, HPA, ScaledObject, sondy, `resources`, Helm.
- Etap 5: „stała liczba workerów (monolit/brak autoskalowania)” miesza architekturę ze sposobem
  skalowania. Potrzebne są scenariusze A, A+, B i C. Brakuje zasad uczciwego porównania, metryk
  poprawności, testów odporności, analizy wąskiego gardła i zagrożeń trafności.
- Etap 1: teza jest zbyt ogólna, a brakuje rozdziału z wymaganiami.

**Rozdziały 1–4:**
- 1.2: workery nie „przyjmują zgłoszeń”. Przyjmuje je Booking API, workery je przetwarzają.
- 2.4: „logarytmiczny wzrost” to błąd, bo wzrost logarytmiczny zwalnia. Flash crowd to wzrost skokowy.
- 3.4: przykład „asynchroniczny worker FastAPI” skalowany po CPU jest niezgodny z projektem
  (worker bez FastAPI, skalowany przez KEDA).
- 4.2: „Redis znacznie szybszy od RabbitMQ” to teza bez źródła. Właściwe argumenty: Redis Streams
  z consumer group, skaler KEDA, prostota utrzymania.
- 4.3: brak KEDA.
- 4.4: zamiast „Code-as-Infrastructure” powinno być „testy jako kod” (*tests as code*).
- Ogólnie: stonować język marketingowy („absolutny standard”, „drastycznie”, „nieporównywalnie”).
