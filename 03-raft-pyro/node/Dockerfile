FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir pyro5 serpent msgpack

COPY raft_node.py .

CMD ["python", "-u", "raft_node.py"]