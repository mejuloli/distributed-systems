# raft com pyro5

implementacao do algoritmo de consenso raft para replicacao de log entre 4 processos comunicando via pyro5.

## dependencias

- docker
- docker compose

> nao e necessario instalar python ou pyro5 localmente para rodar o projeto.
> as dependencias ficam todas dentro dos containers.

### opcional: instalar pyro5 localmente (so para silenciar avisos do vs code)

```bash
sudo apt install python3.12-venv -y
python3 -m venv .venv
.venv/bin/pip install pyro5 serpent msgpack
```

depois, no vs code: `ctrl+shift+p` → `python: select interpreter` → escolha o `.venv`.

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

o Raft é projetado para sobreviver a falhas. Para poder testar, primeiro deixe rodando o docker em paralelo pressionando `d` no console do `docker compose up` em seguida execute:
```bash
docker compose logs -f
```
*dica: o comando logs -f reconecta automaticamente se um nó for reiniciado.*

teste o cluster da seguinte forma:

1. **derrube o líder:**
descubra quem é o líder atual (via logs ou `status`) e pare o contêiner:
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

## conceitos operacionais

### termo (term)

o "tempo lógico" do sistema. Funciona como um número de mandato. Impede que líderes antigos (que ficaram isolados da rede) consigam enviar comandos obsoletos quando voltarem.

### log

o caderno de intenções de cada nó. O simples fato de um comando estar no log **não significa que ele foi executado**. Ele é apenas uma proposta pendente de confirmação.

### confirmado (commit index)

o "carimbo de aprovado". Uma entrada de log só é confirmada quando o líder recebe confirmação da maioria (quórum). Somente após o commit é que a Máquina de Estados executa o comando (ex: altera o valor de `x`).

---

## como funciona

### eleicao (§5.2 do paper raft)

- cada no usa um timeout aleatorio entre 1,5 e 3 segundos
- ao expirar o timeout sem receber heartbeat, o no vira candidato e solicita votos
- um candidato so vence se seu log estiver tao atualizado quanto o do votante
- o lider eleito se registra no servidor de nomes como `raft.leader`

### replicacao (§5.3)

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

---

## configurações técnicas

* **Election Timeout:** aleatório entre 1.5s e 3.0s (evita colisões de candidatos).
* **Heartbeat:** 0.5s (enviado pelo líder para manter autoridade).
* **Rede:** Docker Bridge (`raft-net`) com DNS interno para resolução de nomes dos nós.

---

## referências

- [raft paper](https://raft.github.io/raft.pdf)
- [visualizacao interativa do raft](https://thesecretlivesofdata.com/raft/)
- [documentacao pyro5](https://pyro5.readthedocs.io/en/latest/intro.html)