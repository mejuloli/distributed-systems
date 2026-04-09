"""
Utilitários de conexão e publicação no RabbitMQ.
Exchange única do tipo 'topic' chamada 'Promocoes'.
"""

import json
import pika

RABBITMQ_HOST = "localhost"
EXCHANGE_NAME= "Promocoes"
EXCHANGE_TYPE= "topic"


def get_connection() -> pika.BlockingConnection:
    return pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST, port=5673)
    )


def declare_exchange(channel):
    channel.exchange_declare(
        exchange=EXCHANGE_NAME,
        exchange_type=EXCHANGE_TYPE,
        durable=True,
    )


def payload_to_bytes(payload: dict) -> bytes:
    """Serializa payload para assinar/verificar."""
    return json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()


def publish_event(routing_key: str, payload: dict, signature: str, channel=None):
    """
    Publica um evento na exchange 'Promocoes'.
    Envelope: { "payload": {...}, "signature": "base64..." }
    Se channel for None, abre e fecha uma conexão temporária.
    """
    envelope = {
        "payload":   payload,
        "signature": signature,
    }
    message = json.dumps(envelope, ensure_ascii=False).encode()

    conn = None
    own_conn = channel is None
    if own_conn:
        conn = get_connection()
        channel = conn.channel()
        declare_exchange(channel)

    channel.basic_publish(
        exchange=EXCHANGE_NAME,
        routing_key=routing_key,
        body=message,
        properties=pika.BasicProperties(delivery_mode=2),  # mensagem persistente
    )
    print(f"  [→] Evento publicado em routing_key='{routing_key}'")

    if own_conn and conn:
        conn.close()
