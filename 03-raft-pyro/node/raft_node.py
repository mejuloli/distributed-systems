# implementacao do nó raft usando pyro5
# cada nó pode ser seguidor, candidato ou lider

import Pyro5.api
import Pyro5.server
import threading
import random
import time
import os
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

# configuração

NODE_ID   = int(os.environ["NODE_ID"])          # 1, 2, 3 ou 4
NODE_PORT = int(os.environ["NODE_PORT"])         # 9091 a 9094
NS_HOST   = os.environ.get("NS_HOST", "nameserver")
NS_PORT   = int(os.environ.get("NS_PORT", 9090))

# uris fixos dos nós (objectId@host:porta)
PEERS: dict[int, str] = {
    1: "PYRO:raft.node.1@node1:9091",
    2: "PYRO:raft.node.2@node2:9092",
    3: "PYRO:raft.node.3@node3:9093",
    4: "PYRO:raft.node.4@node4:9094",
}
OBJECT_ID = f"raft.node.{NODE_ID}"

# intervalos de tempo (em segundos)
HEARTBEAT_INTERVAL      = 0.5
ELECTION_TIMEOUT_MIN    = 1.5
ELECTION_TIMEOUT_MAX    = 3.0


class State:
    FOLLOWER  = "follower"
    CANDIDATE = "candidate"
    LEADER    = "leader"


class LogEntry:
    def __init__(self, term: int, command: str):
        self.term    = term
        self.command = command

    def to_dict(self) -> dict:
        return {"term": self.term, "command": self.command}

    @staticmethod
    def from_dict(d: dict) -> "LogEntry":
        return LogEntry(d["term"], d["command"])


@Pyro5.api.expose
class RaftNode:
    # implementação completa do raft exposta como objeto pyro5
    # seções 5.1 a 5.4 do paper (ongaro & ousterhout, 2014)

    def __init__(self):
        self.node_id = NODE_ID
        self.log     = logging.getLogger(f"Node{NODE_ID}")

        # estado persistente (simplificado: mantido em memoria)
        self.current_term = 0
        self.voted_for:   int | None = None
        self.log_entries: list[LogEntry] = []

        # estado volatil
        self.commit_index = -1   # maior indice de entrada confirmada
        self.last_applied = -1   # maior indice aplicado a maquina de estados

        # estado volatil do lider
        self.next_index:  dict[int, int] = {}
        self.match_index: dict[int, int] = {}

        # estado do nó
        self.state           = State.FOLLOWER
        self.leader_id:      int | None = None
        self.votes_received: set[int] = set()

        # comandos aplicados (maquina de estados simulada)
        self.applied_commands: list[str] = []

        # sincronização
        self._lock            = threading.Lock()
        self._election_timer  = None
        self._heartbeat_timer = None

        self.log.info(f"no {NODE_ID} iniciado como seguidor (termo 0)")
        self._reset_election_timer()

    # métodos auxiliares internos

    def _reset_election_timer(self):
        if self._election_timer:
            self._election_timer.cancel()
        timeout = random.uniform(ELECTION_TIMEOUT_MIN, ELECTION_TIMEOUT_MAX)
        self._election_timer = threading.Timer(timeout, self._start_election)
        self._election_timer.daemon = True
        self._election_timer.start()

    def _cancel_election_timer(self):
        if self._election_timer:
            self._election_timer.cancel()
            self._election_timer = None

    def _start_heartbeat_timer(self):
        self._stop_heartbeat_timer()
        self._heartbeat_timer = threading.Timer(HEARTBEAT_INTERVAL, self._send_heartbeats)
        self._heartbeat_timer.daemon = True
        self._heartbeat_timer.start()

    def _stop_heartbeat_timer(self):
        if self._heartbeat_timer:
            self._heartbeat_timer.cancel()
            self._heartbeat_timer = None

    def _become_follower(self, term: int):
        self.state        = State.FOLLOWER
        self.current_term = term
        self.voted_for    = None
        self.leader_id    = None
        self._stop_heartbeat_timer()
        self._reset_election_timer()
        self.log.info(f"-> seguidor  termo={term}")

    def _become_leader(self):
        self.state     = State.LEADER
        self.leader_id = self.node_id
        self._cancel_election_timer()

        # inicializa os índices de controle do líder
        last = len(self.log_entries)
        for pid in PEERS:
            if pid != self.node_id:
                self.next_index[pid]  = last
                self.match_index[pid] = -1

        self.log.info(f"LIDER   termo={self.current_term}")
        self._register_as_leader()
        self._start_heartbeat_timer()

    def _register_as_leader(self):
        # registra (ou sobrescreve) a entrada 'raft.leader' no servidor de nomes
        try:
            ns  = Pyro5.api.locate_ns(host=NS_HOST, port=NS_PORT)
            uri = f"PYRO:{OBJECT_ID}@node{NODE_ID}:{NODE_PORT}"
            ns.register("raft.leader", uri, safe=False)
            self.log.info(f"registrado como 'raft.leader' -> {uri}")
        except Exception as e:
            self.log.warning(f"nao foi possivel registrar como lider no ns: {e}")

    def _last_log_index(self) -> int:
        return len(self.log_entries) - 1

    def _last_log_term(self) -> int:
        if self.log_entries:
            return self.log_entries[-1].term
        return -1

    def _proxy(self, peer_id: int):
        return Pyro5.api.Proxy(PEERS[peer_id])

    # eleição de líder  §5.2

    def _start_election(self):
        with self._lock:
            if self.state == State.LEADER:
                return

            self.current_term  += 1
            self.state          = State.CANDIDATE
            self.voted_for      = self.node_id
            self.votes_received = {self.node_id}
            self.log.info(f"-> candidato  termo={self.current_term}")

        self._reset_election_timer()

        # solicita votos a todos os pares em paralelo
        for peer_id in PEERS:
            if peer_id != self.node_id:
                threading.Thread(
                    target=self._request_vote_from,
                    args=(peer_id,),
                    daemon=True,
                ).start()

    def _request_vote_from(self, peer_id: int):
        try:
            with self._proxy(peer_id) as proxy:
                with self._lock:
                    term           = self.current_term
                    last_log_index = self._last_log_index()
                    last_log_term  = self._last_log_term()

                result = proxy.request_vote(
                    term, self.node_id, last_log_index, last_log_term
                )

            with self._lock:
                if result["term"] > self.current_term:
                    self._become_follower(result["term"])
                    return

                if (
                    self.state == State.CANDIDATE
                    and result["vote_granted"]
                    and result["term"] == self.current_term
                ):
                    self.votes_received.add(peer_id)
                    majority = (len(PEERS) // 2) + 1
                    if len(self.votes_received) >= majority:
                        self._become_leader()

        except Exception as e:
            self.log.debug(f"request_vote para no {peer_id} falhou: {e}")

    # replicação de log  §5.3

    def _send_heartbeats(self):
        if self.state != State.LEADER:
            return
        for peer_id in PEERS:
            if peer_id != self.node_id:
                threading.Thread(
                    target=self._send_append_entries,
                    args=(peer_id,),
                    daemon=True,
                ).start()
        self._start_heartbeat_timer()   # reagenda

    def _send_append_entries(self, peer_id: int):
        with self._lock:
            if self.state != State.LEADER:
                return
            ni         = self.next_index.get(peer_id, len(self.log_entries))
            prev_index = ni - 1
            prev_term  = self.log_entries[prev_index].term if prev_index >= 0 else -1
            entries    = [e.to_dict() for e in self.log_entries[ni:]]
            term       = self.current_term
            commit     = self.commit_index

        try:
            with self._proxy(peer_id) as proxy:
                result = proxy.append_entries(
                    term, self.node_id, prev_index, prev_term, entries, commit
                )

            with self._lock:
                if result["term"] > self.current_term:
                    self._become_follower(result["term"])
                    return

                if result["success"]:
                    new_match = prev_index + len(entries)
                    self.match_index[peer_id] = new_match
                    self.next_index[peer_id]  = new_match + 1
                    self._advance_commit_index()
                else:
                    # decrementa e tenta novamente  §5.3
                    self.next_index[peer_id] = max(0, ni - 1)

        except Exception as e:
            self.log.debug(f"append_entries para no {peer_id} falhou: {e}")

    def _advance_commit_index(self):
        # confirma entradas replicadas na maioria dos servidores  §5.3
        majority = (len(PEERS) // 2) + 1
        last     = len(self.log_entries) - 1

        for n in range(last, self.commit_index, -1):
            if self.log_entries[n].term != self.current_term:
                continue
            count = 1 + sum(
                1 for mid in self.match_index.values() if mid >= n
            )
            if count >= majority:
                self.commit_index = n
                self.log.info(f"confirmado ate o indice {n}")
                self._apply_committed()
                break

    def _apply_committed(self):
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            cmd = self.log_entries[self.last_applied].command
            self.applied_commands.append(cmd)
            self.log.info(f"aplicado [{self.last_applied}] {cmd!r}")

    # rpc pyro5 - request_vote  §5.2

    def request_vote(
        self,
        term: int,
        candidate_id: int,
        last_log_index: int,
        last_log_term: int,
    ) -> dict:
        with self._lock:
            if term > self.current_term:
                self._become_follower(term)

            vote_granted = False

            if term < self.current_term:
                pass  # termo obsoleto, nega o voto
            elif self.voted_for in (None, candidate_id):
                # o log do candidato deve ser atualizado o máximo possível §5.4
                my_last_term  = self._last_log_term()
                my_last_index = self._last_log_index()

                log_ok = (
                    last_log_term > my_last_term
                    or (last_log_term == my_last_term and last_log_index >= my_last_index)
                )
                if log_ok:
                    vote_granted   = True
                    self.voted_for = candidate_id
                    self._reset_election_timer()
                    self.log.info(f"voto concedido ao no {candidate_id} (termo {term})")

            return {"term": self.current_term, "vote_granted": vote_granted}

    # rpc pyro5 - append_entries  §5.3

    def append_entries(
        self,
        term: int,
        leader_id: int,
        prev_log_index: int,
        prev_log_term: int,
        entries: list[dict],
        leader_commit: int,
    ) -> dict:
        with self._lock:
            if term > self.current_term:
                self._become_follower(term)

            if term < self.current_term:
                return {"term": self.current_term, "success": False}

            # mensagem válida do líder, reseta o temporizador de eleição
            self.state     = State.FOLLOWER
            self.leader_id = leader_id
            self._reset_election_timer()

            # verificação de consistência  §5.3
            if prev_log_index >= 0:
                if len(self.log_entries) <= prev_log_index:
                    return {"term": self.current_term, "success": False}
                if self.log_entries[prev_log_index].term != prev_log_term:
                    # remove entrada conflitante e todas as seguintes  §5.3
                    self.log_entries = self.log_entries[:prev_log_index]
                    return {"term": self.current_term, "success": False}

            # adiciona novas entradas
            for i, ed in enumerate(entries):
                idx = prev_log_index + 1 + i
                if idx < len(self.log_entries):
                    if self.log_entries[idx].term != ed["term"]:
                        self.log_entries = self.log_entries[:idx]
                        self.log_entries.append(LogEntry.from_dict(ed))
                else:
                    self.log_entries.append(LogEntry.from_dict(ed))

            # avanca o índice de commit  §5.3
            if leader_commit > self.commit_index:
                self.commit_index = min(leader_commit, len(self.log_entries) - 1)
                self._apply_committed()

            return {"term": self.current_term, "success": True}

    # rpc pyro5 - interface com o cliente

    def submit_command(self, command: str) -> dict:
        # recebe um comando do cliente. apenas o líder aceita.
        # retorna o uri do líder caso o nó não seja o líder
        with self._lock:
            if self.state != State.LEADER:
                leader_uri = PEERS.get(self.leader_id) if self.leader_id else None
                return {
                    "success": False,
                    "error":   "not_leader",
                    "leader":  leader_uri,
                }
            entry = LogEntry(self.current_term, command)
            self.log_entries.append(entry)
            idx = len(self.log_entries) - 1
            self.log.info(f"entrada adicionada [{idx}] {command!r} (termo {self.current_term})")

        # replica imediatamente (o heartbeat tambem garante a replicação)
        for peer_id in PEERS:
            if peer_id != self.node_id:
                threading.Thread(
                    target=self._send_append_entries,
                    args=(peer_id,),
                    daemon=True,
                ).start()

        return {"success": True, "index": idx}

    def get_status(self) -> dict:
        # retorna o estado atual do nó (para depuração)
        with self._lock:
            return {
                "node_id":          self.node_id,
                "state":            self.state,
                "current_term":     self.current_term,
                "leader_id":        self.leader_id,
                "log_length":       len(self.log_entries),
                "commit_index":     self.commit_index,
                "last_applied":     self.last_applied,
                "applied_commands": list(self.applied_commands),
            }


# ponto de entrada

def main():
    # aguarda o servidor de nomes subir
    time.sleep(3)

    daemon = Pyro5.server.Daemon(host=f"node{NODE_ID}", port=NODE_PORT)
    node   = RaftNode()
    uri    = daemon.register(node, objectId=OBJECT_ID)

    # registra no servidor de nomes
    connected = False
    for attempt in range(10):
        try:
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