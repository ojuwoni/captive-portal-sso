# Dockerfile
FROM python:3.11-slim

WORKDIR /opt/captive-portal

# Dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    nftables \
    iproute2 \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code application
COPY . .

# Port
EXPOSE 8000

# Utilisateur non-root (optionnel, désactiver si nftables nécessite root)
# RUN useradd -m portal
# USER portal

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')" || exit 1

# Démarrage
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
