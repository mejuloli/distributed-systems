
import Pyro5.api
import Pyro5.server
import time
from raft_core import RaftNode
from config import NODE_ID, NODE_PORT, NS_HOST, NS_PORT, OBJECT_ID

def main():
    time.sleep(3)

    daemon = Pyro5.server.Daemon(host=f"node{NODE_ID}", port=NODE_PORT)
    node   = RaftNode()
    uri    = daemon.register(node, objectId=OBJECT_ID)

    # registra no servidor de nomes
    connected = False
    for attempt in range(10):
        try:
            # registramos no servidor de nomes para que os clientes possam nos encontrar para o status
            ns = Pyro5.api.locate_ns(host=NS_HOST, port=NS_PORT)
            ns.register(OBJECT_ID, uri)
            print(f"[no{NODE_ID}] registrado: {uri}", flush=True)
            connected = True
            break
        except Exception as e:
            print(f"[no{NODE_ID}] ns indisponivel ({e}), tentativa {attempt+1}/10...", flush=True)
            time.sleep(2)

    if not connected:
        print(f"[no{NODE_ID}] nao foi possivel conectar ao servidor de nomes. encerrando.", flush=True)
        sys.exit(1)

    print(f"[no{NODE_ID}] escutando em {uri}", flush=True)
    daemon.requestLoop()


if __name__ == "__main__":
    main()