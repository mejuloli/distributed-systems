# Raft com Pyro5

Implementação do algoritmo de consenso Raft para replicacao de log entre 4 processos comunicando via Pyro5.

## Dependências

- Docker
- Docker compose

> Não é necessário instalar python ou Pyro5 localmente para rodar o projeto.
> As dependencias ficam todas dentro dos containers.

---

## Estrutura

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

## Como rodar

### Terminal 1 — sobe o Cluster

```bash
docker compose up --build
```

Isso inicializará:
- 1 servidor de nomes Pyro5 (nameserver)
- 4 nos Raft (node1 a node4)
- 1 cliente em modo demo (envia comandos automaticamente)

Aguarde os nós se registrarem e um líder ser eleito. Você verá mensagens como:

```
node3 | LIDER   termo=1
node1 | voto concedido ao nó 3 (termo 1)
```

### Terminal 2 — cliente interativo

```bash
docker compose run --rm client python client.py
```

Comandos disponiveis no prompt `raft>`:

```
raft> status          # exibe estado de todos os nos
raft> SET x=10        # envia comando ao lider
raft> DEL x           # envia comando ao lider
raft> PING            # envia comando ao lider
raft> sair            # encerra o cliente
```

---

## Engenharia de caos (testando resiliência)

Para poder testar o comportamento quando nodos caem, primeiro deixe rodando o docker em paralelo pressionando `d` no console do `docker compose up` e em seguida execute:
```bash
docker compose logs -f
```
*Dessa forma o log irá capturar os nodos reiniciados*

1. **Derrube o líder:**
Descubra quem é o líder atual (via logs ou `status`) e pare o serviço do contêiner:
```bash
docker stop node3
```
*Observe os outros nós atingirem o timeout e elegerem um novo líder.*

2. **Envie comandos sem o nó antigo:**
o sistema continuará operando normalmente (quórum de 3 nós).

3. **Reintegre o nó:**
```bash
docker start node3
```
*O nó voltará, perceberá que seu log está atrasado e usará a otimização de **Log Matching** para sincronizar em lote com o novo líder.*

---

## Encerrar tudo

```bash
docker compose down
```

---

## Como funciona

### Eleição

- Cada nó usa um timeout aleatorio
- Ao expirar o timeout sem receber heartbeat, o nó vira candidato e solicita votos
- Um candidato só vence se seu log estiver tão atualizado quanto o do votante
- O líder eleito se registra no servidor de nomes como `raft.leader`

### Reaplicação

- O cliente descobre o lídder consultando o servidor de nomes
- O líder recebe o comando, anexa ao seu log e envia `AppendEntries` aos seguidores
- A entrada é confirmada (committed) quando a maioria dos nós confirma
- O líder envia heartbeats periódicos para evitar novas eleições

### URIs fixos dos nós

```
PYRO:raft.node.1@node1:9091
PYRO:raft.node.2@node2:9092
PYRO:raft.node.3@node3:9093
PYRO:raft.node.4@node4:9094
```

Os hostnames fixos são garantidos pelo docker compose, que atribui nomes de container determinísticos.