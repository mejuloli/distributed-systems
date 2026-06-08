"""
MS Notificação
--------------
Consome promoções publicadas e hot deals, envia e-mails para a loja e publica
eventos assinados para o Gateway encaminhar por SSE.
"""

import os
import sys
import json

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.crypto_utils import sign_event, verify_event
from shared.rabbitmq_utils import (
    EXCHANGE_NAME,
    declare_exchange,
    get_connection,
    payload_to_bytes,
    publish_event,
)

SERVICE_NAME = "notificacao"
QUEUE_NAME = "Fila_Notificacao"


def enviar_email(para: str, assunto: str, texto: str):
    api_key = os.getenv("RESEND_API_KEY")
    remetente = os.getenv("RESEND_FROM_EMAIL", "Sistema de Promoções <onboarding@resend.dev>")
    destino = os.getenv("RESEND_TO_OVERRIDE") or para

    if not api_key or not destino:
        print(f"[MS Notificação] E-mail simulado para {destino or para}: {assunto} | {texto}")
        return {"simulado": True}

    try:
        resposta = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": remetente,
                "to": [destino],
                "subject": assunto,
                "text": texto,
            },
            timeout=10,
        )
        resposta.raise_for_status()
        print(f"[MS Notificação] E-mail enviado para {destino}: {assunto}")
        return resposta.json()
    except Exception as exc:
        print(f"[MS Notificação] Falha no envio real. Simulação registrada: {exc}")
        return {"simulado": True, "erro": str(exc)}


def payload_notificacao(payload: dict, tipo: str) -> dict:
    dados = {
        "tipo": tipo,
        "promocao_id": payload["promocao_id"],
        "loja_id": payload.get("loja_id"),
        "loja_email": payload.get("loja_email"),
        "titulo": payload.get("titulo", ""),
        "categoria": payload.get("categoria", "").strip().lower(),
        "descricao": payload.get("descricao", ""),
        "preco": payload.get("preco", 0),
        "hot_deal": bool(payload.get("hot_deal", False)),
    }
    if "score" in payload:
        dados["score"] = payload["score"]
    return dados


def publicar_notificacao(routing_key: str, payload: dict):
    assinatura = sign_event(payload_to_bytes(payload), SERVICE_NAME)
    publish_event(routing_key, payload, assinatura)


def on_message(ch, method, props, body):
    routing_key = method.routing_key

    try:
        envelope = json.loads(body)
        payload = envelope["payload"]
        signature = envelope["signature"]

        producer = "promocao" if routing_key == "promocao.publicada" else "ranking"
        if not verify_event(payload_to_bytes(payload), signature, producer):
            print(f"[MS Notificação] Assinatura inválida ({producer}) - descartado.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        titulo = payload.get("titulo", "promoção")
        loja_email = payload.get("loja_email")

        if routing_key == "promocao.publicada":
            enviar_email(
                loja_email,
                "Promoção aprovada",
                f"Sua promoção '{titulo}' foi aprovada e publicada.",
            )
            notif = payload_notificacao(payload, "categoria")
            publicar_notificacao("promocao.categoria", notif)
            print(f"[MS Notificação] Evento promocao.categoria publicado para {notif['categoria']}.")

        else:
            enviar_email(
                loja_email,
                "Promoção virou hot deal",
                f"Sua promoção '{titulo}' atingiu destaque como hot deal.",
            )
            notif = payload_notificacao({**payload, "hot_deal": True}, "hotdeal")
            publicar_notificacao("notificacao.hotdeal", notif)
            print(f"[MS Notificação] Evento notificacao.hotdeal publicado para {titulo}.")

    except Exception as exc:
        print(f"[MS Notificação] Erro ao processar evento: {exc}")
    finally:
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
        ch.basic_consume(queue=QUEUE_NAME, on_message_callback=on_message)

        print("[MS Notificação] Aguardando eventos... (Ctrl+C para sair)")
        ch.start_consuming()
    except KeyboardInterrupt:
        print("\n[MS Notificação] Interrompido pelo usuário. Encerrando...")
        conn.close()


if __name__ == "__main__":
    main()
