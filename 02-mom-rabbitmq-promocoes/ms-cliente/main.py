"""
Cliente Universal de Promoções
──────────────────────────────
Permite instanciar clientes com interesses predefinidos (Presets A e B)
ou criar um cliente customizado dinamicamente.
"""
import sys
import os
import json
import uuid
# garante que o python encontre a pasta 'shared'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.rabbitmq_utils import get_connection, declare_exchange, EXCHANGE_NAME, payload_to_bytes
from shared.crypto_utils import verify_event

# Chaves que sabemos que vêm direto do produtor e precisam de validação de assinatura
SIGNED_KEYS = {"promocao.destaque"}


class ClientePromocao:
    def __init__(self, nome: str, categorias: list[str], receber_destaques: bool = True):
        self.nome = nome
        # Cria um nome de fila único para evitar conflitos se abrir vários clientes iguais
        self.queue_name = f"Fila_{self.nome.replace(' ', '_')}_{str(uuid.uuid4())[:4]}"
        
        # Constrói as routing keys baseadas nas categorias informadas
        self.routing_keys = [f"promocao.{cat.lower().strip()}" for cat in categorias]
        if receber_destaques:
            self.routing_keys.append("promocao.destaque")

    def _on_notificacao(self, ch, method, props, body):
        rk = method.routing_key

        try:
            data = json.loads(body)
        except Exception:
            print(f"[{self.nome}] ✗ Mensagem malformada em '{rk}' - descartada.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # Tratamento rotas que são assinadas
        if rk in SIGNED_KEYS:
            # Assinada (Hot Deal)
            if "payload" not in data or "signature" not in data:
                print(f"[{self.nome}] ✗ Envelope ausente em '{rk}' - descartado.")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
            payload = data["payload"]
            signature = data["signature"]

            #? Cliente valida chave? Acredito que não, mas por já que tem a assinatura vou validar mesmo assim
            if not verify_event(payload_to_bytes(payload), signature, "ranking"):
                print(f"[{self.nome}] Assinatura INVÁLIDA em '{rk}' - descartado.")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return
        else:
            # Mensagens de categoria chegam raw do MS Notificação
            payload = data

        # Exibição
        print(f"\n{'═'*55}")
        if payload.get("tipo") == "hot_deal" or payload.get("label") or payload.get("hot_deal"):
            print(f"[{self.nome}] 🔥 HOT DEAL - via '{rk}'")
            print(f"  Título    : {payload.get('titulo', '?')}")
            print(f"  Categoria : {payload.get('categoria', '?')}")
            print(f"  Preço     : R${payload.get('preco', 0):.2f}")
            print(f"  Descrição : {payload.get('descricao', '')}")
        else:
            print(f"[{self.nome}] 🔔 Nova promoção - via '{rk}'")
            print(f"  Título    : {payload.get('titulo', '?')}")
            print(f"  Categoria : {payload.get('categoria', '?')}")
            print(f"  Preço     : R${payload.get('preco', 0):.2f}")
            print(f"  Descrição : {payload.get('descricao', '')}")
        print(f"{'═'*55}")

        ch.basic_ack(delivery_tag=method.delivery_tag)

    def run(self):
        try:
            self.conn = get_connection()
            self.ch = self.conn.channel()
            declare_exchange(self.ch)

            # auto_delete=True garante que a fila some do RabbitMQ quando o cliente fechar
            self.ch.queue_declare(queue=self.queue_name, durable=False, auto_delete=True)
            
            for rk in self.routing_keys:
                self.ch.queue_bind(exchange=EXCHANGE_NAME, queue=self.queue_name, routing_key=rk)

            self.ch.basic_consume(queue=self.queue_name, on_message_callback=self._on_notificacao)
            
            print(f"\n[{self.nome}] ✔ Conectado com sucesso!")
            print(f"[{self.nome}] Escutando as rotas: {', '.join(self.routing_keys)}")
            print(f"[{self.nome}] Aguardando notificações... (Pressione Ctrl+C para sair)")
            
            self.ch.start_consuming()
            
        except KeyboardInterrupt:
            print(f"\n[{self.nome}] Interrompido pelo usuário (Ctrl+C). Encerrando...")
            if hasattr(self, 'conn') and self.conn.is_open:
                self.conn.close()

# ──────────────────────────────────────────────────────────────
# Menu de Inicialização
# ──────────────────────────────────────────────────────────────
def main():
    print("╔══════════════════════════════════════════╗")
    print("║        INICIADOR DE CLIENTES             ║")
    print("╠══════════════════════════════════════════╣")
    print("║  1. Preset: Cliente A (Livros, Jogos)    ║")
    print("║  2. Preset: Cliente B (Eletrônicos)      ║")
    print("║  3. Criar Cliente Customizado            ║")
    print("╚══════════════════════════════════════════╝")
    
    op = input("Escolha uma opção > ").strip()

    if op == "1":
        cliente = ClientePromocao(nome="Cliente A", categorias=["livros", "jogos"])
        cliente.run()
        
    elif op == "2":
        cliente = ClientePromocao(nome="Cliente B", categorias=["eletronicos"])
        cliente.run()
        
    elif op == "3":
        print("\n--- CONFIGURAÇÃO CUSTOMIZADA ---")
        nome = input("Digite o nome do cliente: ").strip() or "Cliente_Custom"
        cats_input = input("Digite as categorias de interesse separadas por vírgula (ex: roupas, carros, livros): ")
        
        # Limpa e formata a lista de categorias
        categorias = [c.strip() for c in cats_input.split(",") if c.strip()]
        
        destaque_input = input("Deseja receber notificações de Hot Deals gerais? (s/n): ").strip().lower()
        receber_destaques = destaque_input == 's'
        
        cliente = ClientePromocao(nome=nome, categorias=categorias, receber_destaques=receber_destaques)
        cliente.run()
        
    else:
        print("Opção inválida. Encerrando.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Cliente] Interrompido pelo usuário (Ctrl+C). Encerrando...")