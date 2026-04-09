"""
MS Gateway 
----------
Responsável por receber as promoções submetidas vendedores e manter uma lista local das promoções validadas para os clientes. 
Também é o ponto central para os clientes votarem, publicando os eventos de voto assinado para que o MS Promoção possa processá-los.
"""
import sys
import os
import json
import uuid
import threading
import time
# garante que o python encontre a pasta 'shared'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.rabbitmq_utils import (
    get_connection, declare_exchange, publish_event,
    payload_to_bytes, EXCHANGE_NAME,
)
from shared.crypto_utils import sign_event, verify_event

SERVICE_NAME = "gateway"
QUEUE_NAME = "Fila_Gateway"

# lista local para promoções validadas: ID -> payload
promocoes_validadas: dict[str, dict] = {}
_lock = threading.Lock()
conn = None

def publicar_promocao(titulo: str, categoria: str, descricao: str, preco: float):
    payload = {
        "promocao_id":  str(uuid.uuid4()),
        "titulo":       titulo,
        "categoria":    categoria.lower().strip(),
        "descricao":    descricao,
        "preco":        preco,
    }
    sig = sign_event(payload_to_bytes(payload), SERVICE_NAME)
    publish_event("promocao.recebida", payload, sig)
    print("\n[MS Gateway] Enviado! Aguardando validação do MS Promoção...")


def votar_promocao(promocao: dict, voto: str):
    payload = {
        "promocao_id":  promocao["promocao_id"],
        "titulo":       promocao["titulo"],
        "categoria":    promocao["categoria"],
        "descricao":    promocao["descricao"],
        "preco":        promocao["preco"],
        "voto":         voto,
    }
    sig = sign_event(payload_to_bytes(payload), SERVICE_NAME)
    publish_event("promocao.voto", payload, sig)
    print(f"\n[MS Gateway] Voto '{voto}' computado.")


def _on_promocao_publicada(ch, method, props, body):
    envelope= json.loads(body)
    payload = envelope["payload"]
    signature = envelope["signature"]

    if not verify_event(payload_to_bytes(payload), signature, "promocao"):
        print("\n\n[MS Gateway] Assinatura INVÁLIDA na promoção nova - descartado.")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    with _lock:
        promocoes_validadas[payload["promocao_id"]] = payload
        total_atual = len(promocoes_validadas)
    
    print(f"\n\n{'-'*60}")
    print(f" NOVA PROMOÇÃO VALIDADA: {payload['titulo']}")
    print(f" Preço: R$ {payload['preco']:.2f}")
    print(f" Total em memória: {total_atual} itens")
    print(f"{'-'*60}")
    print("(Menu desatualizado acima. Digite sua opção ou Enter para atualizar)")
    
    ch.basic_ack(delivery_tag=method.delivery_tag)


def _consumer_thread():
    """Thread separada para rodar o consumidor do RabbitMQ sem travar o menu."""
    global conn
    try:
        conn = get_connection()
        ch = conn.channel()
        declare_exchange(ch)
        ch.queue_declare(queue=QUEUE_NAME, durable=True)
        ch.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key="promocao.publicada")
        ch.basic_consume(queue=QUEUE_NAME, on_message_callback=_on_promocao_publicada)
        print("[MS Gateway] Conector RabbitMQ pronto na porta 5673.")
        ch.start_consuming()
    except Exception as e:
        print(f"\n[MS Gateway] Falha no consumidor: {e}")


def _menu():
    while True:
        print(f"\n--- [ STATUS: {len(promocoes_validadas)} itens validados ] ---")
        print("╔══════════════════════════════════════════╗")
        print("║     MS Gateway DE PROMOÇÕES - Gateway    ║")
        print("╠══════════════════════════════════════════╣")
        print("║  1. Cadastrar nova promoção              ║")
        print("║  2. Listar promoções (Lista Local)       ║")
        print("║  3. Votar em uma promoção                ║")
        print("║  0. Sair                                 ║")
        print("╚══════════════════════════════════════════╝")
        
        op = input("Escolha uma opção > ").strip()

        if op == "1":
            print("\n--- CADASTRO ---")
            titulo = input("Título: ").strip()
            categoria = input("Categoria: ").strip()
            descricao = input("Descrição: ").strip()
            try:
                preco = float(input("Preço (R$): ").strip().replace(",", "."))
                publicar_promocao(titulo, categoria, descricao, preco)
            except ValueError:
                print("\n[MS Gateway] Preço deve ser um número.")

        elif op == "2":
            with _lock:
                proMS = list(promocoes_validadas.values())
            if not proMS:
                print("\n[MS Gateway] Nenhuma promoção validada na memória local.")
            else:
                print(f"\n{'ID (Resumido)':<15} | {'Título':<25} | {'Preço':<10}")
                print("-" * 60)
                for p in proMS:
                    short_id = p['promocao_id'][:8] + "..."
                    print(f"{short_id:<15} | {p['titulo']:<25} | R$ {p['preco']:.2f}")

        elif op == "3":
            with _lock:
                proMS = list(promocoes_validadas.values())
            if not proMS:
                print("\n[MS Gateway] Nada disponível para votação.")
                continue
            
            for i, p in enumerate(proMS, 1):
                print(f"{i}. {p['titulo']} (ID: {p['promocao_id'][:8]})")
            
            try:
                idx = int(input("\nNúmero da promoção: ")) - 1
                promo = proMS[idx]
                voto = input("Voto (p = positivo / n = negativo): ").strip().lower()
                voto_traduzido = "positivo" if voto == 'p' else "negativo"
                votar_promocao(promo, voto_traduzido)
            except (ValueError, IndexError):
                print("\n[MS Gateway] Seleção inválida.")

        elif op == "0":
            encerrar_sistema()
        
        elif op == "":
            continue
        else:
            print("\n[MS Gateway] Opção inválida.")


def encerrar_sistema():
    global conn
    if conn and conn.is_open:
        conn.close()
    os._exit(0)

if __name__ == "__main__":
    t = threading.Thread(target=_consumer_thread, daemon=True)
    t.start()
    
    time.sleep(0.6)
    try:
        _menu()
    except KeyboardInterrupt:
        print("\n[MS Gateway] Interrompido pelo usuário (Ctrl+C). Encerrando...")
        encerrar_sistema()