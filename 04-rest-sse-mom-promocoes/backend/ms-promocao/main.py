"""
MS Promoção
───────────
gerencia e valida promoções recebidas.

consome : promocao.recebida  (assinada com chave da loja)
publica : promocao.publicada (assinada com chave do MS Promoção)

fluxo:
  1. recebe evento promocao.recebida
  2. valida assinatura digital da loja demo
  3. assina e publica promocao.publicada
"""
import sys
import os
import json
# garante que o python encontre a pasta 'shared'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.rabbitmq_utils import (
    get_connection, declare_exchange, publish_event,
    payload_to_bytes, EXCHANGE_NAME,
)
from shared.crypto_utils import sign_event, verify_event

SERVICE_NAME = "promocao"
QUEUE_NAME = "Fila_Promocao"


def _on_promocao_recebida(ch, method, props, body):
    routing_key = method.routing_key
    envelope= json.loads(body)
    payload = envelope["payload"]
    signature = envelope["signature"]

    print(f"\n[MS Promoção] Evento '{routing_key}' recebido: '{payload.get('titulo', '?')}'")

    # 1. valida assinatura da loja
    if not verify_event(payload_to_bytes(payload), signature, "loja_demo"):
        print("[MS Promoção] Assinatura INVÁLIDA - evento descartado.")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    print("[MS Promoção] ✔ Assinatura válida.")

    required = ["promocao_id", "loja_id", "loja_email", "titulo", "categoria", "descricao", "preco"]
    if any(not payload.get(field) for field in required):
        print("[MS Promoção] Dados obrigatórios ausentes - evento descartado.")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    try:
        payload["preco"] = float(payload["preco"])
    except (TypeError, ValueError):
        print("[MS Promoção] Preço inválido - evento descartado.")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    if payload["preco"] <= 0:
        print("[MS Promoção] Preço deve ser maior que zero - evento descartado.")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    payload["categoria"] = payload["categoria"].strip().lower()
    payload["hot_deal"] = False

    print(f"[MS Promoção] Promoção registrada (id={payload['promocao_id']}).")

    # 2. assina e publica promocao.publicada
    sig_out = sign_event(payload_to_bytes(payload), SERVICE_NAME)
    publish_event("promocao.publicada", payload, sig_out)
    print(f"[MS Promoção] ✔ Evento 'promocao.publicada' publicado para '{payload['titulo']}'.")

    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    conn = get_connection()
    try:
        ch = conn.channel()
        declare_exchange(ch)

        ch.queue_declare(queue=QUEUE_NAME, durable=True)
        ch.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key="promocao.recebida")
        ch.basic_qos(prefetch_count=1)
        ch.basic_consume(queue=QUEUE_NAME, on_message_callback=_on_promocao_recebida)

        print("[MS Promoção] Aguardando eventos 'promocao.recebida'... (Ctrl+C para sair)")
        ch.start_consuming()
    except KeyboardInterrupt:
        print("\n[MS Promoção] Interrompido. Encerrando conexão...")
        conn.close()


if __name__ == "__main__":
    main()
