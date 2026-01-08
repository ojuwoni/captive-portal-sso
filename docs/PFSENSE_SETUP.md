# Configuration pfSense pour le Portail Captif SSO

Ce guide explique comment configurer pfSense en mode hybride (DNS + Firewall) avec le portail captif SSO.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                           pfSense                                │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  DNS Resolver │  │   Firewall   │  │     pfSense API      │  │
│  │  (redirect)   │  │  (bloquer)   │  │  (autoriser IP)      │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│         │                  │                    ▲               │
└─────────│──────────────────│────────────────────│───────────────┘
          │                  │                    │
          ▼                  ▼                    │
   ┌─────────────┐    ┌─────────────┐     ┌──────┴──────┐
   │ Client WiFi │───▶│   Portail   │────▶│  Keycloak   │
   │ (non-auth)  │    │   Captif    │     │   (OIDC)    │
   └─────────────┘    └─────────────┘     └─────────────┘
```

## Flux d'authentification

1. **Client se connecte au WiFi** → Obtient IP via DHCP
2. **Client ouvre navigateur** → pfSense redirige vers portail (DNS)
3. **Client clique "Se connecter"** → Redirection Keycloak
4. **Client s'authentifie** → Keycloak valide
5. **Portail appelle API pfSense** → Ajoute l'IP à l'alias autorisé
6. **pfSense autorise le trafic** → Client navigue librement

---

## Étape 1 : Installer pfSense API

### Option A : Package pfSense-API (recommandé)

```bash
# Sur pfSense (shell)
pkg add https://github.com/jaredhendrickson13/pfsense-api/releases/latest/download/pfSense-2.7-pkg-API.pkg
```

Ou via l'interface web :
1. **System → Package Manager → Available Packages**
2. Rechercher "API" (si disponible dans les repos)

### Option B : Installation manuelle

1. Télécharger le package depuis [GitHub](https://github.com/jaredhendrickson13/pfsense-api/releases)
2. **Diagnostics → Command Prompt**
3. Uploader et installer le package

---

## Étape 2 : Configurer l'API pfSense

### Créer les clés API

1. **System → API → Settings**
2. Activer l'API
3. **System → API → Keys**
4. Cliquer "Add" pour créer une nouvelle clé :
   - **Description** : `captive-portal`
   - **Key Type** : `API Token`
   - Noter la **Client ID** et le **Client Token**

### Permissions requises

L'API key doit avoir accès à :
- `firewall/alias` (lecture/écriture)
- `firewall/apply` (écriture)
- `system/status` (lecture)

---

## Étape 3 : Configurer le Firewall pfSense

### Créer l'alias pour les clients autorisés

1. **Firewall → Aliases → IP**
2. Cliquer "Add"
3. Configurer :
   - **Name** : `captive_portal_allowed`
   - **Description** : `Clients autorisés par le portail captif SSO`
   - **Type** : `Host(s)`
   - Laisser vide (sera rempli par le portail)
4. Sauvegarder

### Créer les règles Firewall

#### Interface WiFi (LAN_WIFI ou similaire)

**Règle 1 : Autoriser DNS vers pfSense**
```
Action: Pass
Interface: WIFI
Protocol: UDP
Source: WIFI net
Destination: This firewall
Dest Port: 53
Description: Autoriser DNS pour captive portal
```

**Règle 2 : Autoriser accès au portail captif**
```
Action: Pass
Interface: WIFI
Protocol: TCP
Source: WIFI net
Destination: <IP du serveur portail>
Dest Port: 80, 443, 8000
Description: Accès au portail captif
```

**Règle 3 : Autoriser accès à Keycloak**
```
Action: Pass
Interface: WIFI
Protocol: TCP
Source: WIFI net
Destination: <IP de Keycloak>
Dest Port: 443, 8080
Description: Accès à Keycloak pour auth
```

**Règle 4 : Autoriser clients authentifiés**
```
Action: Pass
Interface: WIFI
Protocol: Any
Source: captive_portal_allowed (alias)
Destination: Any
Description: Clients autorisés - accès complet
```

**Règle 5 : Bloquer tout le reste**
```
Action: Block
Interface: WIFI
Protocol: Any
Source: WIFI net
Destination: Any
Description: Bloquer clients non authentifiés
```

⚠️ **Important** : L'ordre des règles est crucial ! Les règles sont évaluées de haut en bas.

---

## Étape 4 : Configurer la redirection DNS

### Méthode 1 : DNS Resolver Override (recommandé)

1. **Services → DNS Resolver**
2. Aller dans **Host Overrides**
3. Pour chaque domaine de détection captive portal :

| Host | Domain | IP | Description |
|------|--------|-----|-------------|
| captive | apple.com | IP_PORTAIL | iOS detection |
| www | apple.com | IP_PORTAIL | iOS detection |
| connectivitycheck | gstatic.com | IP_PORTAIL | Android detection |
| www | msftconnecttest.com | IP_PORTAIL | Windows detection |
| * | example.com | IP_PORTAIL | Fallback |

### Méthode 2 : Captive Portal DNS Forwarding

1. **Services → DNS Resolver → General Settings**
2. Activer "DHCP Registration"
3. Configurer le forwarding des requêtes non-auth vers le portail

---

## Étape 5 : Configurer le Portail

### Variables d'environnement (.env)

```bash
# Méthode d'autorisation
AUTH_METHOD=pfsense

# pfSense API
PFSENSE_HOST=https://192.168.1.1
PFSENSE_API_KEY=<votre-client-id>
PFSENSE_API_SECRET=<votre-client-token>
PFSENSE_VERIFY_SSL=false
PFSENSE_ALIAS_NAME=captive_portal_allowed
```

### Lancer le portail

```bash
docker-compose up -d
```

Vérifier les logs :
```bash
docker logs -f captive-portal
```

Vous devriez voir :
```
INFO: Connexion pfSense OK - Version: 2.7.x
INFO: Alias 'captive_portal_allowed' existe déjà
INFO: Portail captif démarré - Méthode auth: pfsense
```

---

## Étape 6 : Test

### Vérifier la connexion API

```bash
curl -k -X GET "https://192.168.1.1/api/v1/system/status" \
  -H "Authorization: <client-id> <client-token>"
```

### Test du flux complet

1. Connecter un appareil au WiFi
2. Ouvrir un navigateur → devrait rediriger vers le portail
3. Se connecter via Keycloak
4. Vérifier dans pfSense :
   - **Firewall → Aliases → Edit captive_portal_allowed**
   - L'IP du client doit apparaître

---

## Dépannage

### API pfSense ne répond pas

```bash
# Vérifier que l'API est active
curl -k https://192.168.1.1/api/v1/system/status
```

- Vérifier que le package API est installé
- Vérifier les permissions de la clé API
- Vérifier le firewall pfSense (autoriser accès API depuis le portail)

### Client non redirigé vers le portail

- Vérifier les règles DNS dans pfSense
- Vider le cache DNS du client : `ipconfig /flushdns` (Windows) ou redémarrer WiFi
- Vérifier que la règle "Block" est bien en dernier

### Client autorisé mais pas d'accès Internet

- Vérifier que l'IP est bien dans l'alias `captive_portal_allowed`
- Vérifier l'ordre des règles firewall
- Cliquer "Apply Changes" dans pfSense si nécessaire

### Logs utiles

```bash
# Logs du portail
docker logs -f captive-portal

# Logs pfSense (via SSH)
clog /var/log/filter.log | tail -50
```

---

## Sécurité

### Recommandations

1. **HTTPS** : Utiliser HTTPS pour le portail et Keycloak
2. **API pfSense** :
   - Limiter l'accès API à l'IP du serveur portail uniquement
   - Utiliser des clés API avec permissions minimales
3. **Certificats** : Utiliser des certificats valides (Let's Encrypt)
4. **Firewall** : Règle stricte - bloquer par défaut

### Règle firewall pour l'API pfSense

Créer une règle sur l'interface appropriée :
```
Action: Pass
Interface: LAN (ou interface du serveur portail)
Protocol: TCP
Source: <IP du serveur portail>
Destination: This firewall
Dest Port: 443
Description: Accès API pfSense pour portail captif
```

---

## Synchronisation des sessions

Le script `sync_sessions.py` peut aussi nettoyer les IP expirées de l'alias pfSense.

```bash
# Lancer le sync daemon
python scripts/sync_sessions.py --daemon --interval 300
```

Ce script vérifie périodiquement :
- Sessions Keycloak expirées → révoque l'IP dans pfSense
- Sessions Redis expirées → nettoie l'alias pfSense
