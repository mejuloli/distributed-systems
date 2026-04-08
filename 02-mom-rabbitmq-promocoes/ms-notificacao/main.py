"""
MS Notificação
--------------
Distribui notificações de promoções para os clientes interessados e republica promoções Hot Deals na categoria da promoção.

Consome : promocao.publicada  (assinada com chave do MS Promoção)
          promocao.destaque   (assinada com chave do MS Ranking)
Publica : promocao.<categoria>(não é assinada)
"""
import sys
import os
import json
# garante que o python encontre a pasta 'shared'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.rabbitmq_utils import (
    get_connection, declare_exchange, payload_to_bytes, 
    publish_raw, EXCHANGE_NAME
)
from shared.crypto_utils import verify_event

QUEUE_NAME = "Fila_Notificacao"


def _on_message(ch, method, props, body):
    routing_key = method.routing_key
    envelope = json.loads(body)
    payload = envelope["payload"]
    signature = envelope["signature"]

    print(f"\n[MS Notificação] Evento '{routing_key}' recebido: '{payload.get('titulo', '?')}'")

    if routing_key == "promocao.publicada":
        producer = "promocao"
    else:  # promocao.destaque
        producer = "ranking"

    if not verify_event(payload_to_bytes(payload), signature, producer):
        print(f"[MS Notificação] Assinatura INVÁLIDA ({producer}) - descartado.")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    print(f"[MS Notificação] Assinatura válida ({producer}).")

    if routing_key == "promocao.publicada":
        pid = payload["promocao_id"]
        categoria = payload["categoria"]

        notif = {
            "promocao_id":  pid,
            "titulo":       payload["titulo"],
            "categoria":    payload["categoria"],
            "descricao":    payload["descricao"],
            "preco":        payload["preco"],
        }
        publish_raw(f"promocao.{categoria}", notif, ch)
        print(f"[MS Notificação] Notificação enviada para categoria '{categoria}'.")

    elif routing_key == "promocao.destaque":
        pid = payload["promocao_id"]

        categoria = payload.get("categoria", "desconhecida")
        notif_cat = {
            "promocao_id":  pid,
            "titulo":       payload.get("titulo", "?"),
            "categoria":    categoria,
            "descricao":    payload.get("descricao", ""),
            "preco":        payload.get("preco", 0),
            "score":        payload["score"],
            "hot_deal":     True,
        }
        publish_raw(f"promocao.{categoria}", notif_cat, ch)
        print(f"[MS Notificação] Hot deal notificado em 'promocao.{categoria}' (id={pid}).")

    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    conn = get_connection()
    try:
        ch = conn.channel()
        declare_exchange(ch)

        ch.queue_declare(queue=QUEUE_NAME, durable=True)
        ch.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key="promocao.publicada")
        ch.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key="promocao.destaque")
        ch.basic_qos(prefetch_count=1)
        ch.basic_consume(queue=QUEUE_NAME, on_message_callback=_on_message)

        print("[MS Notificação] Aguardando eventos... (Ctrl+C para sair)")
        ch.start_consuming()
    except KeyboardInterrupt:
        print("\n[MS Notificação] Interrompido pelo usuário. Encerrando...")


if __name__ == "__main__":
    main()
