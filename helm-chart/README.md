# STAC Semantic Search Helm Chart

This Helm chart deploys the STAC Semantic Search application, which consists of:
- **API**: FastAPI backend for semantic search of STAC collections and items
- **Frontend**: Streamlit web interface for natural language queries

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+
- Docker images for both API and frontend services

## Installation

### 1. Build and Push Docker Images

First, build and push your Docker images to a container registry:

```bash
# Build API image
docker build -t your-registry/stac-search-api:latest .

# Build Frontend image  
docker build -t your-registry/stac-search-frontend:latest ./frontend

# Push images
docker push your-registry/stac-search-api:latest
docker push your-registry/stac-search-frontend:latest
```

### 2. Install the Helm Chart

```bash
# Add your repository prefix to values
helm install stac-search ./helm-chart \
  --set api.image.repository=your-registry/stac-search-api \
  --set frontend.image.repository=your-registry/stac-search-frontend \
  --set ingress.hosts[0].host=stac-search.yourdomain.com
```

Or create a custom values file:

```bash
cp helm-chart/values.yaml my-values.yaml
# Edit my-values.yaml with your configuration
helm install stac-search ./helm-chart -f my-values.yaml
```

### 3. Access the Application

After installation, follow the NOTES output to access your application. Typically:

```bash
# Port forward to access locally
kubectl port-forward service/stac-search-frontend 8501:8501

# Then visit http://localhost:8501
```

## Configuration

### Key Configuration Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| `api.image.repository` | API Docker image repository | `stac-search-api` |
| `api.image.tag` | API Docker image tag | `latest` |
| `api.initContainer.enabled` | Enable init container to pre-load STAC data | `true` |
| `api.initContainer.image.repository` | Init container image repository | `stac-search-api` |
| `api.initContainer.image.tag` | Init container image tag | `latest` |
| `api.initContainer.resources` | Init container resource limits and requests | See values.yaml |
| `frontend.image.repository` | Frontend Docker image repository | `stac-search-frontend` |
| `frontend.image.tag` | Frontend Docker image tag | `latest` |
| `ingress.enabled` | Enable ingress | `true` |
| `ingress.hosts[0].host` | Hostname for ingress | `stac-search.local` |

### Example Custom Values

```yaml
# Custom values.yaml
api:
  image:
    repository: ghcr.io/your-org/stac-search-api
    tag: "v1.0.0"
  resources:
    requests:
      memory: "2Gi"
      cpu: "1000m"

frontend:
  image:
    repository: ghcr.io/your-org/stac-search-frontend
    tag: "v1.0.0"

ingress:
  hosts:
    - host: stac-search.example.com
      paths:
        - path: /
          pathType: Prefix
          service: frontend
  tls:
    - secretName: stac-search-tls
      hosts:
        - stac-search.example.com
  
  # API subdomain configuration
  api:
    enabled: true
    hosts:
      - host: api.stac-search.example.com
        paths:
          - path: /
            pathType: Prefix
    tls:
      - secretName: stac-search-api-tls
        hosts:
          - api.stac-search.example.com
```

## STAC Data Loading with Init Container

The chart includes an init container that automatically loads STAC catalog data into the vector database before the API starts. This ensures that the API has searchable data available immediately upon startup.

### How It Works

1. **Init Container Execution**: Before the API container starts, the init container runs the `stac_search.load` module
2. **Data Loading**: The init container fetches collections from the configured STAC catalog and generates embeddings
3. **Storage**: The embeddings are stored in ChromaDB in the shared data volume
4. **API Startup**: Once data loading is complete, the API container starts with pre-loaded searchable data

### Configuration

The init container uses the same STAC catalog configuration as the API:

```yaml
api:
  env:
    STAC_CATALOG_URL: "https://planetarycomputer.microsoft.com/api/stac/v1"
  
  initContainer:
    enabled: true  # Set to false to disable data pre-loading
    resources:
      limits:
        cpu: 1000m
        memory: 2Gi
      requests:
        cpu: 500m
        memory: 1Gi
```

### Disabling Init Container

If you prefer to load data manually or have pre-existing data, you can disable the init container:

```yaml
api:
  initContainer:
    enabled: false
```

### Multiple Catalogs

To load data from multiple STAC catalogs, you can disable the init container and manually run the load script with different configurations after deployment.

## Architecture

```
┌─────────────────┐    ┌─────────────────┐
│                 │    │                 │
│   Frontend      │────│      API        │
│  (Streamlit)    │    │   (FastAPI)     │
│   Port: 8501    │    │   Port: 8000    │
│                 │    │                 │
└─────────────────┘    └─────────────────┘
         │                       │
         │                       │
    ┌─────────┐              ┌─────────┐
    │ Ingress │              │ChromaDB │
    │         │              │  Data   │
    └─────────┘              └─────────┘
```

**Note**: ChromaDB data is stored in ephemeral storage and will be lost when pods restart. The init container will reload the data automatically on pod startup.

## Development

### Local Development with Helm

```bash
# Render templates locally
helm template stac-search ./helm-chart

# Debug with custom values
helm template stac-search ./helm-chart -f my-values.yaml --debug

# Validate chart
helm lint ./helm-chart
```

### Testing

```bash
# Dry run installation
helm install stac-search ./helm-chart --dry-run

# Test with different values
helm install stac-search ./helm-chart -f test-values.yaml --dry-run
