import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Icon, addCollection } from '@iconify/react';
import solarIcons from '@iconify-json/solar/icons.json';
import { api, SSE_URL } from './api';
import { assinarComoLoja } from './assinatura';
import './style.css';

addCollection(solarIcons);

const categoriasSugestao = ['eletrônicos', 'livros', 'mercado', 'moda', 'games'];

const icones = {
  logo: 'solar:tag-price-bold-duotone',
  refresh: 'solar:refresh-bold-duotone',
  loja: 'solar:bag-4-bold-duotone',
  cliente: 'solar:user-heart-bold-duotone',
  email: 'solar:letter-bold-duotone',
  categoria: 'solar:tag-bold-duotone',
  preco: 'solar:wallet-money-bold-duotone',
  interesse: 'solar:heart-bold-duotone',
  seguir: 'solar:add-circle-bold-duotone',
  aviso: 'solar:bell-bing-bold-duotone',
  hot: 'solar:fire-bold-duotone',
  positivo: 'solar:like-bold-duotone',
  negativo: 'solar:dislike-bold-duotone',
  ok: 'solar:check-circle-bold-duotone',
  vazio: 'solar:box-minimalistic-bold-duotone',
  rest: 'solar:server-square-cloud-bold-duotone',
  sse: 'solar:bolt-circle-bold-duotone',
  rabbit: 'solar:routing-3-bold-duotone',
  chave: 'solar:key-minimalistic-square-2-bold-duotone',
  voltar: 'solar:alt-arrow-left-bold-duotone',
  lua: 'solar:moon-bold-duotone',
  sol: 'solar:sun-bold-duotone',
};

function Ico({ nome }) {
  return <Icon icon={nome} className="icone" aria-hidden="true" />;
}

function pegarClienteId() {
  const salvo = localStorage.getItem('cliente_id_promocoes');
  if (salvo) return salvo;

  const novo = crypto.randomUUID();
  localStorage.setItem('cliente_id_promocoes', novo);
  return novo;
}

function pegarTemaInicial() {
  const salvo = localStorage.getItem('tema_promocoes');
  if (salvo) return salvo;
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'escuro' : 'claro';
}

function precoFormatado(valor) {
  return Number(valor).toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  });
}

function classeCategoria(categoria = '') {
  const valor = categoria.toLowerCase();

  if (valor === 'eletrônicos') return 'tema-azul';
  if (valor === 'livros') return 'tema-roxo';
  if (valor === 'mercado') return 'tema-verde';
  if (valor === 'moda') return 'tema-rosa';
  if (valor === 'games') return 'tema-laranja';

  return 'tema-neutro';
}

function classeEvento(tipo = '') {
  if (tipo === 'hotdeal') return 'evento-hot';
  if (tipo === 'categoria') return 'evento-categoria';
  if (tipo === 'conexao') return 'evento-conexao';

  return 'evento-neutro';
}

function tituloEvento(tipo = '') {
  if (tipo === 'hotdeal') return 'hot deal';
  if (tipo === 'categoria') return 'categoria';
  if (tipo === 'conexao') return 'conexão';

  return tipo || 'evento';
}

function CabecalhoCompacto({ titulo, descricao, voltar, tema, alternarTema, acaoAtualizar }) {
  return (
    <header className="topo-app">
      <button className="botao botao--icone" type="button" onClick={voltar} title="Voltar">
        <Ico nome={icones.voltar} />
      </button>

      <div>
        <span className="selo selo--compacto">
          <Ico nome={icones.logo} />
          Promoções
        </span>
        <h1>{titulo}</h1>
        <p>{descricao}</p>
      </div>

      <div className="topo-acoes">
        {acaoAtualizar && (
          <button className="botao botao--claro" type="button" onClick={acaoAtualizar}>
            <Ico nome={icones.refresh} />
            Atualizar
          </button>
        )}

        <BotaoTema tema={tema} alternarTema={alternarTema} />
      </div>
    </header>
  );
}

function BotaoTema({ tema, alternarTema }) {
  const escuro = tema === 'escuro';

  return (
    <button
      className="botao botao--tema"
      type="button"
      onClick={alternarTema}
      title={escuro ? 'Ativar modo claro' : 'Ativar modo escuro'}
    >
      <Ico nome={escuro ? icones.sol : icones.lua} />
      {escuro ? 'Claro' : 'Escuro'}
    </button>
  );
}

function Mensagem({ texto }) {
  if (!texto) return null;

  return (
    <div className="mensagem">
      <Ico nome={icones.ok} />
      <span>{texto}</span>
    </div>
  );
}

function ResumoSistema() {
  return (
    <section className="cartao cartao--resumo">
      <div className="titulo-card">
        <span className="bolha bolha--laranja">
          <Ico nome={icones.aviso} />
        </span>

        <div>
          <h2>Resumo do sistema</h2>
          <p>Visão rápida dos recursos exigidos no trabalho.</p>
        </div>
      </div>

      <div className="resumo-lista resumo-lista--grade">
        <div className="resumo-item resumo-item--azul">
          <Ico nome={icones.rest} />
          <div>
            <strong>REST API</strong>
            <span>Cadastro, listagem, votos e interesses.</span>
          </div>
        </div>

        <div className="resumo-item resumo-item--roxo">
          <Ico nome={icones.sse} />
          <div>
            <strong>SSE</strong>
            <span>Notificações em tempo real no navegador.</span>
          </div>
        </div>

        <div className="resumo-item resumo-item--laranja">
          <Ico nome={icones.rabbit} />
          <div>
            <strong>RabbitMQ</strong>
            <span>Eventos assíncronos entre microsserviços.</span>
          </div>
        </div>

        <div className="resumo-item resumo-item--verde">
          <Ico nome={icones.chave} />
          <div>
            <strong>Assinatura digital</strong>
            <span>Promoções assinadas e validadas.</span>
          </div>
        </div>
      </div>
    </section>
  );
}

function TelaInicial({ abrirTela, promocoes, interesses, tema, alternarTema }) {
  const totalHotDeals = promocoes.filter((promo) => promo.hot_deal).length;

  return (
    <>
      <header className="hero hero--inicial">
        <div className="hero__conteudo">
          <span className="selo">
            <Ico nome={icones.logo} />
            Sistemas Distribuídos
          </span>

          <h1>Sistema de Promoções</h1>

          <p>
            Aplicação distribuída com REST, SSE, RabbitMQ e assinatura digital
            para cadastro, votação e notificação de promoções.
          </p>

          <div className="metricas">
            <span className="metrica metrica--promocoes">{promocoes.length} promoções</span>
            <span className="metrica metrica--interesses">{interesses.length} interesses</span>
            <span className="metrica metrica--hot">{totalHotDeals} hot deals</span>
          </div>
        </div>

        <BotaoTema tema={tema} alternarTema={alternarTema} />
      </header>

      <section className="seletor-telas">
        <button className="cartao opcao-tela opcao-tela--cliente" type="button" onClick={() => abrirTela('cliente')}>
          <span className="bolha bolha--roxa">
            <Ico nome={icones.cliente} />
          </span>
          <strong>Cliente</strong>
          <span>Seguir categorias, receber SSE e votar em promoções.</span>
        </button>

        <button className="cartao opcao-tela opcao-tela--vendedor" type="button" onClick={() => abrirTela('vendedor')}>
          <span className="bolha bolha--azul">
            <Ico nome={icones.loja} />
          </span>
          <strong>Vendedor</strong>
          <span>Cadastrar promoções assinadas digitalmente.</span>
        </button>
      </section>

      <ResumoSistema />
    </>
  );
}

function PainelInteresses({ interesses, categoriaInteresse, setCategoriaInteresse, seguir, parar }) {
  return (
    <section className="cartao cartao--interesses">
      <div className="titulo-card">
        <span className="bolha bolha--roxa">
          <Ico nome={icones.interesse} />
        </span>

        <div>
          <h2>Interesses do consumidor</h2>
          <p>As notificações SSE aparecem apenas para categorias seguidas.</p>
        </div>
      </div>

      <div className="atalhos atalhos--interesses">
        {categoriasSugestao.map((categoria) => (
          <button
            key={categoria}
            type="button"
            className={
              interesses.includes(categoria)
                ? `atalho ativo ${classeCategoria(categoria)}`
                : `atalho ${classeCategoria(categoria)}`
            }
            onClick={() => (interesses.includes(categoria) ? parar(categoria) : seguir(categoria))}
          >
            {categoria}
          </button>
        ))}
      </div>

      <div className="seguir-linha">
        <input
          placeholder="ex.: games"
          value={categoriaInteresse}
          onChange={(e) => setCategoriaInteresse(e.target.value)}
        />

        <button className="botao botao--principal" type="button" onClick={() => seguir()}>
          <Ico nome={icones.seguir} />
          Seguir
        </button>
      </div>

      <div className="chips">
        {interesses.length === 0 && (
          <span className="estado-vazio">
            <Ico nome={icones.vazio} />
            nenhum interesse cadastrado
          </span>
        )}

        {interesses.map((categoria) => (
          <button
            key={categoria}
            type="button"
            className={`chip ${classeCategoria(categoria)}`}
            onClick={() => parar(categoria)}
            title="Clique para cancelar o interesse"
          >
            {categoria}
            <span>×</span>
          </button>
        ))}
      </div>
    </section>
  );
}

function PainelNotificacoes({ notificacoes }) {
  return (
    <section className="cartao cartao--secao">
      <div className="titulo-card">
        <span className="bolha bolha--verde">
          <Ico nome={icones.aviso} />
        </span>

        <div>
          <h2>Notificações em tempo real</h2>
          <p>Eventos recebidos automaticamente pelo navegador via SSE.</p>
        </div>
      </div>

      {notificacoes.length === 0 ? (
        <div className="estado-vazio estado-vazio--bloco estado-vazio--centro">
          <Ico nome={icones.vazio} />

          <div>
            <strong>Nenhuma notificação recebida ainda</strong>
            <p>Siga uma categoria e aguarde promoções relacionadas.</p>
          </div>
        </div>
      ) : (
        <ul className="timeline">
          {notificacoes.map((item, indice) => (
            <li key={`${item.promocao_id || item.tipo}-${indice}`} className={classeEvento(item.tipo)}>
              <span className={`ponto ${classeEvento(item.tipo)}`} />

              <div>
                <strong>{tituloEvento(item.tipo)}</strong>
                <p>{item.mensagem}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ListaPromocoes({ promocoes, votar, modo = 'cliente' }) {
  return (
    <section className="cartao cartao--secao">
      <div className="titulo-card">
        <span className="bolha bolha--azul">
          <Ico nome={icones.categoria} />
        </span>

        <div>
          <h2>Promoções publicadas</h2>
          <p>Promoções aceitas depois da validação da assinatura.</p>
        </div>
      </div>

      {promocoes.length === 0 ? (
        <div className="estado-vazio estado-vazio--bloco estado-vazio--centro">
          <Ico nome={icones.vazio} />

          <div>
            <strong>Nenhuma promoção publicada</strong>
            <p>Quando uma loja cadastrar uma promoção válida, ela aparecerá aqui.</p>
          </div>
        </div>
      ) : (
        <div className="lista">
          {promocoes.map((promo) => (
            <article key={promo.promocao_id} className={promo.hot_deal ? 'promo promo--hot' : 'promo'}>
              <div className="promo__topo">
                <span className={`badge ${classeCategoria(promo.categoria)}`}>{promo.categoria}</span>

                {promo.hot_deal && (
                  <span className="badge badge--hot">
                    <Ico nome={icones.hot} />
                    hot deal
                  </span>
                )}
              </div>

              <h3>{promo.titulo}</h3>
              <p className="descricao">{promo.descricao}</p>
              <div className="preco">{precoFormatado(promo.preco)}</div>

              <p className="loja">
                <Ico nome={icones.loja} />
                Loja: {promo.loja_email}
              </p>

              {modo === 'cliente' && (
                <div className="botoes">
                  <button className="botao botao--voto botao--positivo" onClick={() => votar(promo.promocao_id, 'positivo')}>
                    <Ico nome={icones.positivo} />
                    positivo
                  </button>

                  <button className="botao botao--voto botao--negativo" onClick={() => votar(promo.promocao_id, 'negativo')}>
                    <Ico nome={icones.negativo} />
                    negativo
                  </button>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function TelaCliente(props) {
  return (
    <>
      <CabecalhoCompacto
        titulo="Área do cliente"
        descricao="Categorias, notificações e votos."
        voltar={props.voltar}
        tema={props.tema}
        alternarTema={props.alternarTema}
        acaoAtualizar={props.carregarPromocoes}
      />

      <Mensagem texto={props.mensagem} />

      <section className="grade-cliente">
        <PainelInteresses
          interesses={props.interesses}
          categoriaInteresse={props.categoriaInteresse}
          setCategoriaInteresse={props.setCategoriaInteresse}
          seguir={props.seguir}
          parar={props.parar}
        />

        <PainelNotificacoes notificacoes={props.notificacoes} />
      </section>

      <ListaPromocoes promocoes={props.promocoes} votar={props.votar} />
    </>
  );
}

function FormularioPromocao({ form, alterarCampo, cadastrar }) {
  return (
    <form className="cartao cartao--form formulario-vendedor" onSubmit={cadastrar}>
      <div className="titulo-card">
        <span className="bolha bolha--azul">
          <Ico nome={icones.loja} />
        </span>

        <div>
          <h2>Cadastrar promoção</h2>
          <p>A loja envia uma promoção assinada digitalmente.</p>
        </div>
      </div>

      <label className="campo">
        <span>E-mail da loja</span>

        <div className="entrada-com-icone">
          <Ico nome={icones.email} />
          <input value={form.loja_email} onChange={(e) => alterarCampo('loja_email', e.target.value)} />
        </div>
      </label>

      <label className="campo">
        <span>Título</span>
        <input
          value={form.titulo}
          onChange={(e) => alterarCampo('titulo', e.target.value)}
          placeholder="Ex.: Headset Gamer"
          required
        />
      </label>

      <label className="campo">
        <span>Categoria</span>
        <input
          list="categorias"
          value={form.categoria}
          onChange={(e) => alterarCampo('categoria', e.target.value)}
          required
        />
      </label>

      <datalist id="categorias">
        {categoriasSugestao.map((categoria) => (
          <option key={categoria} value={categoria} />
        ))}
      </datalist>

      <div className="atalhos">
        {categoriasSugestao.map((categoria) => (
          <button
            key={categoria}
            type="button"
            className={
              form.categoria === categoria
                ? `atalho ativo ${classeCategoria(categoria)}`
                : `atalho ${classeCategoria(categoria)}`
            }
            onClick={() => alterarCampo('categoria', categoria)}
          >
            {categoria}
          </button>
        ))}
      </div>

      <label className="campo">
        <span>Descrição</span>
        <textarea
          value={form.descricao}
          onChange={(e) => alterarCampo('descricao', e.target.value)}
          placeholder="Descreva rapidamente a promoção"
          required
        />
      </label>

      <label className="campo campo--ultimo">
        <span>Preço</span>

        <div className="entrada-com-icone">
          <Ico nome={icones.preco} />
          <input
            type="number"
            min="0.01"
            step="0.01"
            value={form.preco}
            onChange={(e) => alterarCampo('preco', e.target.value)}
            placeholder="99.90"
            required
          />
        </div>
      </label>

      <button className="botao botao--principal" type="submit">
        <Ico nome={icones.ok} />
        Cadastrar com assinatura da loja
      </button>
    </form>
  );
}

function TelaVendedor(props) {
  return (
    <>
      <CabecalhoCompacto
        titulo="Área do vendedor"
        descricao="Cadastro assinado de promoções."
        voltar={props.voltar}
        tema={props.tema}
        alternarTema={props.alternarTema}
        acaoAtualizar={props.carregarPromocoes}
      />

      <Mensagem texto={props.mensagem} />

      <section className="grade-vendedor">
        <FormularioPromocao form={props.form} alterarCampo={props.alterarCampo} cadastrar={props.cadastrar} />
        <ListaPromocoes promocoes={props.promocoes} votar={props.votar} modo="vendedor" />
      </section>
    </>
  );
}

function App() {
  const clienteId = useMemo(pegarClienteId, []);

  const [tela, setTela] = useState('inicio');
  const [tema, setTema] = useState(pegarTemaInicial);
  const [promocoes, setPromocoes] = useState([]);
  const [interesses, setInteresses] = useState([]);
  const [notificacoes, setNotificacoes] = useState([]);
  const [mensagem, setMensagem] = useState('');
  const [categoriaInteresse, setCategoriaInteresse] = useState('');

  const [form, setForm] = useState({
    loja_email: 'loja.demo@email.com',
    titulo: '',
    categoria: 'eletrônicos',
    descricao: '',
    preco: '',
  });

  async function carregarPromocoes() {
    const dados = await api.listarPromocoes();
    setPromocoes(dados);
  }

  async function carregarInteresses() {
    const dados = await api.listarInteresses(clienteId);
    setInteresses(dados.categorias || []);
  }

  useEffect(() => {
    document.body.dataset.theme = tema;
    localStorage.setItem('tema_promocoes', tema);
  }, [tema]);

  useEffect(() => {
    carregarPromocoes().catch((erro) => setMensagem(erro.message));
    carregarInteresses().catch(() => {});
  }, []);

  useEffect(() => {
    const sse = new EventSource(`${SSE_URL}?cliente_id=${clienteId}`);

    sse.onmessage = (evento) => {
      try {
        const dados = JSON.parse(evento.data);
        setNotificacoes((atuais) => [dados, ...atuais].slice(0, 8));

        if (['categoria', 'hotdeal'].includes(dados.tipo)) {
          carregarPromocoes().catch(() => {});
        }
      } catch {
        setMensagem('Não foi possível ler uma notificação SSE.');
      }
    };

    sse.onerror = () => {
      setMensagem('SSE tentando reconectar...');
    };

    return () => sse.close();
  }, [clienteId]);

  function alternarTema() {
    setTema((atual) => (atual === 'escuro' ? 'claro' : 'escuro'));
  }

  function abrirTela(proximaTela) {
    setMensagem('');
    setTela(proximaTela);
  }

  function voltarInicio() {
    setMensagem('');
    setTela('inicio');
  }

  function alterarCampo(campo, valor) {
    setForm((atual) => ({ ...atual, [campo]: valor }));
  }

  async function cadastrar(evento) {
    evento.preventDefault();
    setMensagem('');

    const payload = {
      promocao_id: crypto.randomUUID(),
      loja_id: 'loja_demo',
      loja_email: form.loja_email,
      titulo: form.titulo.trim(),
      categoria: form.categoria.trim().toLowerCase(),
      descricao: form.descricao.trim(),
      preco: Number(form.preco),
    };

    try {
      const assinatura = await assinarComoLoja(payload);
      const resposta = await api.cadastrarPromocao({ payload, assinatura });

      setMensagem(resposta.mensagem);
      setForm((atual) => ({ ...atual, titulo: '', descricao: '', preco: '' }));
      setTimeout(() => carregarPromocoes().catch(() => {}), 900);
    } catch (erro) {
      setMensagem(erro.message);
    }
  }

  async function votar(promocaoId, voto) {
    try {
      const resposta = await api.votar(promocaoId, voto);
      setMensagem(resposta.mensagem);
      setTimeout(() => carregarPromocoes().catch(() => {}), 700);
    } catch (erro) {
      setMensagem(erro.message);
    }
  }

  async function seguir(categoriaManual) {
    const categoria = (categoriaManual || categoriaInteresse).trim().toLowerCase();
    if (!categoria) return;

    try {
      const resposta = await api.seguirCategoria(clienteId, categoria);
      setInteresses(resposta.categorias || []);
      setCategoriaInteresse('');
      setMensagem(`Agora você segue: ${categoria}`);
    } catch (erro) {
      setMensagem(erro.message);
    }
  }

  async function parar(categoria) {
    try {
      const resposta = await api.pararCategoria(clienteId, categoria);
      setInteresses(resposta.categorias || []);
      setMensagem(`Interesse cancelado: ${categoria}`);
    } catch (erro) {
      setMensagem(erro.message);
    }
  }

  return (
    <main className={`pagina pagina--${tela}`}>
      {tela === 'inicio' && (
        <TelaInicial
          abrirTela={abrirTela}
          promocoes={promocoes}
          interesses={interesses}
          tema={tema}
          alternarTema={alternarTema}
        />
      )}

      {tela === 'cliente' && (
        <TelaCliente
          voltar={voltarInicio}
          tema={tema}
          alternarTema={alternarTema}
          mensagem={mensagem}
          promocoes={promocoes}
          interesses={interesses}
          notificacoes={notificacoes}
          categoriaInteresse={categoriaInteresse}
          setCategoriaInteresse={setCategoriaInteresse}
          carregarPromocoes={carregarPromocoes}
          seguir={seguir}
          parar={parar}
          votar={votar}
        />
      )}

      {tela === 'vendedor' && (
        <TelaVendedor
          voltar={voltarInicio}
          tema={tema}
          alternarTema={alternarTema}
          mensagem={mensagem}
          promocoes={promocoes}
          form={form}
          carregarPromocoes={carregarPromocoes}
          alterarCampo={alterarCampo}
          cadastrar={cadastrar}
          votar={votar}
        />
      )}
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
