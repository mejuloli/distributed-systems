# raft com pyro5

implementacao do algoritmo de consenso raft para replicacao de log entre 4 processos comunicando via pyro5.

## como rodar

```bash
docker compose up --build
```

## testar falha do lider

```bash
# derruba o lider
docker stop <node_lider>

# acompanha a nova eleicao
docker compose logs -f
```

## cliente interativo

```bash
docker compose run --rm client python client.py
```

## estrutura

```
03-raft-pyro/
├── docker-compose.yml
├── node/
│   ├── Dockerfile
│   └── raft_node.py
└── client/
    ├── Dockerfile
    └── client.py
```