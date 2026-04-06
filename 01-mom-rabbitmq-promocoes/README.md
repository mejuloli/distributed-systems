# 🛒 Sistema de Promoções Distribuído

Trabalho 1 — Sistemas Distribuídos | UTFPR  
Disciplina: Microsserviços, Mensageria (RabbitMQ), Criptografia Assimétrica

## 📐 Arquitetura

```
MS Gateway  ──publishes──▶  promocao.recebida  ──▶  MS Promoção
MS Gateway  ──publishes──▶  promocao.voto      ──▶  MS Ranking
MS Gateway  ◀──consumes──   promocao.publicada

MS Promoção ──publishes──▶  promocao.publicada ──▶  MS Gateway
                                               ──▶  MS Notificação

MS Ranking  ◀──consumes──   promocao.voto
MS Ranking  ──publishes──▶  promocao.destaque  ──▶  MS Notificação
                                               ──▶  Clientes (inscritos em destaque)

MS Notificação ──publishes──▶ promocao.<categoria> ──▶ Clientes (por categoria)
               (inclui mensagens com "hot deal" quando a promoção for destacada)
```

> **Fluxo do Hot Deal:** O MS Ranking publica `promocao.destaque` diretamente no broker. Os clientes inscritos nessa routing key recebem o evento diretamente do MS Ranking (com assinatura). Em paralelo, o MS Notificação consome esse mesmo evento e publica uma notificação adicional em `promocao.<categoria>` (com a palavra "hot deal" no payload), para que clientes que seguem apenas a categoria também sejam alertados.

## 🔐 Criptografia Assimétrica

Cada microsserviço produtor (Gateway, Promoção, Ranking) possui um par de chaves RSA.

- **Produtor**: gera um hash SHA-256 do payload e assina com sua chave privada. A assinatura é incluída no campo `signature` do envelope do evento.
- **Consumidor**: verifica a assinatura com a chave pública do produtor esperado antes de qualquer processamento.

### Política de Descarte

Todo consumidor aplica a seguinte regra como **guardião da mensagem**:

```
se verify_event(payload, signature, produtor) == False:
    log("Assinatura INVÁLIDA — descartado")
    basic_ack()   # retira da fila sem processar
    return        # para execução imediatamente
```

| Consumidor       | Valida assinatura de |
|------------------|----------------------|
| MS Promoção      | `gateway`            |
| MS Ranking       | `gateway`            |
| MS Notificação   | `promocao` ou `ranking` (conforme routing key) |
| MS Gateway       | `promocao`           |
| Clientes (A, B…) | `ranking` (somente para `promocao.destaque`) |

> Mensagens publicadas pelo MS Notificação para `promocao.<categoria>` chegam aos clientes sem assinatura (redistribuidor sem chave própria). Essas mensagens são exibidas diretamente.

## 🐇 Exchange RabbitMQ

O sistema usa uma única exchange do tipo **`topic`** chamada `Promocoes`.

Exchange topic foi escolhida porque as routing keys seguem o padrão hierárquico `promocao.<subtipo>`, permitindo que consumidores usem wildcards de binding (`*`, `#`) se necessário.

Cada processo (microsserviço ou cliente) **cria sua própria fila** e faz o bind às routing keys de interesse:

```
Fila_Gateway     → bind: promocao.publicada
Fila_Promocao    → bind: promocao.recebida
Fila_Ranking     → bind: promocao.voto
Fila_Notificacao → bind: promocao.publicada, promocao.destaque
Fila_Cliente_A   → bind: promocao.livro, promocao.jogo, promocao.destaque
Fila_Cliente_B   → bind: promocao.eletronico, promocao.destaque
```

## 🗂️ Eventos (Routing Keys)

| Routing Key            | Produtor        | Consumidores                                     |
|------------------------|-----------------|--------------------------------------------------|
| `promocao.recebida`    | MS Gateway      | MS Promoção                                      |
| `promocao.voto`        | MS Gateway      | MS Ranking                                       |
| `promocao.publicada`   | MS Promoção     | MS Gateway, MS Notificação                       |
| `promocao.destaque`    | MS Ranking      | MS Notificação, Clientes (inscritos em destaque) |
| `promocao.<categoria>` | MS Notificação  | Clientes (inscritos na categoria)                |

## 🏆 Hot Deal

Uma promoção vira **hot deal** quando `score = votos_positivos − votos_negativos ≥ 5`.

O MS Ranking promove a promoção **uma única vez** (flag `hot_deal` garante idempotência) e publica `promocao.destaque`. O MS Notificação então reencaminha a notificação para `promocao.<categoria>` contendo `"label": "🔥 HOT DEAL"` no payload.

## 🚀 Como Rodar

### 1. Subir o RabbitMQ via Docker

```bash
cd docker
docker-compose up -d
# Management UI: http://localhost:15672  (guest / guest)
```

### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

### 3. Gerar os pares de chaves RSA (uma única vez)

```bash
python keys/generate_keys.py
```

### 4. Iniciar os microsserviços (cada um em um terminal separado)

```bash
python ms-promocao/main.py
python ms-ranking/main.py
python ms-notificacao/main.py
python ms-gateway/main.py        # interface principal com o usuário
python ms-cliente/cliente_a.py   # interesses: livros, jogos, destaque
python ms-cliente/cliente_b.py   # interesses: eletronicos, destaque
```

## 📦 Estrutura de Pastas

```
promocoes-system/
├── docker/
│   └── docker-compose.yml
├── keys/
│   ├── generate_keys.py
│   ├── gateway_private.pem      # gerado
│   ├── gateway_public.pem       # gerado
│   ├── promocao_private.pem     # gerado
│   ├── promocao_public.pem      # gerado
│   ├── ranking_private.pem      # gerado
│   └── ranking_public.pem       # gerado
├── ms-gateway/
│   └── main.py
├── ms-promocao/
│   └── main.py
├── ms-ranking/
│   └── main.py
├── ms-notificacao/
│   └── main.py
├── ms-cliente/
│   ├── cliente_a.py
│   └── cliente_b.py
├── shared/
│   ├── crypto_utils.py          # sign_event / verify_event (RSA PKCS1v15 + SHA256)
│   └── rabbitmq_utils.py        # conexão, declare_exchange, publish_event
├── requirements.txt
└── README.md
```

---
UTFPR | Profa. Ana Cristina Barreiras Kochem Vendramin
