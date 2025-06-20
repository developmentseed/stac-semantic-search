{{/*
Expand the name of the chart.
*/}}
{{- define "stac-search.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "stac-search.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "stac-search.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "stac-search.labels" -}}
helm.sh/chart: {{ include "stac-search.chart" . }}
{{ include "stac-search.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
API Selector labels
*/}}
{{- define "stac-search.api.selectorLabels" -}}
app.kubernetes.io/name: {{ include "stac-search.name" . }}-api
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: api
{{- end }}

{{/*
Frontend Selector labels
*/}}
{{- define "stac-search.frontend.selectorLabels" -}}
app.kubernetes.io/name: {{ include "stac-search.name" . }}-frontend
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: frontend
{{- end }}

{{/*
Common selector labels
*/}}
{{- define "stac-search.selectorLabels" -}}
app.kubernetes.io/name: {{ include "stac-search.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "stac-search.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "stac-search.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
API image name
*/}}
{{- define "stac-search.api.image" -}}
{{- $registryName := .Values.global.imageRegistry -}}
{{- $repositoryName := .Values.api.image.repository -}}
{{- $tag := .Values.api.image.tag | toString -}}
{{- if $registryName }}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}
{{- else }}
{{- printf "%s:%s" $repositoryName $tag -}}
{{- end }}
{{- end }}

{{/*
Frontend image name
*/}}
{{- define "stac-search.frontend.image" -}}
{{- $registryName := .Values.global.imageRegistry -}}
{{- $repositoryName := .Values.frontend.image.repository -}}
{{- $tag := .Values.frontend.image.tag | toString -}}
{{- if $registryName }}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}
{{- else }}
{{- printf "%s:%s" $repositoryName $tag -}}
{{- end }}
{{- end }}

{{/*
API service name
*/}}
{{- define "stac-search.api.serviceName" -}}
{{- printf "%s-api" (include "stac-search.fullname" .) }}
{{- end }}

{{/*
Frontend service name
*/}}
{{- define "stac-search.frontend.serviceName" -}}
{{- printf "%s-frontend" (include "stac-search.fullname" .) }}
{{- end }}

{{/*
Init container image name
*/}}
{{- define "stac-search.initContainer.image" -}}
{{- $registryName := .Values.global.imageRegistry -}}
{{- $repositoryName := .Values.api.initContainer.image.repository -}}
{{- $tag := .Values.api.initContainer.image.tag | toString -}}
{{- if $registryName }}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}
{{- else }}
{{- printf "%s:%s" $repositoryName $tag -}}
{{- end }}
{{- end }}
