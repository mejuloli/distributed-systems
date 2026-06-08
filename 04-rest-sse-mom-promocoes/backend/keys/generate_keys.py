"""
Gera pares de chaves RSA para todos os produtores do projeto 04.

O Docker executa este script no serviço keygen antes dos microsserviços.
As chaves são idempotentes: se o par já existir no volume, ele é preservado.
"""

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import os

SERVICES = ["gateway", "promocao", "ranking", "notificacao", "loja_demo"]
KEYS_DIR = os.getenv("KEYS_DIR", os.path.dirname(os.path.abspath(__file__)))


def generate_key_pair(service_name: str):
    os.makedirs(KEYS_DIR, exist_ok=True)

    priv_path = os.path.join(KEYS_DIR, f"{service_name}_private.pem")
    pub_path= os.path.join(KEYS_DIR, f"{service_name}_public.pem")

    if os.path.exists(priv_path) and os.path.exists(pub_path):
        print(f" Chaves existentes preservadas para '{service_name}'.")
        return

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    with open(priv_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    with open(pub_path, "wb") as f:
        f.write(private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ))

    print(f" Chaves geradas para '{service_name}':")
    print(f"     Privada : {priv_path}")
    print(f"     Pública : {pub_path}")


if __name__ == "__main__":
    for svc in SERVICES:
        generate_key_pair(svc)
    print("\n Todas as chaves foram geradas com sucesso!")
