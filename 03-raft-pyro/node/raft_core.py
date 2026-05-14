import Pyro5.api
import Pyro5.errors
import threading
import random
import logging
import time
from models import State, LogEntry
from config import (COMMAND_TIMEOUT, NODE_ID, PEERS, NS_HOST, NS_PORT, HEARTBEAT_INTERVAL, ELECTION_TIMEOUT_MIN, ELECTION_TIMEOUT_MAX, RPC_TIMEOUT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

# implementação do nodo do algoritmo Raft usando Pyro5 para comunicação remota
@Pyro5.api.expose
class RaftNode:
    def __init__(self):
        self.node_id = NODE_ID
        self.log     = logging.getLogger(f"Node{NODE_ID}")

        # estado
        self.current_term = 0
        self.voted_for:   int | None = None
        self.log_entries: list[LogEntry] = []
        self.commit_index = -1 
        self.last_applied = -1 

        # estado do lider
        self.next_index:  dict[int, int] = {}
        self.match_index: dict[int, int] = {}

        # estado do nó
        self.state           = State.FOLLOWER
        self.leader_id:      int | None = None
        self.votes_received: set[int] = set()

        # comandos aplicados
        self.applied_commands: list[str] = []

        # sincronização
        self._lock            = threading.Lock()
        self._election_timer  = None
        self._heartbeat_timer = None

        self.log.info(f"no {NODE_ID} iniciado como seguidor (termo 0)")
        self._reset_election_timer()

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
        # registra/sobrescreve a entrada 'raft.leader' no servidor de nomes
        try:
            ns  = Pyro5.api.locate_ns(host=NS_HOST, port=NS_PORT)
            uri = PEERS[NODE_ID]
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

                proxy._pyroTimeout = RPC_TIMEOUT
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

        except Pyro5.errors.CommunicationError as e:
            self.log.warning(f"request_vote Rede indisponivel para no {peer_id} (Timeout/Queda)")
        except Exception as e:
            self.log.error(f"request_vote Falha critica ao se comunicar com {peer_id}: {e}")

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
        self._start_heartbeat_timer()

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
                proxy._pyroTimeout = RPC_TIMEOUT
                result = proxy.append_entries(
                    term, self.node_id, prev_index, prev_term, entries, commit
                )

            with self._lock:
                # se o termo do seguidor for maior, o líder deve se tornar seguidor imediatamente
                if result["term"] > self.current_term:
                    self._become_follower(result["term"])
                    return

                if result["success"]:
                    # atualiza os índices de controle do líder
                    new_match = prev_index + len(entries)
                    self.match_index[peer_id] = new_match
                    self.next_index[peer_id]  = new_match + 1
                    self._advance_commit_index()
                else:
                    # falha de consistência, pega o último índice do nodo e envia o restante
                    follower_log_len = result.get("log_len", max(0, ni - 1))
                    self.next_index[peer_id] = min(max(0, ni - 1), follower_log_len)

        except Pyro5.errors.CommunicationError as e:
            self.log.warning(f"append_entries Rede indisponivel para no {peer_id} (Timeout/Queda)")
        except Exception as e:
            self.log.error(f"append_entries Falha critica ao se comunicar com {peer_id}: {e}")

    def _advance_commit_index(self):
        # confirma entradas replicadas na maioria dos servidores
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

    def request_vote(
        self,
        term: int,
        candidate_id: int,
        last_log_index: int,
        last_log_term: int,
    ) -> dict:
        with self._lock:
            # se o termo do candidato for maior, o seguidor deve aceitar o candidato e se tornar seguidor imediatamente
            if term > self.current_term:
                self._become_follower(term)

            vote_granted = False

            if term < self.current_term:
                # voto negado por termo desatualizado
                pass 
            elif self.voted_for in (None, candidate_id):
                # o log do candidato deve ser atualizado o máximo possível
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
            # se o termo do líder for maior, o seguidor deve aceitar o líder e se tornar seguidor imediatamente
            if term > self.current_term:
                self._become_follower(term)

            # se o termo do líder for menor, rejeita a mensagem
            if term < self.current_term:
                return {"term": self.current_term, "success": False, "log_len": len(self.log_entries)}

            # mensagem válida do líder, reseta o temporizador de eleição
            self.state     = State.FOLLOWER
            self.leader_id = leader_id
            self._reset_election_timer()

            # verificação de consistência
            if prev_log_index >= 0:
                if len(self.log_entries) <= prev_log_index:
                    return {"term": self.current_term, "success": False, "log_len": len(self.log_entries)}
                if self.log_entries[prev_log_index].term != prev_log_term:
                    # remove entrada conflitante e todas as seguintes
                    self.log_entries = self.log_entries[:prev_log_index]
                    return {"term": self.current_term, "success": False, "log_len": len(self.log_entries)}

            # adiciona novas entradas
            for i, ed in enumerate(entries):
                idx = prev_log_index + 1 + i
                if idx < len(self.log_entries):
                    if self.log_entries[idx].term != ed["term"]:
                        self.log_entries = self.log_entries[:idx]
                        self.log_entries.append(LogEntry.from_dict(ed))
                else:
                    self.log_entries.append(LogEntry.from_dict(ed))

            # avanca o índice de commit
            if leader_commit > self.commit_index:
                self.commit_index = min(leader_commit, len(self.log_entries) - 1)
                self._apply_committed()

            return {"term": self.current_term, "success": True}

    def submit_command(self, command: str) -> dict:
        # recebe um comando do cliente. apenas o líder aceita.
        with self._lock:
            if self.state != State.LEADER:
                # se não for líder, retorna o URI do líder para o cliente redirecionar a requisição
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

        # replica imediatamente
        for peer_id in PEERS:
            if peer_id != self.node_id:
                threading.Thread(
                    target=self._send_append_entries,
                    args=(peer_id,),
                    daemon=True,
                ).start()

        # espera até que a entrada seja confirmada (replicada na maioria dos nós)
        start_time = time.time()
        while True:
            with self._lock:
                if self.state != State.LEADER:
                    return {"success": False, "error": "lost_leadership"}
                if self.commit_index >= idx:
                    return {"success": True, "index": idx}
            
            if time.time() - start_time > COMMAND_TIMEOUT:
                return {
                    "success": False, 
                    "error": "timeout", 
                    "message": "quórum não alcançado (nós insuficientes)"
                }
            time.sleep(0.3)

    def get_status(self) -> dict:
        # retorna o estado atual do nó
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