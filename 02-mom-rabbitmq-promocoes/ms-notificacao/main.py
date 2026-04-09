"""
MS Notificação
──────────────
Distribui notificações de promoções para os clientes interessados.

Consome : promocao.publicada  (assinada com chave do MS Promoção)
          promocao.destaque   (assinada com chave do MS Ranking)
Publica : promocao.<categoria>  - notificação de nova promoção na categoria
                                  (também publicado com "hot deal" quando a
                                   promoção for destacada pelo MS Ranking)

IMPORTANTE: O MS Ranking já publica promocao.destaque diretamente no broker.
Os clientes interessados em destaques consomem essa chave diretamente.
O papel deste MS em relação a destaques é APENAS publicar uma notificação
adicional em promocao.<categoria> contendo "hot deal" no payload, para que
clientes inscritos naquela categoria também sejam avisados do destaque.

Nota: o MS Notificação NÃO assina os eventos que publica (redistribuidor).
"""
import sys
import os
import json
# garante que o python encontre a pasta 'shared'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.rabbitmq_utils import (
    get_connection, declare_exchange, payload_to_bytes, 
    publish_event, EXCHANGE_NAME
)
from shared.crypto_utils import sign_event, verify_event

SERVICE_NAME = "notificacao"
QUEUE_NAME = "Fila_Notificacao"


def _on_message(ch, method, props, body):
    routing_key = method.routing_key
    envelope = json.loads(body)
    payload = envelope["payload"]
    signature = envelope["signature"]

    print(f"\n[MS Notificação] Evento '{routing_key}' recebido: '{payload.get('titulo', '?')}'")

    # determina o produtor esperado para validar assinatura
    if routing_key == "promocao.publicada":
        producer = "promocao"
    else:  # promocao.destaque
        producer = "ranking"

    if not verify_event(payload_to_bytes(payload), signature, producer):
        print(f"[MS Notificação] Assinatura INVÁLIDA ({producer}) - descartado.")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    print(f"[MS Notificação] ✔ Assinatura válida ({producer}).")

    # ── promoção nova publicada ────────────────────────────────
    pid = payload["promocao_id"]
    categoria = payload["categoria"]
    if routing_key == "promocao.publicada":
        notif = {
            "promocao_id":  pid,
            "titulo":       payload["titulo"],
            "categoria":    categoria,
            "descricao":    payload["descricao"],
            "preco":        payload["preco"],
        }
        publish_event(f"promocao.{categoria}", notif, ch)
        print(f"[MS Notificação] ✔ Notificação enviada para categoria '{categoria}'.")

    else:
        # o MS Ranking já publicou promocao.destaque direto no broker.
        # notifica na categoria da promoção (promocao.<categoria>) 
        # para clientes que seguem a categoria mas talvez não estejam
        # inscritos em promocao.destaque.
        notif = {
            "promocao_id":  pid,
            "titulo":       payload["titulo"],
            "categoria":    categoria,
            "descricao":    payload["descricao"],
            "preco":        payload["preco"],
            "score":        payload["score"],
            "hot_deal":     True,
        }
        print(f"[MS Notificação] Hot deal notificado em 'promocao.{categoria}' (id={pid}).")
    sig_out = sign_event(payload_to_bytes(payload), SERVICE_NAME)
    publish_event(f"promocao.{categoria}", notif, sig_out)

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
