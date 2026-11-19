# Kubernetes — Ticketline

| Plik | Co |
| --- | --- |
| `k3d-cluster.yaml` | lokalny klaster k3d `ticketline` (1 server + 2 agenty, Ingress na `localhost:8080`) |
| `deploy.ps1` | budowa obrazów → `k3d image import` → `helm upgrade --install` → rollout |
| `ticketline/` | Helm chart: PostgreSQL, Redis, Core API, Booking API, worker, Ingress |
| `ticketline/values.yaml` | domyślne wartości = scenariusz **C** (HPA dla API, KEDA dla workera) |
| `ticketline/values-static.yaml` | scenariusz **B** (stała liczba podów) |

## Szybki start

Wszystkie polecenia uruchamiasz z katalogu głównego repo.

```powershell
k3d cluster create --config k8s/k3d-cluster.yaml
```

```powershell
.\k8s\deploy.ps1
```

```powershell
kubectl -n ticketline exec deploy/core-api -- python scripts/smoke_check.py --requests 200 --capacity 20 --parallel 50
```

API przez Ingress: http://localhost:8080/api/events (rezerwacje: `/api/ticket-requests`).

Inne warianty:

```powershell
.\k8s\deploy.ps1 -SkipBuild
```

```powershell
.\k8s\deploy.ps1 -Values values-static.yaml
```

```powershell
helm uninstall ticketline -n ticketline
```

`helm uninstall` nie usuwa wolumenów (PVC) bazy i Redisa. Pełny reset bazy (init.sql wykona się ponownie):

```powershell
kubectl delete namespace ticketline
```

## KEDA (autoskalowanie workera)

ScaledObject renderuje się tylko wtedy, gdy w klastrze są CRD KEDA. Bez KEDA worker ma stałą liczbę
replik (`worker.replicas`). Instalacja KEDA (jednorazowo):

```powershell
helm repo add kedacore https://kedacore.github.io/charts
```

```powershell
helm install keda kedacore/keda --namespace keda --create-namespace
```

Po instalacji ponownie uruchom `.\k8s\deploy.ps1 -SkipBuild`.

## Decyzje w charcie (materiał do pracy)

- **Walidacja budżetu połączeń** (`templates/validate.yaml`): `helm install` przerywa wdrożenie, jeśli
  `(maxReplicas core + worker) × (pula + overflow) + 10 > max_connections`. Booking API się nie liczy,
  bo nie łączy się z bazą.
- **`db/init.sql` jako jedyne źródło schematu:** przekazywany przez `--set-file`, nie kopiowany do charta.
- **Redis z AOF na PVC:** restart poda Redisa nie gubi kolejki (`appendfsync everysec`, czyli
  do utraty co najwyżej ~1 s danych).
- **Booking API bez zmiennych bazy:** zasada architektury egzekwowana w manifeście.
- **HPA Booking API:** `scaleUp` bez okna stabilizacji (+100% co 15 s), `scaleDown` po 120 s.
- **KEDA:** scaler `redis-streams`, `lagCount` (wiadomości nieodczytane przez grupę), `pollingInterval: 5`
  zamiast domyślnych 30 s.
- **Worker:** `terminationGracePeriodSeconds: 30` na dokończenie paczki po SIGTERM, bez probe'ów HTTP.
- **`initContainer wait-for-postgres`** w Core API i workerze, żeby uniknąć restartów przy pierwszym starcie.
- **Usługi na porcie 8000:** `smoke_check.py` działa w klastrze bez zmian adresów.
