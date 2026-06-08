const API_URL = 'http://localhost:5000';

async function chamar(caminho, opcoes = {}) {
  const resposta = await fetch(`${API_URL}${caminho}`, {
    headers: { 'Content-Type': 'application/json', ...(opcoes.headers || {}) },
    ...opcoes,
  });

  const texto = await resposta.text();

  let dados = {};
  try {
    dados = texto ? JSON.parse(texto) : {};
  } catch {
    throw new Error(`A API não respondeu JSON. Status: ${resposta.status}. Resposta: ${texto.slice(0, 120)}`);
  }

  if (!resposta.ok) {
    throw new Error(dados.erro || 'Erro na API');
  }

  return dados;
}

export const api = {
  listarPromocoes: () => chamar('/api/promocoes'),

  cadastrarPromocao: (envelope) => chamar('/api/promocoes', {
    method: 'POST',
    body: JSON.stringify(envelope),
  }),

  votar: (promocaoId, voto) => chamar(`/api/promocoes/${promocaoId}/votos`, {
    method: 'POST',
    body: JSON.stringify({ voto }),
  }),

  listarInteresses: (clienteId) => chamar(`/api/interesses?cliente_id=${clienteId}`),

  seguirCategoria: (clienteId, categoria) => chamar('/api/interesses', {
    method: 'POST',
    body: JSON.stringify({ cliente_id: clienteId, categoria }),
  }),

  pararCategoria: (clienteId, categoria) => chamar(`/api/interesses/${encodeURIComponent(categoria)}?cliente_id=${clienteId}`, {
    method: 'DELETE',
  }),
};

export const SSE_URL = `${API_URL}/api/sse`;
