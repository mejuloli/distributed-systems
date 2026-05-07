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