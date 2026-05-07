# config.py
import os

# Configurações do Nó (Falha rápida se não existirem)
NODE_ID   = int(os.environ["NODE_ID"])          # 1, 2, 3 ou 4
NODE_PORT = int(os.environ["NODE_PORT"])        # 9091 a 9094

# Configurações do Name Server (Usa fallback/default se não existir)
NS_HOST   = os.environ.get("NS_HOST", "nameserver")
NS_PORT   = int(os.environ.get("NS_PORT", 9090))

# Computado no momento da inicialização
OBJECT_ID = f"raft.node.{NODE_ID}"

# URIs fixos dos pares na rede Docker (objectId@host:porta)
PEERS: dict[int, str] = {
    1: "PYRO:raft.node.1@node1:9091",
    2: "PYRO:raft.node.2@node2:9092",
    3: "PYRO:raft.node.3@node3:9093",
    4: "PYRO:raft.node.4@node4:9094",
}

# Intervalos de tempo (em segundos)
HEARTBEAT_INTERVAL      = 0.5
ELECTION_TIMEOUT_MIN    = 1.5
ELECTION_TIMEOUT_MAX    = 3.0