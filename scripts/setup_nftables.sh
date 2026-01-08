#!/bin/bash
# scripts/setup_nftables.sh
# Configure nftables pour le portail captif
# Exécuter avec sudo

set -e

echo "Configuration nftables pour portail captif..."

# Variables
TABLE="inet filter"
WIFI_INTERFACE="wlan0"  # Adapter selon ton infra
PORTAL_IP="192.168.1.10"  # IP du serveur portail
PORTAL_PORT="8000"

# Créer la table et les chaînes si elles n'existent pas
nft add table inet filter 2>/dev/null || true

# Créer le set pour les MACs autorisées
nft add set inet filter allowed_macs { type ether_addr \; } 2>/dev/null || true

# Chaîne input
nft add chain inet filter input { type filter hook input priority 0 \; policy accept \; } 2>/dev/null || true

# Chaîne forward pour le trafic WiFi
nft add chain inet filter forward { type filter hook forward priority 0 \; policy drop \; } 2>/dev/null || true

# Règles de base
nft flush chain inet filter forward

# 1. Autoriser le trafic des MACs dans le set
nft add rule inet filter forward iifname "$WIFI_INTERFACE" ether saddr @allowed_macs accept

# 2. Autoriser le trafic vers le portail captif (pour auth)
nft add rule inet filter forward iifname "$WIFI_INTERFACE" ip daddr $PORTAL_IP tcp dport $PORTAL_PORT accept

# 3. Autoriser DNS (pour résolution initiale)
nft add rule inet filter forward iifname "$WIFI_INTERFACE" udp dport 53 accept
nft add rule inet filter forward iifname "$WIFI_INTERFACE" tcp dport 53 accept

# 4. Autoriser DHCP
nft add rule inet filter forward iifname "$WIFI_INTERFACE" udp dport 67 accept
nft add rule inet filter forward iifname "$WIFI_INTERFACE" udp sport 68 accept

# 5. Rediriger HTTP vers le portail captif (pour les non-authentifiés)
nft add chain inet nat prerouting { type nat hook prerouting priority -100 \; } 2>/dev/null || true
nft add rule inet nat prerouting iifname "$WIFI_INTERFACE" ether saddr != @allowed_macs tcp dport 80 redirect to :$PORTAL_PORT

# Afficher la config
echo ""
echo "Configuration appliquée:"
nft list ruleset

echo ""
echo "Pour ajouter une MAC manuellement:"
echo "  nft add element inet filter allowed_macs { aa:bb:cc:dd:ee:ff }"
echo ""
echo "Pour retirer une MAC:"
echo "  nft delete element inet filter allowed_macs { aa:bb:cc:dd:ee:ff }"
echo ""
echo "Pour lister les MACs autorisées:"
echo "  nft list set inet filter allowed_macs"
