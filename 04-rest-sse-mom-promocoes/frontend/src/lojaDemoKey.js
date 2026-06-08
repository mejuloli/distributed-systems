let chaveCache = null;

export async function carregarLojaDemoPrivateKey() {
  if (chaveCache) return chaveCache;

  const resposta = await fetch('/keys/loja_demo_private.pem');
  if (!resposta.ok) {
    throw new Error('Chave da loja demo não encontrada. Inicie o projeto com Docker para gerar as chaves.');
  }

  chaveCache = await resposta.text();
  return chaveCache;
}
