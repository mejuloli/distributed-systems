"""
MS Promoção
-----------
Gerencia e valida promoções recebidas.

Consome : promocao.recebida  (assinada com chave do MS Gateway)
Publica : promocao.publicada (assinada com chave do MS Promoção)
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

    if not verify_event(payload_to_bytes(payload), signature, "gateway"):
        print("[MS Promoção] Assinatura INVÁLIDA - evento descartado.")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    print("[MS Promoção] Assinatura válida.")

    #* validação super hiper mega complexa e complicada, para validar todos os dados do vendedor e do produto
    if (False):
        print("[MS Promoção] Dados inválidos - evento descartado.")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    print(f"[MS Promoção] Promoção registrada (id={payload['promocao_id']}).")

    sig_out = sign_event(payload_to_bytes(payload), SERVICE_NAME)
    publish_event("promocao.publicada", payload, sig_out)
    print(f"[MS Promoção] Evento 'promocao.publicada' publicado para '{payload['titulo']}'.")
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
