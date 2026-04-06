"""
MS Ranking
──────────
Processa votos e identifica promoções em destaque (hot deal).

Consome : promocao.voto     (do MS Gateway)
Publica : promocao.destaque (assinado com chave do MS Ranking)

Regra de hot deal:
    score = votos_positivos - votos_negativos >= HOT_DEAL_SCORE (padrão: 5)
    Ao atingir o limite, publica promocao.destaque UMA ÚNICA VEZ por promoção.
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

SERVICE_NAME   = "ranking"
QUEUE_NAME     = "Fila_Ranking"
HOT_DEAL_SCORE = 5

# estrutura de scores: { promocao_id: { "positivo": N, "negativo": N, "hot_deal": bool } }
scores: dict[str, dict] = {}


def _on_voto(ch, method, props, body):
    envelope  = json.loads(body)
    payload   = envelope["payload"]
    signature = envelope["signature"]

    pid = payload.get("promocao_id", "?")
    print(f"\n[MS Ranking] Voto recebido para '{pid}'")

    # 1. valida assinatura do Gateway
    if not verify_event(payload_to_bytes(payload), signature, "gateway"):
        print("[MS Ranking] ⚠ Assinatura INVÁLIDA — voto descartado.")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    voto = payload.get("voto", "")
    if voto not in ("positivo", "negativo"):
        print(f"[MS Ranking] ✗ Voto inválido: '{voto}'. Descartado.")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    # 2. atualiza contadores
    if pid not in scores:
        scores[pid] = {"positivo": 0, "negativo": 0, "hot_deal": False}

    scores[pid][voto] += 1
    score = scores[pid]["positivo"] - scores[pid]["negativo"]
    print(f"[MS Ranking] Score de '{pid}': {score:+d}  "
          f"(+{scores[pid]['positivo']} / -{scores[pid]['negativo']})")

    # 3. verifica hot deal
    if score >= HOT_DEAL_SCORE and not scores[pid]["hot_deal"]:
        scores[pid]["hot_deal"] = True
        hot_payload = {
            "promocao_id": pid,
            "score":       score,
            "hot_deal":    True,
        }
        sig = sign_event(payload_to_bytes(hot_payload), SERVICE_NAME)
        publish_event("promocao.destaque", hot_payload, sig)
        print(f"[MS Ranking] 🔥 HOT DEAL! Promoção '{pid}' promovida (score={score}).")

    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    conn = get_connection()
    ch   = conn.channel()
    declare_exchange(ch)

    ch.queue_declare(queue=QUEUE_NAME, durable=True)
    ch.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key="promocao.voto")
    ch.basic_qos(prefetch_count=1)
    ch.basic_consume(queue=QUEUE_NAME, on_message_callback=_on_voto)

    print(f"[MS Ranking] Aguardando eventos 'promocao.voto'... "
          f"(hot deal em score >= {HOT_DEAL_SCORE}) (Ctrl+C para sair)")
    ch.start_consuming()


if __name__ == "__main__":
    main()
