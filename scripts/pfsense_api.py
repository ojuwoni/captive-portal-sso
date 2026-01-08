# scripts/pfsense_api.py
"""
Module d'intégration avec l'API pfSense pour le portail captif.
Gère l'autorisation/révocation des MAC via les règles firewall pfSense.

Compatibilité:
- pfSense CE 2.7+ avec package pfSense-API
- pfSense Plus avec API REST native

Documentation: https://github.com/jaredhendrickson13/pfsense-api
"""

import httpx
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class PfSenseAPI:
    """Client pour l'API pfSense."""

    def __init__(
        self,
        host: str,
        api_key: str,
        api_secret: str,
        verify_ssl: bool = False,
        timeout: int = 10
    ):
        """
        Initialise le client pfSense API.

        Args:
            host: URL de pfSense (ex: https://192.168.1.1)
            api_key: Clé API pfSense
            api_secret: Secret API pfSense
            verify_ssl: Vérifier le certificat SSL (False pour self-signed)
            timeout: Timeout des requêtes en secondes
        """
        self.host = host.rstrip('/')
        self.api_key = api_key
        self.api_secret = api_secret
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.base_url = f"{self.host}/api/v1"

    def _get_headers(self) -> dict:
        """Retourne les headers d'authentification."""
        return {
            "Authorization": f"{self.api_key} {self.api_secret}",
            "Content-Type": "application/json"
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None
    ) -> dict:
        """Effectue une requête à l'API pfSense."""
        url = f"{self.base_url}/{endpoint}"

        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=self.timeout) as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self._get_headers(),
                    json=data
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"pfSense API error: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"pfSense API request failed: {e}")
                raise

    async def get_firewall_aliases(self) -> list:
        """Liste tous les alias firewall."""
        result = await self._request("GET", "firewall/alias")
        return result.get("data", [])

    async def create_alias_if_not_exists(self, alias_name: str = "captive_portal_allowed") -> bool:
        """
        Crée l'alias pour les MAC autorisées s'il n'existe pas.

        L'alias est de type 'host' et contiendra les adresses IP des clients autorisés.
        Note: pfSense ne supporte pas les alias MAC directement dans les règles,
        on utilise donc les IP avec des baux DHCP statiques ou on track par IP.
        """
        try:
            aliases = await self.get_firewall_aliases()

            # Vérifier si l'alias existe déjà
            for alias in aliases:
                if alias.get("name") == alias_name:
                    logger.info(f"Alias '{alias_name}' existe déjà")
                    return True

            # Créer l'alias
            data = {
                "name": alias_name,
                "type": "host",
                "descr": "Clients autorisés par le portail captif SSO",
                "address": [],
                "detail": []
            }

            await self._request("POST", "firewall/alias", data)
            logger.info(f"Alias '{alias_name}' créé avec succès")

            # Appliquer les changements
            await self.apply_changes()
            return True

        except Exception as e:
            logger.error(f"Erreur création alias: {e}")
            return False

    async def add_ip_to_alias(
        self,
        ip: str,
        username: str,
        alias_name: str = "captive_portal_allowed"
    ) -> bool:
        """
        Ajoute une IP à l'alias des clients autorisés.

        Args:
            ip: Adresse IP du client
            username: Nom d'utilisateur (pour la description)
            alias_name: Nom de l'alias pfSense
        """
        try:
            # Récupérer l'alias actuel
            aliases = await self.get_firewall_aliases()
            target_alias = None

            for alias in aliases:
                if alias.get("name") == alias_name:
                    target_alias = alias
                    break

            if not target_alias:
                logger.error(f"Alias '{alias_name}' non trouvé")
                return False

            # Récupérer les adresses existantes
            current_addresses = target_alias.get("address", "")
            current_details = target_alias.get("detail", "")

            # Convertir en listes
            if isinstance(current_addresses, str):
                addresses = [a.strip() for a in current_addresses.split(" ") if a.strip()]
            else:
                addresses = list(current_addresses) if current_addresses else []

            if isinstance(current_details, str):
                details = [d.strip() for d in current_details.split("||") if d.strip()]
            else:
                details = list(current_details) if current_details else []

            # Vérifier si l'IP existe déjà
            if ip in addresses:
                logger.info(f"IP {ip} déjà dans l'alias")
                return True

            # Ajouter la nouvelle IP
            addresses.append(ip)
            details.append(f"{username}@{datetime.now().strftime('%Y-%m-%d %H:%M')}")

            # Mettre à jour l'alias
            data = {
                "name": alias_name,
                "type": "host",
                "address": " ".join(addresses),
                "detail": "||".join(details)
            }

            await self._request("PUT", f"firewall/alias", data)
            logger.info(f"IP {ip} ajoutée à l'alias '{alias_name}' pour {username}")

            # Appliquer les changements
            await self.apply_changes()
            return True

        except Exception as e:
            logger.error(f"Erreur ajout IP à l'alias: {e}")
            return False

    async def remove_ip_from_alias(
        self,
        ip: str,
        alias_name: str = "captive_portal_allowed"
    ) -> bool:
        """
        Retire une IP de l'alias des clients autorisés.

        Args:
            ip: Adresse IP du client
            alias_name: Nom de l'alias pfSense
        """
        try:
            # Récupérer l'alias actuel
            aliases = await self.get_firewall_aliases()
            target_alias = None

            for alias in aliases:
                if alias.get("name") == alias_name:
                    target_alias = alias
                    break

            if not target_alias:
                logger.error(f"Alias '{alias_name}' non trouvé")
                return False

            # Récupérer les adresses existantes
            current_addresses = target_alias.get("address", "")
            current_details = target_alias.get("detail", "")

            # Convertir en listes
            if isinstance(current_addresses, str):
                addresses = [a.strip() for a in current_addresses.split(" ") if a.strip()]
            else:
                addresses = list(current_addresses) if current_addresses else []

            if isinstance(current_details, str):
                details = [d.strip() for d in current_details.split("||") if d.strip()]
            else:
                details = list(current_details) if current_details else []

            # Retirer l'IP
            if ip not in addresses:
                logger.info(f"IP {ip} non trouvée dans l'alias")
                return True

            idx = addresses.index(ip)
            addresses.pop(idx)
            if idx < len(details):
                details.pop(idx)

            # Mettre à jour l'alias
            data = {
                "name": alias_name,
                "type": "host",
                "address": " ".join(addresses) if addresses else "",
                "detail": "||".join(details) if details else ""
            }

            await self._request("PUT", f"firewall/alias", data)
            logger.info(f"IP {ip} retirée de l'alias '{alias_name}'")

            # Appliquer les changements
            await self.apply_changes()
            return True

        except Exception as e:
            logger.error(f"Erreur retrait IP de l'alias: {e}")
            return False

    async def apply_changes(self) -> bool:
        """Applique les changements de configuration pfSense."""
        try:
            await self._request("POST", "firewall/apply")
            logger.info("Changements pfSense appliqués")
            return True
        except Exception as e:
            logger.error(f"Erreur application changements: {e}")
            return False

    async def test_connection(self) -> bool:
        """Teste la connexion à l'API pfSense."""
        try:
            result = await self._request("GET", "system/status")
            logger.info(f"Connexion pfSense OK - Version: {result.get('data', {}).get('system_version', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"Test connexion pfSense échoué: {e}")
            return False


# Instance globale (initialisée au démarrage si configuré)
pfsense_client: Optional[PfSenseAPI] = None


def init_pfsense_client(
    host: str,
    api_key: str,
    api_secret: str,
    verify_ssl: bool = False
) -> PfSenseAPI:
    """Initialise le client pfSense global."""
    global pfsense_client
    pfsense_client = PfSenseAPI(
        host=host,
        api_key=api_key,
        api_secret=api_secret,
        verify_ssl=verify_ssl
    )
    return pfsense_client


def get_pfsense_client() -> Optional[PfSenseAPI]:
    """Retourne le client pfSense global."""
    return pfsense_client
