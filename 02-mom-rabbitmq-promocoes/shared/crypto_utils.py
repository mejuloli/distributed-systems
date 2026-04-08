"""
Utilitários de criptografia assimétrica RSA (PKCS1v15 + SHA256).
"""

import base64
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature

# garante encontrar a pasta 'shared' para acessar as chaves
KEYS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "keys")


def _load_private_key(service_name: str):
    path = os.path.join(KEYS_DIR, f"{service_name}_private.pem")
    try:
        with open(path, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)
    except Exception as e:
        print(f"Erro ao carregar chave privada de {service_name}\nVerifique se as chaves foram criadas em {KEYS_DIR}\nE: {e}")
        raise


def _load_public_key(service_name: str):
    path = os.path.join(KEYS_DIR, f"{service_name}_public.pem")
    try:
        with open(path, "rb") as f:
            return serialization.load_pem_public_key(f.read())
    except Exception as e:
        print(f"Erro ao carregar chave pública de {service_name}\nVerifique se as chaves foram criadas em {KEYS_DIR}\nE: {e}")
        raise


def sign_event(payload_bytes: bytes, service_name: str) -> str:
    """
    Assina payload_bytes com a chave privada de service_name.
    Retorna a assinatura codificada em base64 (string).
    """
    private_key = _load_private_key(service_name)
    signature = private_key.sign(
        payload_bytes,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode()


def verify_event(payload_bytes: bytes, signature_b64: str, producer_service: str) -> bool:
    """
    Verifica a assinatura base64 usando a chave pública de producer_service.
    Retorna True se válida, False caso contrário.
    """
    try:
        public_key = _load_public_key(producer_service)
        signature = base64.b64decode(signature_b64)
        public_key.verify(
            signature,
            payload_bytes,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except (InvalidSignature, Exception):
        return False
