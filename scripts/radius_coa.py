#!/usr/bin/env python3
"""
scripts/radius_coa.py
Utilitaires pour RADIUS Change of Authorization (CoA)
Compatible avec FreeRADIUS, Cisco, HP, Aruba

Usage:
  python radius_coa.py authorize --mac AA:BB:CC:DD:EE:FF --user john
  python radius_coa.py disconnect --mac AA:BB:CC:DD:EE:FF
  python radius_coa.py test --nas 10.0.0.1
"""

import argparse
import socket
import struct
import hashlib
import secrets
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# RADIUS packet codes
COA_REQUEST = 43
COA_ACK = 44
COA_NAK = 45
DISCONNECT_REQUEST = 40
DISCONNECT_ACK = 41
DISCONNECT_NAK = 42

# RADIUS attribute types
USER_NAME = 1
NAS_IP_ADDRESS = 4
CALLING_STATION_ID = 31
ACCT_SESSION_ID = 44
MESSAGE_AUTHENTICATOR = 80


class RadiusPacket:
    """Constructeur de paquets RADIUS."""
    
    def __init__(self, code: int, identifier: int = None, secret: bytes = b""):
        self.code = code
        self.identifier = identifier or secrets.randbelow(256)
        self.secret = secret
        self.attributes = []
        self.authenticator = secrets.token_bytes(16)
    
    def add_attribute(self, attr_type: int, value: bytes):
        """Ajoute un attribut au paquet."""
        self.attributes.append((attr_type, value))
    
    def add_string(self, attr_type: int, value: str):
        """Ajoute un attribut string."""
        self.add_attribute(attr_type, value.encode('utf-8'))
    
    def add_ipaddr(self, attr_type: int, ip: str):
        """Ajoute un attribut IP."""
        octets = [int(x) for x in ip.split('.')]
        self.add_attribute(attr_type, bytes(octets))
    
    def build(self) -> bytes:
        """Construit le paquet binaire."""
        # Construire les attributs
        attrs_data = b""
        for attr_type, value in self.attributes:
            length = len(value) + 2
            attrs_data += struct.pack("!BB", attr_type, length) + value
        
        # Placeholder pour Message-Authenticator (si nécessaire)
        msg_auth_placeholder = struct.pack("!BB", MESSAGE_AUTHENTICATOR, 18) + (b"\x00" * 16)
        attrs_data += msg_auth_placeholder
        
        # Header
        total_length = 20 + len(attrs_data)
        header = struct.pack("!BBH", self.code, self.identifier, total_length)
        
        # Paquet sans authenticator final
        packet = header + self.authenticator + attrs_data
        
        # Calculer Message-Authenticator (HMAC-MD5)
        msg_auth = hashlib.md5(packet + self.secret).digest()
        
        # Remplacer le placeholder
        msg_auth_pos = len(header) + 16 + len(attrs_data) - 18
        packet = packet[:msg_auth_pos + 2] + msg_auth + packet[msg_auth_pos + 18:]
        
        # Recalculer l'authenticator du paquet
        packet_for_auth = packet[:4] + (b"\x00" * 16) + packet[20:]
        final_auth = hashlib.md5(packet_for_auth + self.secret).digest()
        packet = packet[:4] + final_auth + packet[20:]
        
        return packet


class RadiusCoAClient:
    """Client RADIUS CoA."""
    
    def __init__(self, nas_ip: str, secret: str, port: int = 3799, timeout: int = 5):
        self.nas_ip = nas_ip
        self.secret = secret.encode('utf-8')
        self.port = port
        self.timeout = timeout
    
    def send_packet(self, packet: RadiusPacket) -> Optional[int]:
        """Envoie un paquet et retourne le code de réponse."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.timeout)
            
            data = packet.build()
            sock.sendto(data, (self.nas_ip, self.port))
            
            response, _ = sock.recvfrom(4096)
            
            if len(response) >= 1:
                return response[0]  # Code de réponse
            
            return None
            
        except socket.timeout:
            logger.error(f"Timeout CoA vers {self.nas_ip}:{self.port}")
            return None
        except Exception as e:
            logger.error(f"Erreur CoA: {e}")
            return None
        finally:
            sock.close()
    
    def authorize(self, mac: str, username: str, session_id: str = None) -> bool:
        """Envoie un CoA pour autoriser un utilisateur."""
        packet = RadiusPacket(COA_REQUEST, secret=self.secret)
        
        # Attributs
        packet.add_string(USER_NAME, username)
        packet.add_string(CALLING_STATION_ID, mac.replace(":", "-"))
        
        if session_id:
            packet.add_string(ACCT_SESSION_ID, session_id)
        
        # Attributs vendor-specific selon l'équipement
        # Cisco: Cisco-AVPair = "subscriber:command=account-logon"
        # HP/Aruba: voir documentation spécifique
        
        response = self.send_packet(packet)
        
        if response == COA_ACK:
            logger.info(f"CoA ACK: {username} ({mac}) autorisé")
            return True
        elif response == COA_NAK:
            logger.warning(f"CoA NAK: {username} ({mac}) refusé")
            return False
        else:
            logger.error(f"CoA réponse inattendue: {response}")
            return False
    
    def disconnect(self, mac: str, username: str = None, session_id: str = None) -> bool:
        """Envoie un Disconnect-Request pour déconnecter un utilisateur."""
        packet = RadiusPacket(DISCONNECT_REQUEST, secret=self.secret)
        
        packet.add_string(CALLING_STATION_ID, mac.replace(":", "-"))
        
        if username:
            packet.add_string(USER_NAME, username)
        
        if session_id:
            packet.add_string(ACCT_SESSION_ID, session_id)
        
        response = self.send_packet(packet)
        
        if response == DISCONNECT_ACK:
            logger.info(f"Disconnect ACK: {mac} déconnecté")
            return True
        elif response == DISCONNECT_NAK:
            logger.warning(f"Disconnect NAK: {mac}")
            return False
        else:
            logger.error(f"Disconnect réponse inattendue: {response}")
            return False
    
    def test_connection(self) -> bool:
        """Test de connectivité CoA."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2)
            sock.connect((self.nas_ip, self.port))
            sock.close()
            logger.info(f"Connexion CoA OK vers {self.nas_ip}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Connexion CoA échouée: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description="RADIUS CoA Utility")
    parser.add_argument("action", choices=["authorize", "disconnect", "test"])
    parser.add_argument("--nas", required=True, help="NAS IP address")
    parser.add_argument("--secret", default="testing123", help="RADIUS secret")
    parser.add_argument("--port", type=int, default=3799, help="CoA port")
    parser.add_argument("--mac", help="Client MAC address")
    parser.add_argument("--user", help="Username")
    parser.add_argument("--session", help="Session ID")
    
    args = parser.parse_args()
    
    client = RadiusCoAClient(args.nas, args.secret, args.port)
    
    if args.action == "test":
        success = client.test_connection()
        exit(0 if success else 1)
    
    elif args.action == "authorize":
        if not args.mac or not args.user:
            parser.error("authorize nécessite --mac et --user")
        success = client.authorize(args.mac, args.user, args.session)
        exit(0 if success else 1)
    
    elif args.action == "disconnect":
        if not args.mac:
            parser.error("disconnect nécessite --mac")
        success = client.disconnect(args.mac, args.user, args.session)
        exit(0 if success else 1)


if __name__ == "__main__":
    main()
