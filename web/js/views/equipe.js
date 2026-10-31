import { api } from '../api.js';
import { data } from '../format.js';
import { abrirModal, aviso, html, icon, render, toast, vazio } from '../ui.js';

/** O link fica na tela para ser copiado: sem SMTP é o único jeito de entregar, e com SMTP serve de reserva. */
function mostrarLink(titulo, r, para) {
  const m = abrirModal({
    titulo,
    subtitulo: r.enviado ? `Enviado por e-mail para ${para}. O link abaixo também funciona.` : `Mande este link para ${para} por um canal seguro (e-mail, WhatsApp).`,
    corpo: html`
      <div class="stack">
        <input class="input mono" id="link-conta" readonly value="${r.link}">
        <div class="actions"><button class="btn btn-primary" id="copiar" type="button">${icon('doc')} Copiar link</button></div>
        <p class="small muted">Vale uma vez só. Quem tiver o link consegue usá-lo: não publique em grupos.</p>
      </div>`,
  });
  const campo = document.getElementById('link-conta');
  campo.addEventListener('focus', () => campo.select());
  document.getElementById('copiar').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(r.link); toast('Link copiado'); } catch { campo.select(); toast('Selecione e copie com Ctrl+C', 'erro'); }
  });
  return m;
}

export async function render_(el) {
  const eq = await api.equipe();
  render(el, html`
    <div class="page-head">
      <div><h1>Equipe</h1><p class="sub">Quem da sua empresa tem acesso ao ObraNexo. Convide um colega: a conta dele vê o mesmo catálogo e as mesmas análises.</p></div>
    </div>
    ${eq.email_configurado ? '' : html`<div style="margin-bottom:24px">${aviso('O envio de e-mail não está configurado neste servidor: o convite gera um link para você copiar e mandar.', 'warn')}</div>`}

    <form class="form-row" id="form-convite">
      <label class="field" style="flex:1;min-width:240px">E-mail do colega<input class="input" name="email" type="email" required></label>
      <button class="btn btn-primary" type="submit">${icon('send')} Convidar</button>
    </form>

    <section class="secao">
      <div class="secao-head"><h2>Contas</h2></div>
      <div class="linhas">${eq.usuarios.map((u) => html`
        <div class="linha" style="grid-template-columns:minmax(0,1fr) 140px ${eq.admin ? '190px' : ''}">
          <div style="min-width:0"><div class="linha-titulo truncate">${u.nome || u.email}</div><div class="linha-sub">${u.email}${u.admin ? ' · administrador' : ''}${u.ativo ? '' : ' · desativada'}</div></div>
          <div class="num small muted">desde ${data(u.criado_em)}</div>
          ${eq.admin ? html`<div class="actions" style="justify-content:flex-end"><button class="btn btn-ghost btn-sm" data-redefinir="${u.email}" type="button">${icon('refresh')} Link de nova senha</button></div>` : ''}
        </div>`)}</div>
    </section>

    <section class="secao">
      <div class="secao-head"><h2>Convites pendentes</h2></div>
      ${eq.convites.length ? html`<div class="linhas">${eq.convites.map((c) => html`
        <div class="linha" style="grid-template-columns:minmax(0,1fr) 160px 120px">
          <div class="linha-titulo truncate">${c.email}</div>
          <div class="num small muted">vale até ${data(c.expira_em)}</div>
          <div class="actions" style="justify-content:flex-end"><button class="btn btn-ghost btn-sm" data-cancelar="${c.id}" type="button">${icon('x')} Cancelar</button></div>
        </div>`)}</div>` : vazio('Nenhum convite pendente')}
    </section>

    ${eq.admin ? html`
      <section class="secao">
        <div class="secao-head"><h2>Convidar outra empresa</h2></div>
        <p class="muted small" style="margin-bottom:12px">Administrador da plataforma: a empresa é criada quando o convite é aceito, com o próprio catálogo e as próprias análises.</p>
        <form class="form-row" id="form-empresa">
          <label class="field" style="flex:1;min-width:200px">Empresa<input class="input" name="empresa_nova" required minlength="2"></label>
          <label class="field" style="flex:1;min-width:220px">E-mail de quem vai usar<input class="input" name="email" type="email" required></label>
          <button class="btn" type="submit">${icon('send')} Convidar empresa</button>
        </form>
      </section>` : ''}`);

  const enviar = (form, montar) => form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const dados = Object.fromEntries(new FormData(form));
    const botao = form.querySelector('button[type=submit]');
    botao.disabled = true;
    try {
      const r = await api.convidar(montar(dados));
      render_(el);
      mostrarLink('Convite criado', r, dados.email);
    } catch (err) {
      toast(err.message, 'erro');
      botao.disabled = false;
    }
  });
  enviar(el.querySelector('#form-convite'), (d) => ({ email: d.email }));
  enviar(el.querySelector('#form-empresa'), (d) => ({ email: d.email, empresa_nova: d.empresa_nova }));

  el.querySelectorAll('[data-cancelar]').forEach((b) => b.addEventListener('click', async () => {
    try {
      await api.cancelarConvite(b.dataset.cancelar);
      toast('Convite cancelado');
      render_(el);
    } catch (err) { toast(err.message, 'erro'); }
  }));
  el.querySelectorAll('[data-redefinir]').forEach((b) => b.addEventListener('click', async () => {
    try {
      mostrarLink('Link de nova senha', await api.gerarRedefinicao(b.dataset.redefinir), b.dataset.redefinir);
    } catch (err) { toast(err.message, 'erro'); }
  }));
}

export { render_ as render };
