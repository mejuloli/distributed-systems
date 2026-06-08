"""
Utilitários de conexão e publicação no RabbitMQ.
Exchange única do tipo 'topic' chamada 'Promocoes'.
"""

import json
import os
import time

import pika

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5673"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")
EXCHANGE_NAME= "Promocoes"
EXCHANGE_TYPE= "topic"


def get_connection() -> pika.BlockingConnection:
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    params = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
        heartbeat=600,
        blocked_connection_timeout=300,
    )

    last_error = None
    for _ in range(30):
        try:
            return pika.BlockingConnection(params)
        except pika.exceptions.AMQPConnectionError as exc:
            last_error = exc
            time.sleep(2)

    raise last_error


def declare_exchange(channel):
    channel.exchange_declare(
        exchange=EXCHANGE_NAME,
        exchange_type=EXCHANGE_TYPE,
        durable=True,
    )


def payload_to_bytes(payload: dict) -> bytes:
    """Serializa payload para assinar/verificar."""
    return json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()


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
