# Sistema de Promoções REST + SSE + MOM

Projeto 04 de Sistemas Distribuídos: aplicação web de promoções com frontend React, backend Python, RabbitMQ, REST, SSE, assinatura digital RSA e envio de e-mail via Resend com fallback simulado.

## Arquitetura

O frontend é a única interface para consumidor e loja/vendedor. Ele acessa apenas o MS Gateway por REST/SSE.

```text
Frontend --REST/SSE--> MS Gateway

MS Gateway     --promocao.recebida--> MS Promoção
MS Gateway     --promocao.voto------> MS Ranking
MS Promoção    --promocao.publicada-> MS Gateway + MS Notificação
MS Ranking     --promocao.destaque--> MS Gateway + MS Notificação
MS Notificação --promocao.categoria-> MS Gateway
MS Notificação --notificacao.hotdeal> MS Gateway
```

Toda comunicação entre microsserviços passa pelo RabbitMQ.

## Serviços

- `ms-gateway`: API REST, cache em memória, interesses dos consumidores e SSE.
- `ms-promocao`: valida a assinatura da loja e publica promoções aprovadas.
- `ms-ranking`: processa votos, calcula score e publica hot deals.
- `ms-notificacao`: envia e-mails reais/simulados e publica notificações para SSE.
- `frontend`: interface web para consumidor e loja/vendedor.

O antigo `ms-cliente` do projeto base foi removido, pois o cliente agora é o navegador.

## Execução

Na pasta `04-rest-sse-mom-promocoes`:

```bash
docker compose up --build
```

Acesse:

- Frontend: http://localhost:5173
- Gateway/API: http://localhost:5000
- RabbitMQ Management: http://localhost:15673 (`guest` / `guest`)

O serviço `keygen` gera automaticamente as chaves RSA em um volume Docker compartilhado antes dos microsserviços iniciarem.

## E-mail

Sem credenciais, o MS Notificação usa modo simulado e registra o envio nos logs.

Para envio real com Resend:

```bash
RESEND_API_KEY=... \
RESEND_FROM_EMAIL='Sistema de Promoções <onboarding@resend.dev>' \
docker compose up --build
```

Opcionalmente, use `RESEND_TO_OVERRIDE=email@destino.com` durante testes para redirecionar todos os envios.

## Endpoints Principais

- `GET /api/promocoes`
- `POST /api/promocoes`
- `POST /api/promocoes/<promocao_id>/votos`
- `GET /api/interesses?cliente_id=...`
- `POST /api/interesses`
- `DELETE /api/interesses/<categoria>?cliente_id=...`
- `GET /api/sse?cliente_id=...`
