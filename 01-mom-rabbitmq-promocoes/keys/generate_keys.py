"""
Gera pares de chaves RSA (privada/pública) para cada microsserviço produtor.
Execute UMA VEZ antes de iniciar o sistema:
    python keys/generate_keys.py
"""

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import os

SERVICES = ["gateway", "promocao", "ranking"]
KEYS_DIR = os.path.dirname(os.path.abspath(__file__))


def generate_key_pair(service_name: str):
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    priv_path = os.path.join(KEYS_DIR, f"{service_name}_private.pem")
    pub_path  = os.path.join(KEYS_DIR, f"{service_name}_public.pem")

    with open(priv_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    with open(pub_path, "wb") as f:
        f.write(private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ))

    print(f"[OK] Chaves geradas para '{service_name}':")
    print(f"     Privada : {priv_path}")
    print(f"     Pública : {pub_path}")


if __name__ == "__main__":
    for svc in SERVICES:
        generate_key_pair(svc)
    print("\n✅ Todas as chaves foram geradas com sucesso!")
