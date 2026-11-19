{{/* Wspólne etykiety i fragmenty szablonów. */}}

{{- define "ticketline.labels" -}}
app.kubernetes.io/part-of: ticketline
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

{{/* Selektor: {{ include "ticketline.selector" (dict "component" "core-api") }} */}}
{{- define "ticketline.selector" -}}
app.kubernetes.io/name: {{ .component }}
{{- end }}

{{- define "ticketline.image" -}}
{{ .root.Values.image.registry }}/{{ .name }}:{{ .root.Values.image.tag }}
{{- end }}

{{/* Zmienne środowiskowe dla serwisów łączących się z PostgreSQL.
     $(POSTGRES_PASSWORD) jest rozwijane przez Kubernetesa z wcześniej zdefiniowanej zmiennej. */}}
{{- define "ticketline.dbEnv" -}}
- name: POSTGRES_PASSWORD
  valueFrom:
    secretKeyRef: { name: ticketline-secrets, key: postgres-password }
- name: DATABASE_URL
  value: postgresql+asyncpg://{{ .Values.db.user }}:$(POSTGRES_PASSWORD)@postgres:5432/{{ .Values.db.name }}
- name: DB_POOL_SIZE
  value: {{ .Values.db.poolSize | quote }}
- name: DB_MAX_OVERFLOW
  value: {{ .Values.db.maxOverflow | quote }}
{{- end }}

{{/* Czekanie na PostgreSQL przed startem serwisu. Bez tego Core API przy pierwszej instalacji
     restartuje się kilka razy (lifespan zakłada konto admina, zanim baza wstanie). */}}
{{- define "ticketline.waitForPostgres" -}}
- name: wait-for-postgres
  image: {{ .Values.postgres.image }}
  command: ["sh", "-c", "until pg_isready -h postgres -p 5432 -U {{ .Values.db.user }}; do sleep 2; done"]
  resources:
    requests: { cpu: 10m, memory: 16Mi }
    limits: { cpu: 100m, memory: 64Mi }
{{- end }}

{{- define "ticketline.redisEnv" -}}
- name: REDIS_URL
  value: redis://redis:6379/0
{{- end }}
