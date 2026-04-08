# 🛒 Sistema de Promoções Distribuído (MOM)

**Avaliação 2 — Sistemas Distribuídos | UTFPR (BSI)** **Tema:** Microsserviços, Mensageria (RabbitMQ) e Criptografia Assimétrica.

Este projeto implementa uma arquitetura orientada a eventos (EDA) para o gerenciamento de promoções, onde o desacoplamento é garantido pelo uso de um broker de mensagens e a segurança pela assinatura digital de cada evento.

## 📐 Arquitetura do Sistema

A comunicação entre os microsserviços é estritamente indireta via RabbitMQ.

```text
MS Gateway     ──publishes──▶  promocao.recebida   ──▶  MS Promoção
MS Gateway     ──publishes──▶  promocao.voto       ──▶  MS Ranking
MS Gateway     ◀──consumes──   promocao.publicada

MS Promoção    ──publishes──▶  promocao.publicada  ──▶  MS Gateway
                                                   ──▶  MS Notificação

MS Ranking     ◀──consumes──   promocao.voto
MS Ranking     ──publishes──▶  promocao.destaque   ──▶  MS Notificação
                                                   ──▶  Clientes (Destaque)

MS Notificação ──publishes──▶  promocao.<categoria> ──▶  Clientes (Categoria)
```

> **Fluxo do Hot Deal:** O MS Ranking publica `promocao.destaque`. O MS Notificação consome este evento e republica em `promocao.<categoria>` com a flag `"label": "🔥 HOT DEAL"`, permitindo que mesmo clientes que não seguem "destaques" sejam avisados sobre ofertas quentes em suas categorias favoritas.



## 🔐 Segurança e Integridade (RSA)

Para garantir que uma promoção não seja forjada ou alterada, utilizamos **Criptografia Assimétrica (RSA)** com hash **SHA-256**.

* **Assinatura:** O produtor gera o hash do payload e assina com sua **chave privada**.
* **Validação:** O consumidor utiliza a **chave pública** do produtor esperado. Se a assinatura for inválida, o evento é **descartado imediatamente**.

### Matriz de Validação de Assinaturas

| Consumidor | Valida assinatura de |
| :--- | :--- |
| **MS Promoção** | `gateway` |
| **MS Ranking** | `gateway` |
| **MS Notificação** | `promocao` ou `ranking` |
| **MS Gateway** | `promocao` |
| **Clientes** | `ranking` (somente em `promocao.destaque`) |

## 🐇 Configuração do RabbitMQ

O sistema utiliza uma exchange do tipo **`topic`** chamada `Promocoes`.

* **Routing Keys:** Utilizam o padrão hierárquico `promocao.<subtipo>`, permitindo bindings flexíveis. 
* **Filas Dinâmicas:** Cada processo possui sua própria fila. Os clientes geram filas dinâmicas temporárias que são excluídas automaticamente (auto_delete=True) ao encerrarem a conexão.
* **Graceful Shutdown:** Interrupções nos terminais (Ctrl+C) disparam um encerramento seguro, fechando as conexões TCP com o broker sem deixar estados inconsistentes.

## 🏆 Regra do Hot Deal (Destaque)

Uma promoção é elevada ao status de **Hot Deal** quando atinge um score crítico: 
$$\text{Score} = (\text{Votos Positivos} - \text{Votos Negativos}) \geq 5$$

## 🚀 Como Executar

> **Nota:** Certifique-se de estar dentro da pasta raiz do projeto `/02-mom-rabbitmq-promocoes`. É necessário criar e ativar um ambiente virtual (.venv) e instalar as dependências do requirements.txt antes de rodar os serviços locais.

1.  **Subir Infraestrutura (Docker):**
    ```bash
    docker compose up -d
    ```
2.  **Gerar Chaves RSA:**
    ```bash
    python keys/generate_keys.py
    ```
3.  **Iniciar Microsserviços (Terminais Separados):**
    ```bash
    python ms-promocao/main.py
    python ms-ranking/main.py
    python ms-notificacao/main.py
    python ms-gateway/main.py
    ```
4.  **Iniciar Clientes de Teste:** 

    Abra um ou mais terminais e execute o cliente universal. Um menu interativo permitirá escolher presets (A ou B) ou criar um cliente customizado ouvindo categorias específicas:
    ```bash
    python ms-cliente/main.py
    ```

---
**Desenvolvido por Alexei Lara & Julia Oliveira** *Engenharia de Computação & Sistemas de Informação - UTFPR Curitiba*

---