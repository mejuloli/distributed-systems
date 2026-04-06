"""
MS Notificação
──────────────
Distribui notificações de promoções para os clientes interessados.

Consome : promocao.publicada  (do MS Promoção)
          promocao.destaque   (do MS Ranking)
Publica : promocao.<categoria>  — notificação de nova promoção na categoria
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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pika
from shared.rabbitmq_utils import (
    get_connection, declare_exchange, payload_to_bytes,
    EXCHANGE_NAME,
)
from shared.crypto_utils import verify_event

QUEUE_NAME = "Fila_Notificacao"

# cache local: id -> dados da promoção (necessário para saber categoria no hot deal)
_cache: dict[str, dict] = {}


def _publish_raw(routing_key: str, payload: dict):
    """Publica evento sem envelope de assinatura (direto para clientes)."""
    conn = get_connection()
    ch   = conn.channel()
    declare_exchange(ch)
    ch.basic_publish(
        exchange=EXCHANGE_NAME,
        routing_key=routing_key,
        body=json.dumps(payload, ensure_ascii=False).encode(),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    print(f"  [→] Notificação publicada em '{routing_key}'")
    conn.close()


def _on_message(ch, method, props, body):
    routing_key = method.routing_key
    envelope    = json.loads(body)
    payload     = envelope["payload"]
    signature   = envelope["signature"]

    print(f"\n[MS Notificação] Evento '{routing_key}' recebido.")

    # determina o produtor esperado para validar assinatura
    if routing_key == "promocao.publicada":
        producer = "promocao"
    else:  # promocao.destaque
        producer = "ranking"

    if not verify_event(payload_to_bytes(payload), signature, producer):
        print(f"[MS Notificação] ⚠ Assinatura INVÁLIDA ({producer}) — descartado.")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    print(f"[MS Notificação] ✔ Assinatura válida ({producer}).")

    # ── Promoção nova publicada ────────────────────────────────
    if routing_key == "promocao.publicada":
        pid       = payload["id"]
        categoria = payload["categoria"]
        _cache[pid] = payload

        notif = {
            "tipo":      "nova_promocao",
            "id":        pid,
            "titulo":    payload["titulo"],
            "categoria": categoria,
            "descricao": payload["descricao"],
            "preco":     payload["preco"],
        }
        _publish_raw(f"promocao.{categoria}", notif)
        print(f"[MS Notificação] ✔ Notificação enviada para categoria '{categoria}'.")

    # ── Promoção em destaque ───────────────────────────────────
    elif routing_key == "promocao.destaque":
        pid  = payload["promocao_id"]
        prom = _cache.get(pid, {})

        # O MS Ranking já publicou promocao.destaque direto no broker.
        # Notifica na categoria da promoção (promocao.<categoria>) 
        # para clientes que seguem a categoria mas talvez não estejam
        # inscritos em promocao.destaque.
        if prom:
            categoria = prom.get("categoria", "desconhecida")
            notif_cat = {
                "tipo":      "hot_deal",
                "id":        pid,
                "titulo":    prom.get("titulo", "?"),
                "categoria": categoria,
                "descricao": prom.get("descricao", ""),
                "preco":     prom.get("preco", 0),
                "score":     payload["score"],
                "label":     "🔥 HOT DEAL",
            }
            _publish_raw(f"promocao.{categoria}", notif_cat)
            print(f"[MS Notificação] ✔ Hot deal notificado em 'promocao.{categoria}' (id={pid}).")
        else:
            print(f"[MS Notificação] ⚠ Promoção '{pid}' não encontrada no cache — "
                  "notificação de categoria ignorada.")

    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    conn = get_connection()
    ch   = conn.channel()
    declare_exchange(ch)

    ch.queue_declare(queue=QUEUE_NAME, durable=True)
    ch.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key="promocao.publicada")
    ch.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key="promocao.destaque")
    ch.basic_qos(prefetch_count=1)
    ch.basic_consume(queue=QUEUE_NAME, on_message_callback=_on_message)

    print("[MS Notificação] Aguardando eventos... (Ctrl+C para sair)")
    ch.start_consuming()


if __name__ == "__main__":
    main()
