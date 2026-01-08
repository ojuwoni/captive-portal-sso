#!/bin/bash
# install.sh
# Installation automatique du portail captif
# Exécuter avec: sudo bash install.sh

set -e

echo "=== Installation Portail Captif SSO ==="

# Variables
INSTALL_DIR="/opt/captive-portal"
PYTHON_VERSION="python3"

# Vérification root
if [ "$EUID" -ne 0 ]; then
    echo "Erreur: Exécuter avec sudo"
    exit 1
fi

# Dépendances système
echo "[1/7] Installation dépendances système..."
apt-get update
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    redis-server \
    nginx \
    nftables \
    iproute2

# Créer répertoire
echo "[2/7] Création répertoire $INSTALL_DIR..."
mkdir -p $INSTALL_DIR
cp -r ./* $INSTALL_DIR/

# Environnement virtuel
echo "[3/7] Création environnement Python..."
cd $INSTALL_DIR
$PYTHON_VERSION -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Configuration
echo "[4/7] Configuration..."
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp .env.example .env
    echo "ATTENTION: Éditer $INSTALL_DIR/.env avec tes valeurs"
fi

# Services systemd
echo "[5/7] Installation services systemd..."
cp config/captive-portal.service /etc/systemd/system/
cp config/captive-sync.service /etc/systemd/system/
systemctl daemon-reload

# Nginx
echo "[6/7] Configuration Nginx..."
cp config/nginx.conf /etc/nginx/sites-available/captive-portal
ln -sf /etc/nginx/sites-available/captive-portal /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# nftables
echo "[7/7] Configuration nftables..."
bash scripts/setup_nftables.sh

echo ""
echo "=== Installation terminée ==="
echo ""
echo "Prochaines étapes:"
echo "1. Éditer $INSTALL_DIR/.env"
echo "2. Configurer le client dans Keycloak"
echo "3. Démarrer les services:"
echo "   sudo systemctl enable --now redis"
echo "   sudo systemctl enable --now captive-portal"
echo "   sudo systemctl enable --now captive-sync"
echo ""
echo "4. Vérifier les logs:"
echo "   journalctl -u captive-portal -f"
echo ""
