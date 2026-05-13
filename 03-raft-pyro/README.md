# raft com pyro5

implementacao do algoritmo de consenso raft para replicacao de log entre 4 processos comunicando via pyro5.

## dependencias

- docker
- docker compose

> nao e necessario instalar python ou pyro5 localmente para rodar o projeto.
> as dependencias ficam todas dentro dos containers.

---

## estrutura

```
03-raft-pyro/
├── docker-compose.yml
├── node/
│   ├── config.py
│   ├── Dockerfile
│   ├── models.py
│   ├── raft_core.py
│   └── raft_run.py
└── client/
    ├── Dockerfile
    └── client.py
```

---

## como rodar

### terminal 1 — sobe o cluster

```bash
docker compose up --build
```

isso inicializa:
- 1 servidor de nomes pyro5 (nameserver)
- 4 nos raft (node1 a node4)
- 1 cliente em modo demo (envia comandos automaticamente)

aguarde os nos se registrarem e um lider ser eleito. voce vera mensagens como:

```
node3 | LIDER   termo=1
node1 | voto concedido ao no 3 (termo 1)
```

### terminal 2 — cliente interativo

```bash
docker compose run --rm client python client.py
```

comandos disponiveis no prompt `raft>`:

```
raft> status          # exibe estado de todos os nos
raft> SET x=10        # envia comando ao lider
raft> DEL x           # envia comando ao lider
raft> PING            # envia comando ao lider
raft> sair            # encerra o cliente
```

---

## engenharia de caos (testando resiliência)

para poder testar o comportamento quando nodos caem, primeiro deixe rodando o docker em paralelo pressionando `d` no console do `docker compose up` em seguida execute:
```bash
docker compose logs -f
```
*dessa forma o log irá capturar os nodos reiniciados*

1. **derrube o líder:**
descubra quem é o líder atual (via logs ou `status`) e pare o serviço do contêiner:
```bash
docker stop node3
```
*observe os outros nós atingirem o timeout e elegerem um novo líder.*

2. **envie comandos sem o nó antigo:**
o sistema continuará operando normalmente (quórum de 3 nós).

3. **reintegre o nó:**
```bash
docker start node3
```
*O nó voltará, perceberá que seu log está atrasado e usará a otimização de **Log Matching** para sincronizar em lote com o novo líder.*

---

## encerrar tudo

```bash
docker compose down
```

---

## como funciona

### eleicao

- cada no usa um timeout aleatorio
- ao expirar o timeout sem receber heartbeat, o no vira candidato e solicita votos
- um candidato so vence se seu log estiver tao atualizado quanto o do votante
- o lider eleito se registra no servidor de nomes como `raft.leader`

### replicacao

- o cliente descobre o lider consultando o servidor de nomes
- o lider recebe o comando, anexa ao seu log e envia `AppendEntries` aos seguidores
- a entrada e confirmada (committed) quando a maioria dos nos confirma
- o lider envia heartbeats periodicos para evitar novas eleicoes

### uris fixos dos nos

```
PYRO:raft.node.1@node1:9091
PYRO:raft.node.2@node2:9092
PYRO:raft.node.3@node3:9093
PYRO:raft.node.4@node4:9094
```

os hostnames fixos sao garantidos pelo docker compose, que atribui nomes de container deterministicos.