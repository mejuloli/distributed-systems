"""
MS Gateway/API
--------------
Expõe a API REST consumida pelo frontend, publica ações no RabbitMQ e mantém
conexões SSE para consumidores interessados em categorias e hot deals.
"""

import json
import os
import queue
import sys
import threading
import time

from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.crypto_utils import sign_event, verify_event
from shared.rabbitmq_utils import (
    EXCHANGE_NAME,
    declare_exchange,
    get_connection,
    payload_to_bytes,
    publish_event,
)

SERVICE_NAME = "gateway"
QUEUE_NAME = "Fila_Gateway_API"

app = Flask(__name__)
CORS(app)

promocoes: dict[str, dict] = {}
interesses: dict[str, set[str]] = {}
sse_clients: dict[str, list[queue.Queue]] = {}
hotdeals_notificados: set[str] = set()
lock = threading.RLock()


def normalizar_categoria(categoria: str) -> str:
    return (categoria or "").strip().lower()


def resposta_erro(mensagem: str, status: int):
    return jsonify({"erro": mensagem}), status


def validar_payload_promocao(payload: dict):
    campos = ["promocao_id", "loja_id", "loja_email", "titulo", "categoria", "descricao", "preco"]
    ausentes = [campo for campo in campos if campo not in payload]
    if ausentes:
        return f"Campos ausentes: {', '.join(ausentes)}"

    if not str(payload["promocao_id"]).strip():
        return "promocao_id é obrigatório."
    if not str(payload["loja_email"]).strip():
        return "loja_email é obrigatório."
    if not str(payload["titulo"]).strip():
        return "titulo é obrigatório."
    if not normalizar_categoria(payload["categoria"]):
        return "categoria é obrigatória."
    if not str(payload["descricao"]).strip():
        return "descricao é obrigatória."

    try:
        preco = float(payload["preco"])
    except (TypeError, ValueError):
        return "preco deve ser numérico."

    if preco <= 0:
        return "preco deve ser maior que zero."

    return None


def registrar_cliente_sse(cliente_id: str) -> queue.Queue:
    fila = queue.Queue()
    with lock:
        sse_clients.setdefault(cliente_id, []).append(fila)
    return fila


def remover_cliente_sse(cliente_id: str, fila: queue.Queue):
    with lock:
        filas = sse_clients.get(cliente_id, [])
        if fila in filas:
            filas.remove(fila)
        if not filas:
            sse_clients.pop(cliente_id, None)


def enviar_sse(cliente_id: str, evento: dict):
    with lock:
        filas = list(sse_clients.get(cliente_id, []))

    for fila in filas:
        fila.put(evento)


def enviar_sse_por_categoria(categoria: str, evento: dict):
    categoria = normalizar_categoria(categoria)
    with lock:
        clientes = [
            cliente_id
            for cliente_id, categorias in interesses.items()
            if categoria in categorias
        ]

    for cliente_id in clientes:
        enviar_sse(cliente_id, evento)


def enviar_sse_para_todos(evento: dict):
    with lock:
        clientes = list(sse_clients.keys())

    for cliente_id in clientes:
        enviar_sse(cliente_id, evento)


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/promocoes")
def listar_promocoes():
    with lock:
        dados = list(promocoes.values())

    dados.sort(key=lambda item: item.get("titulo", "").lower())
    return jsonify(dados)


@app.post("/api/promocoes")
def cadastrar_promocao():
    envelope = request.get_json(silent=True) or {}
    payload = envelope.get("payload")
    assinatura = envelope.get("assinatura") or envelope.get("signature")

    if not isinstance(payload, dict) or not assinatura:
        return resposta_erro("Envie { payload, assinatura }.", 400)

    erro = validar_payload_promocao(payload)
    if erro:
        return resposta_erro(erro, 400)

    payload = {
        **payload,
        "categoria": normalizar_categoria(payload["categoria"]),
        "preco": float(payload["preco"]),
    }

    publish_event("promocao.recebida", payload, assinatura)
    return jsonify({"mensagem": "Promoção recebida e enviada para validação."}), 202


@app.post("/api/promocoes/<promocao_id>/votos")
def votar_promocao(promocao_id: str):
    dados = request.get_json(silent=True) or {}
    voto = dados.get("voto")
    if voto not in ("positivo", "negativo"):
        return resposta_erro("voto deve ser positivo ou negativo.", 400)

    with lock:
        promocao = promocoes.get(promocao_id)

    if not promocao:
        return resposta_erro("Promoção não encontrada.", 404)

    payload = {
        "promocao_id": promocao["promocao_id"],
        "loja_id": promocao.get("loja_id"),
        "loja_email": promocao.get("loja_email"),
        "titulo": promocao["titulo"],
        "categoria": promocao["categoria"],
        "descricao": promocao["descricao"],
        "preco": promocao["preco"],
        "voto": voto,
    }
    assinatura = sign_event(payload_to_bytes(payload), SERVICE_NAME)
    publish_event("promocao.voto", payload, assinatura)
    return jsonify({"mensagem": f"Voto {voto} enviado para processamento."}), 202


@app.get("/api/interesses")
def listar_interesses():
    cliente_id = request.args.get("cliente_id", "").strip()
    if not cliente_id:
        return resposta_erro("cliente_id é obrigatório.", 400)

    with lock:
        categorias = sorted(interesses.get(cliente_id, set()))

    return jsonify({"cliente_id": cliente_id, "categorias": categorias})


@app.post("/api/interesses")
def seguir_categoria():
    dados = request.get_json(silent=True) or {}
    cliente_id = str(dados.get("cliente_id", "")).strip()
    categoria = normalizar_categoria(dados.get("categoria", ""))

    if not cliente_id or not categoria:
        return resposta_erro("cliente_id e categoria são obrigatórios.", 400)

    with lock:
        interesses.setdefault(cliente_id, set()).add(categoria)
        categorias = sorted(interesses[cliente_id])

    return jsonify({"cliente_id": cliente_id, "categorias": categorias})


@app.delete("/api/interesses/<categoria>")
def parar_categoria(categoria: str):
    cliente_id = request.args.get("cliente_id", "").strip()
    categoria = normalizar_categoria(categoria)

    if not cliente_id or not categoria:
        return resposta_erro("cliente_id e categoria são obrigatórios.", 400)

    with lock:
        interesses.setdefault(cliente_id, set()).discard(categoria)
        categorias = sorted(interesses[cliente_id])

    return jsonify({"cliente_id": cliente_id, "categorias": categorias})


@app.get("/api/sse")
def sse():
    cliente_id = request.args.get("cliente_id", "").strip()
    if not cliente_id:
        return resposta_erro("cliente_id é obrigatório.", 400)

    fila = registrar_cliente_sse(cliente_id)
    fila.put({
        "tipo": "conexao",
        "mensagem": "Conexão SSE estabelecida.",
    })

    def stream():
        try:
            while True:
                try:
                    evento = fila.get(timeout=20)
                    yield f"data: {json.dumps(evento, ensure_ascii=False)}\n\n"
                except queue.Empty:
                    yield "event: ping\ndata: {}\n\n"
        finally:
            remover_cliente_sse(cliente_id, fila)

    return Response(
        stream_with_context(stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def atualizar_promocao_publicada(payload: dict):
    promocao = {
        **payload,
        "categoria": normalizar_categoria(payload.get("categoria", "")),
        "hot_deal": bool(payload.get("hot_deal", False)),
    }
    with lock:
        existente = promocoes.get(promocao["promocao_id"], {})
        promocoes[promocao["promocao_id"]] = {**existente, **promocao}


def marcar_hotdeal(payload: dict) -> bool:
    promocao_id = payload.get("promocao_id")
    if not promocao_id:
        return False

    with lock:
        novo_hotdeal = promocao_id not in hotdeals_notificados
        hotdeals_notificados.add(promocao_id)
        atual = promocoes.get(promocao_id, {})
        promocoes[promocao_id] = {
            **atual,
            **payload,
            "categoria": normalizar_categoria(payload.get("categoria", atual.get("categoria", ""))),
            "hot_deal": True,
        }
        return novo_hotdeal


def evento_sse(tipo: str, payload: dict) -> dict:
    titulo = payload.get("titulo", "promoção")
    categoria = normalizar_categoria(payload.get("categoria", ""))

    if tipo == "hotdeal":
        mensagem = f"{titulo} virou hot deal."
    else:
        mensagem = f"Nova promoção em {categoria}: {titulo}."

    return {
        "tipo": tipo,
        "promocao_id": payload.get("promocao_id"),
        "categoria": categoria,
        "mensagem": mensagem,
    }


def on_evento(ch, method, props, body):
    routing_key = method.routing_key
    try:
        envelope = json.loads(body)
        payload = envelope["payload"]
        assinatura = envelope["signature"]

        produtores = {
            "promocao.publicada": "promocao",
            "promocao.categoria": "notificacao",
            "promocao.destaque": "ranking",
            "notificacao.hotdeal": "notificacao",
        }
        produtor = produtores.get(routing_key)

        if not produtor or not verify_event(payload_to_bytes(payload), assinatura, produtor):
            print(f"[MS Gateway] Assinatura inválida em '{routing_key}'. Evento descartado.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        if routing_key == "promocao.publicada":
            atualizar_promocao_publicada(payload)
            print(f"[MS Gateway] Promoção publicada em cache: {payload.get('titulo')}")

        elif routing_key == "promocao.categoria":
            enviar_sse_por_categoria(payload.get("categoria", ""), evento_sse("categoria", payload))
            print(f"[MS Gateway] SSE categoria enviado: {payload.get('categoria')}")

        else:
            if marcar_hotdeal(payload):
                enviar_sse_para_todos(evento_sse("hotdeal", payload))
                print(f"[MS Gateway] SSE hot deal enviado: {payload.get('titulo')}")

    except Exception as exc:
        print(f"[MS Gateway] Erro ao processar evento: {exc}")
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)


def consumer_thread():
    while True:
        try:
            conn = get_connection()
            ch = conn.channel()
            declare_exchange(ch)
            ch.queue_declare(queue=QUEUE_NAME, durable=True)

            for routing_key in (
                "promocao.publicada",
                "promocao.categoria",
                "promocao.destaque",
                "notificacao.hotdeal",
            ):
                ch.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key=routing_key)

            ch.basic_qos(prefetch_count=1)
            ch.basic_consume(queue=QUEUE_NAME, on_message_callback=on_evento)
            print("[MS Gateway] Consumidor RabbitMQ iniciado.")
            ch.start_consuming()
        except Exception as exc:
            print(f"[MS Gateway] Consumidor reiniciando após erro: {exc}")
            time.sleep(3)


if __name__ == "__main__":
    threading.Thread(target=consumer_thread, daemon=True).start()
    port = int(os.getenv("GATEWAY_PORT", "5000"))
    app.run(host="0.0.0.0", port=port, threaded=True)
