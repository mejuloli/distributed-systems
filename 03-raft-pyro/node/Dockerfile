FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir pyro5 serpent msgpack

COPY *.py ./

CMD ["python", "-u", "run_node.py"]