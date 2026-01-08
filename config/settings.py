# config/settings.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Application
    app_name: str = "Captive Portal SSO"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False
    dev_mode: bool = False  # En mode dev, génère une MAC fictive pour les tests
    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    
    # Keycloak OIDC
    keycloak_url: str = "https://keycloak.example.com"
    keycloak_realm: str = "university"
    keycloak_client_id: str = "captive-portal"
    keycloak_client_secret: str = "your-client-secret"
    
    # URLs dérivées (calculées)
    @property
    def keycloak_issuer(self) -> str:
        return f"{self.keycloak_url}/realms/{self.keycloak_realm}"
    
    @property
    def keycloak_metadata_url(self) -> str:
        return f"{self.keycloak_issuer}/.well-known/openid-configuration"
    
    @property
    def keycloak_admin_url(self) -> str:
        return f"{self.keycloak_url}/admin/realms/{self.keycloak_realm}"
    
    # Redis (pour sessions et MAC autorisées)
    redis_url: str = "redis://localhost:6379/0"
    
    # Session timeout (secondes)
    session_timeout: int = 28800  # 8 heures par défaut
    
    # Méthode d'autorisation réseau: "nftables" ou "radius_coa"
    auth_method: str = "nftables"
    
    # nftables config
    nft_table: str = "inet"
    nft_chain: str = "filter"
    nft_set: str = "allowed_macs"
    
    # RADIUS CoA config
    radius_nas_ip: str = "10.0.0.1"
    radius_secret: str = "radius-secret"
    radius_coa_port: int = 3799
    
    # Interface réseau pour ARP lookup
    network_interface: str = "eth0"
    
    # Callback URL (doit être accessible depuis le client)
    callback_url: str = "http://portal.example.com/callback"
    
    # URL de redirection après login réussi
    success_redirect_url: str = "https://www.google.com"
    
    # Keycloak Admin (pour sync sessions)
    keycloak_admin_client_id: str = "admin-cli"
    keycloak_admin_client_secret: str = "admin-secret"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
