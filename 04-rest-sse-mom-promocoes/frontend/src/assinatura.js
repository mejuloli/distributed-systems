import { LOJA_DEMO_PRIVATE_KEY } from './lojaDemoKey';

function ordenar(valor) {
  if (Array.isArray(valor)) return valor.map(ordenar);
  if (valor && typeof valor === 'object') {
    return Object.keys(valor).sort().reduce((novo, chave) => {
      novo[chave] = ordenar(valor[chave]);
      return novo;
    }, {});
  }
  return valor;
}

function textoPadrao(dados) {
  return JSON.stringify(ordenar(dados));
}

function pemParaBuffer(pem) {
  const base64 = pem.replace(/-----BEGIN PRIVATE KEY-----/g, '')
    .replace(/-----END PRIVATE KEY-----/g, '')
    .replace(/\s/g, '');

  const binario = atob(base64);
  const bytes = new Uint8Array(binario.length);

  for (let i = 0; i < binario.length; i += 1) {
    bytes[i] = binario.charCodeAt(i);
  }

  return bytes.buffer;
}

function bufferParaBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let texto = '';

  bytes.forEach((byte) => {
    texto += String.fromCharCode(byte);
  });

  return btoa(texto);
}

async function importarChave() {
  return crypto.subtle.importKey(
    'pkcs8',
    pemParaBuffer(LOJA_DEMO_PRIVATE_KEY),
    { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' },
    false,
    ['sign'],
  );
}

export async function assinarComoLoja(dados) {
  const chave = await importarChave();
  const bytes = new TextEncoder().encode(textoPadrao(dados));
  const assinatura = await crypto.subtle.sign('RSASSA-PKCS1-v1_5', chave, bytes);
  return bufferParaBase64(assinatura);
}
