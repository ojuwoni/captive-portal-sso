#!/usr/bin/env python3
"""
scripts/sync_sessions.py
Synchronise les sessions du portail avec Keycloak.
- Révoque les accès réseau quand la session Keycloak expire
- Nettoie les sessions orphelines
- Peut tourner en daemon ou en cron

Usage:
  python sync_sessions.py --once        # Exécution unique
  python sync_sessions.py --daemon      # Mode daemon (recommandé)
  python sync_sessions.py --interval 60 # Intervalle en secondes (défaut: 300)
"""

import asyncio
import argparse
import logging
import subprocess
import sys
from datetime import datetime
from typing import Optional

import httpx
import redis.asyncio as redis

# Ajouter le répertoire parent au path
sys.path.insert(0, '/opt/captive-portal')
from config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class KeycloakAdmin:
    """Client pour l'API Admin Keycloak."""
    
    def __init__(self):
        self.base_url = settings.keycloak_url
        self.realm = settings.keycloak_realm
        self.client_id = settings.keycloak_admin_client_id
        self.client_secret = settings.keycloak_admin_client_secret
        self.token: Optional[str] = None
        self.token_expires: Optional[datetime] = None
    
    async def get_token(self) -> str:
        """Obtient un token admin."""
        if self.token and self.token_expires and datetime.utcnow() < self.token_expires:
            return self.token
        
        async with httpx.AsyncClient(verify=True) as client:
            response = await client.post(
                f"{self.base_url}/realms/{self.realm}/protocol/openid-connect/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                }
            )
            response.raise_for_status()
            data = response.json()
            
            self.token = data["access_token"]
            # Expire 60s avant la vraie expiration
            expires_in = data.get("expires_in", 300) - 60
            self.token_expires = datetime.utcnow()
            
            return self.token
    
    async def get_active_sessions(self) -> list:
        """Récupère les sessions actives du realm."""
        token = await self.get_token()
        
        async with httpx.AsyncClient(verify=True) as client:
            # Récupérer les sessions du client captive-portal
            response = await client.get(
                f"{self.base_url}/admin/realms/{self.realm}/clients",
                headers={"Authorization": f"Bearer {token}"},
                params={"clientId": settings.keycloak_client_id}
            )
            response.raise_for_status()
            clients = response.json()
            
            if not clients:
                return []
            
            client_uuid = clients[0]["id"]
            
            # Récupérer les sessions de ce client
            response = await client.get(
                f"{self.base_url}/admin/realms/{self.realm}/clients/{client_uuid}/user-sessions",
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            
            return response.json()
    
    async def get_user_sessions(self, username: str) -> list:
        """Récupère les sessions d'un utilisateur."""
        token = await self.get_token()
        
        async with httpx.AsyncClient(verify=True) as client:
            # Trouver l'utilisateur
            response = await client.get(
                f"{self.base_url}/admin/realms/{self.realm}/users",
                headers={"Authorization": f"Bearer {token}"},
                params={"username": username, "exact": "true"}
            )
            response.raise_for_status()
            users = response.json()
            
            if not users:
                return []
            
            user_id = users[0]["id"]
            
            # Récupérer ses sessions
            response = await client.get(
                f"{self.base_url}/admin/realms/{self.realm}/users/{user_id}/sessions",
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            
            return response.json()


class SessionSynchronizer:
    """Synchronise les sessions portail/Keycloak."""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.keycloak = KeycloakAdmin()
    
    async def connect(self):
        """Connexion Redis."""
        self.redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    
    async def close(self):
        """Fermeture connexion."""
        if self.redis_client:
            await self.redis_client.close()
    
    async def get_portal_sessions(self) -> dict:
        """Récupère toutes les sessions du portail depuis Redis."""
        sessions = {}
        cursor = 0
        
        while True:
            cursor, keys = await self.redis_client.scan(
                cursor=cursor,
                match="session:*",
                count=100
            )
            
            for key in keys:
                mac = key.replace("session:", "")
                data = await self.redis_client.get(key)
                if data:
                    parts = data.split(":")
                    sessions[mac] = {
                        "username": parts[0],
                        "login_time": parts[1] if len(parts) > 1 else None
                    }
            
            if cursor == 0:
                break
        
        return sessions
    
    async def revoke_mac_nftables(self, mac: str) -> bool:
        """Révoque une MAC via nftables."""
        try:
            cmd = [
                "nft", "delete", "element",
                settings.nft_table, settings.nft_chain,
                settings.nft_set, "{", mac, "}"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Erreur revoke nftables {mac}: {e}")
            return False
    
    async def revoke_session(self, mac: str, username: str):
        """Révoque une session complète."""
        logger.info(f"Révocation session: {username} ({mac})")
        
        # Supprimer de Redis
        await self.redis_client.delete(f"session:{mac}")
        
        # Révoquer l'accès réseau
        if settings.auth_method == "nftables":
            await self.revoke_mac_nftables(mac)
    
    async def sync(self):
        """Synchronise les sessions."""
        logger.info("Démarrage synchronisation...")
        
        try:
            # Récupérer les sessions des deux côtés
            portal_sessions = await self.get_portal_sessions()
            keycloak_sessions = await self.keycloak.get_active_sessions()
            
            # Créer un set des usernames avec session Keycloak active
            active_users = set()
            for session in keycloak_sessions:
                active_users.add(session.get("username"))
            
            logger.info(f"Sessions portail: {len(portal_sessions)}, Sessions Keycloak: {len(active_users)}")
            
            # Vérifier chaque session portail
            revoked = 0
            for mac, session_data in portal_sessions.items():
                username = session_data["username"]
                
                # Si l'utilisateur n'a plus de session Keycloak active
                if username not in active_users:
                    await self.revoke_session(mac, username)
                    revoked += 1
            
            logger.info(f"Synchronisation terminée. {revoked} sessions révoquées.")
            
        except Exception as e:
            logger.error(f"Erreur synchronisation: {e}")
            raise
    
    async def cleanup_expired(self):
        """Nettoie les sessions Redis expirées (backup si TTL échoue)."""
        # Redis TTL devrait gérer ça, mais au cas où
        portal_sessions = await self.get_portal_sessions()
        
        for mac, session_data in portal_sessions.items():
            ttl = await self.redis_client.ttl(f"session:{mac}")
            if ttl == -1:  # Pas de TTL défini
                logger.warning(f"Session sans TTL: {mac}, suppression")
                await self.revoke_session(mac, session_data["username"])


async def run_once():
    """Exécution unique."""
    sync = SessionSynchronizer()
    await sync.connect()
    try:
        await sync.sync()
        await sync.cleanup_expired()
    finally:
        await sync.close()


async def run_daemon(interval: int):
    """Mode daemon."""
    sync = SessionSynchronizer()
    await sync.connect()
    
    logger.info(f"Daemon démarré, intervalle: {interval}s")
    
    try:
        while True:
            try:
                await sync.sync()
                await sync.cleanup_expired()
            except Exception as e:
                logger.error(f"Erreur dans le cycle: {e}")
            
            await asyncio.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Arrêt daemon...")
    finally:
        await sync.close()


def main():
    parser = argparse.ArgumentParser(description="Synchronisation sessions portail/Keycloak")
    parser.add_argument("--once", action="store_true", help="Exécution unique")
    parser.add_argument("--daemon", action="store_true", help="Mode daemon")
    parser.add_argument("--interval", type=int, default=300, help="Intervalle en secondes (défaut: 300)")
    
    args = parser.parse_args()
    
    if args.once:
        asyncio.run(run_once())
    elif args.daemon:
        asyncio.run(run_daemon(args.interval))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
