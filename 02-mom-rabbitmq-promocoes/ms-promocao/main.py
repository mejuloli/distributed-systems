"""
MS Promoção
───────────
Gerencia e valida promoções recebidas.

Consome : promocao.recebida  (do MS Gateway)
Publica : promocao.publicada (assinada com chave do MS Promoção)

Fluxo:
  1. Recebe evento promocao.recebida
  2. Valida assinatura digital do Gateway
  3. Registra a promoção localmente
  4. Assina e publica promocao.publicada
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.rabbitmq_utils import (
    get_connection, declare_exchange, publish_event,
    payload_to_bytes, EXCHANGE_NAME,
)
from shared.crypto_utils import sign_event, verify_event

SERVICE_NAME   = "promocao"
QUEUE_NAME     = "Fila_Promocao"

# registro local de promoções validadas
promocoes: dict[str, dict] = {}


def _on_promocao_recebida(ch, method, props, body):
    envelope  = json.loads(body)
    payload   = envelope["payload"]
    signature = envelope["signature"]

    print(f"\n[MS Promoção] Evento recebido: '{payload.get('titulo', '?')}'")

    # 1. valida assinatura do Gateway
    if not verify_event(payload_to_bytes(payload), signature, "gateway"):
        print("[MS Promoção] ⚠ Assinatura INVÁLIDA — evento descartado.")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    print("[MS Promoção] ✔ Assinatura válida.")

    # 2. registra promoção
    pid = payload["id"]
    promocoes[pid] = payload
    print(f"[MS Promoção] Promoção registrada (id={pid}).")

    # 3. assina e publica promocao.publicada
    sig_out = sign_event(payload_to_bytes(payload), SERVICE_NAME)
    publish_event("promocao.publicada", payload, sig_out)
    print(f"[MS Promoção] ✔ Evento 'promocao.publicada' publicado para '{payload['titulo']}'.")

    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    conn = get_connection()
    ch   = conn.channel()
    declare_exchange(ch)

    ch.queue_declare(queue=QUEUE_NAME, durable=True)
    ch.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key="promocao.recebida")
    ch.basic_qos(prefetch_count=1)
    ch.basic_consume(queue=QUEUE_NAME, on_message_callback=_on_promocao_recebida)

    print("[MS Promoção] Aguardando eventos 'promocao.recebida'... (Ctrl+C para sair)")
    ch.start_consuming()


if __name__ == "__main__":
    main()
