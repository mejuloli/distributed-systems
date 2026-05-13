
import Pyro5.api
import os
import time
import argparse

NS_HOST = os.environ.get("NS_HOST", "nameserver")
NS_PORT = int(os.environ.get("NS_PORT", 9090))

def get_leader_uri() -> str | None:
    # consulta o servidor de nomes para descobrir o lider atual
    try:
        ns  = Pyro5.api.locate_ns(host=NS_HOST, port=NS_PORT)
        uri = ns.lookup("raft.leader")
        return str(uri)
    except Exception:
        return None


def send_command(command: str, retries: int = 5) -> bool:
    # envia um comando ao lider
    # se redirecionado, segue o redirecionamento automaticamente
    leader_uri = get_leader_uri()

    for _ in range(retries):
        if not leader_uri:
            print("aguardando lider ser eleito...")
            time.sleep(2)
            leader_uri = get_leader_uri()
            continue

        try:
            with Pyro5.api.Proxy(leader_uri) as proxy:
                result = proxy.submit_command(command)

            if result["success"]:
                print(f"confirmado no indice {result['index']}")
                return True
            elif result["error"] == "not_leader":
                # segue o redirecionamento
                redirect = result.get("leader")
                print(f"redirecionando para o lider: {redirect}")
                leader_uri = redirect
            else:
                print(f"erro: {result}")
                return False

        except Exception as e:
            print(f"rpc falhou ({e}), tentando novamente...")
            leader_uri = get_leader_uri()
            time.sleep(1)

    print("nao foi possivel entregar o comando apos as tentativas.")
    return False


def print_status():
    print("\n-- status do cluster --")
    for nid in range(1, 5):
        # usamos PYRONAME para o proxy resolver o URI do nó, que deve estar registrado no servidor de nomes
        logical_uri = f"PYRONAME:raft.node.{nid}"
        try:
            with Pyro5.api.Proxy(logical_uri) as proxy:
                s = proxy.get_status()
                
            role = {"leader": "lider", "candidate": "candidato", "follower": "seguidor"}[s["state"]]
            print(
                f"  no{s['node_id']}  "
                f"estado={role:<10}  "
                f"termo={s['current_term']:>3}  "
                f"log={s['log_length']:>3}  "
                f"confirmado={s['commit_index']:>3}"
            )
        except Exception:
            print(f"  no{nid}  (inalcancavel)")
    print("-----------------------\n")


def demo_mode():
    # envia um conjunto de comandos de demonstracao automaticamente
    commands = [
        "SET x=10",
        "SET y=20",
        "SET z=x+y",
        "DEL x",
        "SET name=raft-demo",
        "PING",
    ]
    print("modo demo - enviando comandos automaticamente\n")
    time.sleep(4)

    for cmd in commands:
        print(f"> {cmd}")
        send_command(cmd)
        time.sleep(1)

    print_status()


def interactive_mode():
    print("cliente raft - digite um comando, 'status' ou 'sair'")
    while True:
        try:
            line = input("raft> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            continue
        if line in ("sair", "quit", "exit", "q"):
            break
        if line == "status":
            print_status()
        else:
            send_command(line)


def main():
    parser = argparse.ArgumentParser(description="cliente raft pyro5")
    parser.add_argument(
        "--demo", action="store_true", help="executa comandos de demonstracao"
    )
    args = parser.parse_args()

    if args.demo:
        demo_mode()
    else:
        interactive_mode()


if __name__ == "__main__":
    main()