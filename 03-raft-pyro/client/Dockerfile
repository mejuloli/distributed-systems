FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir pyro5 serpent msgpack

COPY client.py .

CMD ["python", "-u", "client.py", "--demo"]