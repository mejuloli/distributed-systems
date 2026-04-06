"""
MS Gateway - versão final
ponto de entrada do sistema com interface terminal
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

SERVICE_NAME   = "Gateway"
QUEUE_NAME     = "Fila_Gateway"

# lista local em memória para armazenar promoções validadas
promocoes_validadas: dict[str, dict] = {}
_lock = threading.Lock()

# ──────────────────────────────────────────────────────────────
# funções de lógica de publicação
# ──────────────────────────────────────────────────────────────

def publicar_promocao(titulo: str, categoria: str, descricao: str, preco: float):
    # gera o payload da nova promoção
    payload = {
        "id":        str(uuid.uuid4()),
        "titulo":    titulo,
        "categoria": categoria.lower().strip(),
        "descricao": descricao,
        "preco":     preco,
    }
    # assina o evento com a chave privada do Gateway
    sig = sign_event(payload_to_bytes(payload), SERVICE_NAME)
    # envia para a routing key de recebimento
    publish_event("promocao.recebida", payload, sig)
    print("\n[SISTEMA] ✔ Enviado! Aguardando validação do MS Promoção...")


def votar_promocao(promocao_id: str, voto: str):
    # gera o payload do voto
    payload = {
        "promocao_id": promocao_id,
        "voto":        voto,
    }
    # assina o evento
    sig = sign_event(payload_to_bytes(payload), SERVICE_NAME)
    # envia para a routing key de votos
    publish_event("promocao.voto", payload, sig)
    print(f"\n[SISTEMA] ✔ Voto '{voto}' computado.")


def excluir_promocao(promocao_id: str):
    # gera o payload de exclusão
    payload = {
        "promocao_id": promocao_id,
        "status": "removida"
    }
    # assina o evento para garantir autenticidade da remoção
    sig = sign_event(payload_to_bytes(payload), SERVICE_NAME)
    
    # publica o evento de exclusão para o sistema
    publish_event("promocao.excluida", payload, sig)
    
    # remove da memória local do Gateway imediatamente para atualizar a lista
    with _lock:
        if promocao_id in promocoes_validadas:
            del promocoes_validadas[promocao_id]
            
    print("\n[SISTEMA] 🗑 Promoção removida localmente e evento de exclusão enviado.")


# ────────────────────────────────────────────────────────────────
# consumidor (thread de fundo) - escuta validações do MS Promoção
# ────────────────────────────────────────────────────────────────

def _on_promocao_publicada(ch, method, props, body):
    # decodifica o envelope recebido
    envelope  = json.loads(body)
    payload   = envelope["payload"]
    signature = envelope["signature"]

    # validação RSA: verifica se quem publicou foi o MS Promoção
    if not verify_event(payload_to_bytes(payload), signature, "promocao"):
        print("\n\n[ALERTA] ⚠ Assinatura INVÁLIDA detectada! Mensagem descartada.")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    # salva na lista local de forma segura e define o total
    with _lock:
        promocoes_validadas[payload["id"]] = payload
        total_atual = len(promocoes_validadas) # definindo a variável
    
    # aviso visual de que uma nova promoção chegou
    print(f"\n\n{'─'*60}")
    print(f" ✨ NOVA PROMOÇÃO VALIDADA: {payload['titulo']}")
    print(f" 💰 Preço: R$ {payload['preco']:.2f}")
    print(f" 📈 Total em memória: {total_atual} itens")
    print(f"{'─'*60}")
    print("(Menu desatualizado acima. Digite sua opção ou Enter para atualizar)")
    
    ch.basic_ack(delivery_tag=method.delivery_tag)


def _consumer_thread():
    # configura a conexão e consumo da fila do Gateway
    try:
        conn = get_connection()
        ch   = conn.channel()
        declare_exchange(ch)
        ch.queue_declare(queue=QUEUE_NAME, durable=True)
        ch.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key="promocao.publicada")
        ch.basic_consume(queue=QUEUE_NAME, on_message_callback=_on_promocao_publicada)
        print("[Gateway] Conector RabbitMQ pronto na porta 5673.")
        ch.start_consuming()
    except Exception as e:
        print(f"\n[ERRO] Falha no consumidor: {e}")


# ──────────────────────────────────────────────────────────────
# interface do usuário (menu terminal)
# ──────────────────────────────────────────────────────────────

def _menu():
    while True:
        # exibe o cabeçalho com o contador de promoções em cache
        print(f"\n--- [ STATUS: {len(promocoes_validadas)} itens validados ] ---")
        print("╔══════════════════════════════════════════╗")
        print("║     🛒  SISTEMA DE PROMOÇÕES — Gateway   ║")
        print("╠══════════════════════════════════════════╣")
        print("║  1. Cadastrar nova promoção              ║")
        print("║  2. Listar promoções (Lista Local)       ║")
        print("║  3. Votar em uma promoção                ║")
        print("║  4. Excluir uma promoção                 ║")
        print("║  0. Sair                                 ║")
        print("╚══════════════════════════════════════════╝")
        
        op = input("Escolha uma opção > ").strip()

        if op == "1":
            # fluxo de cadastro
            print("\n--- CADASTRO ---")
            titulo    = input("Título: ").strip()
            categoria = input("Categoria: ").strip()
            descricao = input("Descrição: ").strip()
            try:
                preco = float(input("Preço (R$): ").strip().replace(",", "."))
                publicar_promocao(titulo, categoria, descricao, preco)
            except ValueError:
                print("\n[ERRO] Preço deve ser um número.")

        elif op == "2":
            # lista o que está salvo na memória local do Gateway
            with _lock:
                proMS = list(promocoes_validadas.values())
            if not proMS:
                print("\n[!] Nenhuma promoção validada na memória local.")
            else:
                print(f"\n{'ID (Resumido)':<15} | {'Título':<25} | {'Preço':<10}")
                print("-" * 60)
                for p in proMS:
                    short_id = p['id'][:8] + "..."
                    print(f"{short_id:<15} | {p['titulo']:<25} | R$ {p['preco']:.2f}")

        elif op == "3":
            # fluxo de votação
            with _lock:
                proMS = list(promocoes_validadas.values())
            if not proMS:
                print("\n[!] Nada disponível para votação.")
                continue
            
            for i, p in enumerate(proMS, 1):
                print(f"{i}. {p['titulo']} (ID: {p['id'][:8]})")
            
            try:
                idx = int(input("\nNúmero da promoção: ")) - 1
                p   = proMS[idx]
                voto = input("Voto (p = positivo / n = negativo): ").strip().lower()
                voto_traduzido = "positivo" if voto == 'p' else "negativo"
                votar_promocao(p["id"], voto_traduzido)
            except (ValueError, IndexError):
                print("\n[ERRO] Seleção inválida.")

        elif op == "4":
            # fluxo de exclusão
            with _lock:
                proMS = list(promocoes_validadas.values())
            if not proMS:
                print("\n[!] Nada para excluir.")
                continue
            
            print("\n--- EXCLUSÃO ---")
            for i, p in enumerate(proMS, 1):
                print(f"{i}. {p['titulo']} (ID: {p['id'][:8]})")
            
            try:
                idx_input = input("\nNúmero da promoção para remover (ou 'c' para cancelar): ").strip().lower()
                if idx_input == 'c':
                    continue
                    
                idx = int(idx_input) - 1
                p = proMS[idx]
                confirmar = input(f"Tem certeza que deseja excluir '{p['titulo']}'? (s/n): ").lower()
                if confirmar == 's':
                    excluir_promocao(p["id"])
            except (ValueError, IndexError):
                print("\n[ERRO] Seleção inválida.")

        elif op == "0":
            # encerramento limpo do Gateway
            print("\nDesconectando do RabbitMQ... Tchau!")
            os._exit(0)
        
        elif op == "":
            # apenas ignora se o usuário der enter sem digitar nada
            continue
        else:
            print("\n[!] Opção inválida.")


if __name__ == "__main__":
    # inicia o consumidor em uma thread separada para não travar o menu
    t = threading.Thread(target=_consumer_thread, daemon=True)
    t.start()
    
    # aguarda um pouco para que a mensagem de 'pronto' do consumidor apareça antes do menu
    time.sleep(0.6)
    _menu()