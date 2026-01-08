# Portail Captif SSO avec Keycloak

Portail captif WiFi avec authentification OIDC Keycloak. Une seule authentification pour le WiFi et toutes les applications.

## Pourquoi ce projet ?

Problèmes résolus :
1. **pfSense captive portal ne scale pas** : erreurs "bad gateway" autour de 4000 sessions
2. **Double authentification** : WiFi puis applications = 2 logins
3. **Pas de SSO** : le portail pfSense ne supporte pas OIDC/SAML

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         pfSense                             │
│         (Firewall/NAT/DHCP - portail captif DÉSACTIVÉ)      │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ┌─────────────────────────────▼───────────────────────────────┐
                              │              Serveur Portail Captif (VM/Container)          │
                              │                                                             │
                              │   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
                              │   │   Nginx     │────│   FastAPI   │────│    Redis    │    │
                              │   │  (reverse)  │    │  (portail)  │    │ (sessions)  │    │
                              │   └─────────────┘    └──────┬──────┘    └─────────────┘    │
                              │                             │                               │
                              │                      ┌──────▼──────┐                        │
                              │                      │  nftables   │                        │
                              │                      │ (auth MAC)  │                        │
                              │                      └─────────────┘                        │
                              └─────────────────────────────────────────────────────────────┘
                                                            │
                                                                                   ┌──────▼──────┐
                                                                                                          │  Keycloak   │
                                                                                                                                 │   (OIDC)    │
                                                                                                                                                        └─────────────┘
                                                                                                                                                        ```

## Flux d'authentification

```
1. Client se connecte au WiFi → obtient IP (accès restreint)
2. Client ouvre navigateur → redirigé vers portail
3. Portail redirige vers Keycloak (OIDC)
4. Utilisateur s'authentifie → session SSO créée
5. Callback → portail autorise la MAC (nftables)
6. Client navigue librement
7. Apps reconnaissent la session Keycloak → pas de re-login
```

## Prérequis

- Python 3.10+
- Redis
- Keycloak 20+ avec realm configuré
- nftables (si méthode nftables)
- FreeRADIUS (si méthode CoA)

---

## Installation

### 1. Cloner et configurer

```bash
git clone <repo>
cd captive-portal-sso
cp .env.example .env
nano .env  # Éditer avec tes valeurs
```

### 2. Configurer Keycloak

Créer un client OIDC dans Keycloak :

| Paramètre | Valeur |
|-----------|--------|
| Client ID | captive-portal |
| Client Protocol | openid-connect |
| Access Type | confidential |
| Valid Redirect URIs | http://portal.university.edu/callback |
| Web Origins | http://portal.university.edu |

Récupérer le client secret dans l'onglet Credentials.

Pour la synchronisation des sessions, créer un client service account :

| Paramètre | Valeur |
|-----------|--------|
| Client ID | admin-cli |
| Service Accounts Enabled | ON |
| Roles | realm-admin (ou view-users, view-clients) |

### 3. Configurer nftables

```bash
sudo bash scripts/setup_nftables.sh
```

Adapter les variables dans le script :
- `WIFI_INTERFACE` : interface WiFi (wlan0, eth1...)
- `PORTAL_IP` : IP du serveur portail
- `PORTAL_PORT` : port du portail (8000)

### 4. Lancer avec Docker

```bash
docker-compose up -d
```

### 5. Lancer sans Docker

```bash
# Redis
sudo systemctl start redis

# Portail
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Sync sessions (dans un autre terminal)
python scripts/sync_sessions.py --daemon
```

---

## Personnalisation du thème

### Fichiers statiques

Placer dans le dossier `static/` :

| Fichier | Dimensions | Description |
|---------|------------|-------------|
| `logo.png` | 120x120px | Logo société |
| `favicon.ico` | 32x32px | Icône navigateur |
| `background.jpg` | 1920x1080px | Image de fond (optionnel) |

### Variables d'environnement

```bash
# .env
THEME_COMPANY_NAME=IDADU TECH
THEME_PORTAL_TITLE=Portail WiFi
THEME_PRIMARY_COLOR=#00A651
THEME_PRIMARY_HOVER=#008C44
THEME_LOGO_URL=/static/logo.png
THEME_BACKGROUND_TYPE=gradient
THEME_BACKGROUND_GRADIENT_START=#004D25
THEME_BACKGROUND_GRADIENT_END=#00A651
```

### Exemples de palettes

**IDADU TECH (vert)**
```
PRIMARY: #00A651
HOVER: #008C44
GRADIENT: #004D25 → #00A651
```

**EdTech (orange)**
```
PRIMARY: #F97316
HOVER: #EA580C
GRADIENT: #7C2D12 → #F97316
```

**FinTech (bleu)**
```
PRIMARY: #0EA5E9
HOVER: #0284C7
GRADIENT: #0C4A6E → #0EA5E9
```

**AgriTech (vert nature)**
```
PRIMARY: #22C55E
HOVER: #16A34A
GRADIENT: #14532D → #22C55E
```

### Textes personnalisables

```bash
THEME_LOGIN_BUTTON_TEXT=Se connecter avec mon compte IDADU
THEME_SUCCESS_MESSAGE=Bienvenue sur le réseau IDADU TECH
THEME_FOOTER_TEXT=© 2024 IDADU TECH - Conditions d'utilisation
THEME_TERMS_URL=https://idadu.tech/cgu
```

---

## Migration depuis pfSense

### Prérequis

- Une VM ou serveur dédié pour le portail (Ubuntu 22.04/24.04 recommandé)
- Accès admin à pfSense
- Client Keycloak configuré (voir section Installation)

### Étape 1 : Préparer le serveur portail

```bash
# Sur le nouveau serveur (pas pfSense)
# 1. Cloner le projet
git clone <repo> /opt/captive-portal
cd /opt/captive-portal

# 2. Configurer
cp .env.example .env
nano .env  # Remplir les valeurs Keycloak + thème

# 3. Ajouter le logo dans static/
cp /chemin/vers/logo.png static/logo.png

# 4. Installer
sudo bash install.sh

# 5. Vérifier que ça tourne
curl http://localhost:8000/health
# Doit retourner: {"status":"ok","auth_method":"nftables"}
```

### Étape 2 : Configurer le réseau

**Le serveur portail doit pouvoir :**
1. Recevoir le trafic HTTP des clients WiFi
2. Accéder à Keycloak
3. Contrôler le trafic réseau (nftables)

**Architecture réseau typique :**

```
                    ┌─────────────┐
                        Internet ───────│   pfSense   │
                                            │  (gateway)  │
                                                                └──────┬──────┘
                                                                                           │
                                                                                                         ┌────────────┼────────────┐
                                                                                                                       │            │            │
                                                                                                                               ┌─────▼─────┐ ┌────▼────┐ ┌─────▼─────┐
                                                                                                                                       │  Portail  │ │ Keycloak│ │  Bornes   │
                                                                                                                                               │  Captif   │ │         │ │   WiFi    │
                                                                                                                                                       │ 10.0.0.10 │ │10.0.0.20│ │           │
                                                                                                                                                               └───────────┘ └─────────┘ └───────────┘
                                                                                                                                                               ```

### Étape 3 : Désactiver le portail captif pfSense

**Dans pfSense :**

1. **Aller dans** : Services → Captive Portal

2. **Sélectionner la zone** (ex: "WIFI" ou "LAN")

3. **Décocher** : "Enable Captive Portal"

4. **Cliquer** : Save

5. **Vérifier** : Status → Captive Portal → la zone doit être vide

**Important** : Ne pas toucher à :
- DHCP Server (garder actif)
- DNS Resolver (garder actif)
- Firewall rules (on va les modifier)

### Étape 4 : Configurer les règles firewall pfSense

**Objectif** : Rediriger le trafic HTTP des clients non-auth vers le portail.

**Dans pfSense** : Firewall → NAT → Port Forward

Ajouter une règle :

| Champ | Valeur |
|-------|--------|
| Interface | WIFI (ou ton interface WiFi) |
| Protocol | TCP |
| Source | any |
| Destination | any |
| Destination port | 80 |
| Redirect target IP | 10.0.0.10 (IP du portail) |
| Redirect target port | 8000 |
| Description | Redirect to captive portal |

**Cliquer** : Save → Apply Changes

**Ajouter aussi** : Firewall → Rules → WIFI

| Champ | Valeur |
|-------|--------|
| Action | Pass |
| Interface | WIFI |
| Source | any |
| Destination | 10.0.0.10 |
| Destination port | 8000 |
| Description | Allow captive portal |

### Étape 5 : Configurer nftables sur le serveur portail

```bash
# Sur le serveur portail
sudo nano /opt/captive-portal/scripts/setup_nftables.sh
```

Modifier les variables :

```bash
WIFI_INTERFACE="eth0"      # Interface connectée au réseau WiFi
PORTAL_IP="10.0.0.10"      # IP du serveur portail
PORTAL_PORT="8000"
```

Exécuter :

```bash
sudo bash /opt/captive-portal/scripts/setup_nftables.sh
```

### Étape 6 : Tester

**Test 1 : Accès au portail**
```bash
# Depuis un PC sur le réseau WiFi
curl -I http://10.0.0.10:8000
# Doit retourner HTTP 200
```

**Test 2 : Redirection**
```bash
# Depuis un client WiFi non-auth
# Ouvrir http://example.com dans un navigateur
# Doit rediriger vers le portail
```

**Test 3 : Authentification complète**
1. Connecter un device au WiFi
2. Ouvrir un navigateur → redirection vers portail
3. Cliquer "Se connecter"
4. S'authentifier sur Keycloak
5. Vérifier l'accès Internet

**Test 4 : SSO**
1. Après auth WiFi, ouvrir une app protégée par Keycloak
2. L'utilisateur ne doit PAS se reconnecter

### Étape 7 : Basculer en production

1. **Planifier** une fenêtre de maintenance (30 min)

2. **Sauvegarder** la config pfSense :
   - Diagnostics → Backup & Restore → Download

   3. **Désactiver** l'ancien portail captif (Étape 3)

   4. **Activer** les règles firewall (Étape 4)

   5. **Monitorer** les logs :
      ```bash
         # Sur le serveur portail
            journalctl -u captive-portal -f
               ```

               6. **Tester** avec plusieurs devices

### Rollback (si problème)

```bash
# 1. Sur pfSense : réactiver le captive portal
# Services → Captive Portal → Enable

# 2. Supprimer la règle NAT de redirection
# Firewall → NAT → Port Forward → Supprimer la règle

# 3. Apply Changes
```

### Dépannage migration

| Problème | Cause probable | Solution |
|----------|----------------|----------|
| Pas de redirection | Règle NAT manquante | Vérifier Firewall → NAT |
| Portail inaccessible | Firewall bloque | Ajouter règle Pass vers portail |
| Auth Keycloak échoue | Callback URL incorrecte | Vérifier .env et client Keycloak |
| MAC non détectée | Serveur sur autre segment | Utiliser RADIUS CoA ou proxy ARP |
| Pas de SSO | Cookie Keycloak non transmis | Vérifier domaines et HTTPS |

---

## Configuration

### Variables d'environnement principales

| Variable | Description | Défaut |
|----------|-------------|--------|
| `KEYCLOAK_URL` | URL Keycloak | - |
| `KEYCLOAK_REALM` | Nom du realm | university |
| `KEYCLOAK_CLIENT_ID` | Client ID OIDC | captive-portal |
| `KEYCLOAK_CLIENT_SECRET` | Client secret | - |
| `AUTH_METHOD` | nftables ou radius_coa | nftables |
| `SESSION_TIMEOUT` | Durée session (secondes) | 28800 |
| `CALLBACK_URL` | URL callback OIDC | - |

### Méthodes d'autorisation

#### nftables (recommandé)

**C'est quoi ?** nftables est le firewall Linux moderne (remplace iptables). Il contrôle quel trafic réseau est autorisé ou bloqué.

**Son rôle ici :**
```
1. Client se connecte au WiFi → MAC pas dans la liste → trafic bloqué
2. Client s'authentifie via Keycloak → portail ajoute la MAC à la liste
3. MAC dans la liste → trafic autorisé → Internet accessible
```

**Commandes utiles :**
```bash
# Voir les MAC autorisées
nft list set inet filter allowed_macs

# Ajouter une MAC manuellement
nft add element inet filter allowed_macs { aa:bb:cc:dd:ee:ff }

# Retirer une MAC
nft delete element inet filter allowed_macs { aa:bb:cc:dd:ee:ff }
```

**Prérequis :** Le serveur portail doit être sur le même segment réseau (L2) que les clients WiFi pour pouvoir contrôler leur trafic.

#### radius_coa (infra RADIUS existante)

**C'est quoi ?** RADIUS Change of Authorization permet d'envoyer des commandes aux bornes WiFi pour autoriser/déconnecter des clients.

**Son rôle ici :**
```
1. Client s'authentifie via Keycloak
2. Portail envoie un paquet CoA à la borne WiFi
3. Borne autorise le client
```

**Quand l'utiliser :**
- Tu as des bornes WiFi Cisco, HP, Aruba
- Le serveur portail n'est pas sur le même segment que les clients
- Tu as déjà une infra FreeRADIUS

**Configuration :**
```bash
# .env
AUTH_METHOD=radius_coa
RADIUS_NAS_IP=10.0.0.1      # IP de la borne/contrôleur
RADIUS_SECRET=secret123
RADIUS_COA_PORT=3799
```

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Page d'accueil portail |
| `GET /login` | Initie le flow OIDC |
| `GET /callback` | Callback OIDC |
| `GET /logout` | Déconnexion |
| `GET /status` | Statut connexion (JSON) |
| `GET /health` | Health check |

---

## Synchronisation des sessions

Le script `sync_sessions.py` vérifie périodiquement :
- Session Keycloak expirée → révoque l'accès réseau
- Sessions orphelines → nettoyage

```bash
# Mode daemon (recommandé)
python scripts/sync_sessions.py --daemon --interval 300

# Exécution unique (cron)
python scripts/sync_sessions.py --once
```

---

## Production

### Nginx reverse proxy

```nginx
server {
        listen 80;
            server_name portal.university.edu;
                
                    location / {
                                proxy_pass http://127.0.0.1:8000;
                                        proxy_set_header Host $host;
                                                proxy_set_header X-Real-IP $remote_addr;
                                                        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                                                                proxy_set_header X-Forwarded-Proto $scheme;
                                                                    }
}
```

### Systemd services

```bash
sudo cp config/captive-portal.service /etc/systemd/system/
sudo cp config/captive-sync.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now captive-portal captive-sync
```

---

## Dépannage

### MAC non détectée

- Vérifier que le serveur est sur le même segment L2
- Ou interroger le serveur DHCP pour le mapping IP→MAC

### Session Keycloak non créée

- Vérifier les logs Keycloak
- Vérifier que le callback URL est exact
- Tester avec `curl` le endpoint token

### nftables : permission denied

- Le portail doit tourner en root ou avec `CAP_NET_ADMIN`
- Docker : ajouter `cap_add: NET_ADMIN` et `privileged: true`

### Erreur "bad gateway" (anciennement pfSense)

Ce projet résout ce problème. Redis gère les sessions sans limite.

---

## Structure du projet

```
captive-portal-sso/
├── app/
│   ├── __init__.py
│   └── main.py              # Application FastAPI
├── config/
│   ├── settings.py          # Configuration générale
│   ├── theme.py             # Configuration thème
│   ├── nginx.conf
│   └── *.service            # Services systemd
├── scripts/
│   ├── setup_nftables.sh    # Config nftables
│   ├── sync_sessions.py     # Sync Keycloak
│   └── radius_coa.py        # Client RADIUS CoA
├── static/                  # Logo, favicon, images
├── templates/               # Pages HTML
├── .env.example
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── install.sh
```

---

## Licence

MIT

