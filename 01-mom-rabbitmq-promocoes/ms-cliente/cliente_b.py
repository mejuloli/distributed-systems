"""
Cliente B
─────────
Interesses (hard coded): eletrônicos e promoções em destaque.
Routing keys: promocao.eletronicos | promocao.destaque

Fontes das mensagens por routing key:
  promocao.eletronicos → MS Notificação (payload raw, sem assinatura)
  promocao.destaque    → MS Ranking     (envelope assinado com chave do ranking)

Política de descarte:
  - Mensagens de promocao.destaque têm assinatura do MS Ranking e são
    validadas antes de exibir. Se inválida, a mensagem é descartada.
  - Mensagens de categoria chegam sem assinatura — exibidas diretamente.
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.rabbitmq_utils import get_connection, declare_exchange, EXCHANGE_NAME, payload_to_bytes
from shared.crypto_utils import verify_event

CLIENT_NAME  = "Cliente_B"
QUEUE_NAME   = "Fila_Cliente_B"
ROUTING_KEYS = ["promocao.eletronicos", "promocao.destaque"]

SIGNED_KEYS = {"promocao.destaque"}


def _on_notificacao(ch, method, props, body):
    rk = method.routing_key

    try:
        data = json.loads(body)
    except Exception:
        print(f"[{CLIENT_NAME}] ✗ Mensagem malformada em '{rk}' — descartada.")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    if rk in SIGNED_KEYS:
        if "payload" not in data or "signature" not in data:
            print(f"[{CLIENT_NAME}] ✗ Envelope ausente em '{rk}' — descartado.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return
        payload   = data["payload"]
        signature = data["signature"]
        if not verify_event(payload_to_bytes(payload), signature, "ranking"):
            print(f"[{CLIENT_NAME}] ⚠ Assinatura INVÁLIDA em '{rk}' — descartado.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return
    else:
        payload = data

    print(f"\n{'═'*55}")
    if payload.get("tipo") == "hot_deal" or payload.get("label") or payload.get("hot_deal"):
        print(f"[{CLIENT_NAME}] 🔥 HOT DEAL — via '{rk}'")
        print(f"  Título : {payload.get('titulo', '?')}")
        print(f"  Score  : {payload.get('score', '?')}")
    else:
        print(f"[{CLIENT_NAME}] 🔔 Nova promoção — via '{rk}'")
        print(f"  Título    : {payload.get('titulo', '?')}")
        print(f"  Categoria : {payload.get('categoria', '?')}")
        print(f"  Preço     : R${payload.get('preco', 0):.2f}")
        print(f"  Descrição : {payload.get('descricao', '')}")
    print(f"{'═'*55}")

    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    conn = get_connection()
    ch   = conn.channel()
    declare_exchange(ch)

    ch.queue_declare(queue=QUEUE_NAME, durable=False, auto_delete=True)
    for rk in ROUTING_KEYS:
        ch.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key=rk)

    ch.basic_consume(queue=QUEUE_NAME, on_message_callback=_on_notificacao)
    print(f"[{CLIENT_NAME}] Inscrito em: {', '.join(ROUTING_KEYS)}")
    print(f"[{CLIENT_NAME}] Aguardando notificações... (Ctrl+C para sair)")
    ch.start_consuming()


if __name__ == "__main__":
    main()
