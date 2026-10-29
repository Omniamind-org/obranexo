"""Linha de comando do ObraNexo.

  obranexo servidor [--porta 8000]        sobe a API + interface web (http://127.0.0.1:8000)
  obranexo casos                         lista os pacotes congelados em data/casos
  obranexo analisar <caso> [--catalogo]  executa a análise completa de um caso
  obranexo coletar <cnpj> <ano> <seq> <nome>   baixa uma contratação do PNCP e congela em data/casos/<nome>
  obranexo buscar [--uf GO] [--dias 30] [--palavras lumin,led]   busca contratações recentes no PNCP
  obranexo abertas [--uf GO] [--palavras lumin,led]              contratações com propostas em aberto
  obranexo usuario criar <email> --empresa "Nome" [--admin]      cria a conta (e a empresa) para entrar na interface
  obranexo usuario listar | senha <email> | desativar <email> | ativar <email>
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from obranexo.config import config


def _empresa(caminho: str | None):
    from obranexo.catalog.loader import carregar_catalogo_json, carregar_catalogo_tabela

    p = Path(caminho) if caminho else config.catalogo_demo
    return carregar_catalogo_json(p) if p.suffix.lower() == ".json" else carregar_catalogo_tabela(p)


def cmd_casos(_args) -> int:
    from obranexo.connectors.pncp import carregar_caso, listar_casos

    for d in listar_casos():
        c, itens, docs = carregar_caso(d)
        print(f"{d.name:32} {c.id:30} {c.orgao_nome[:40]:40} itens={len(itens):3} docs={len(docs):2}  {c.objeto[:70]}")
    return 0


def cmd_analisar(args) -> int:
    from obranexo.agents.pipeline import executar_caso

    caso = Path(args.caso)
    if not caso.exists():
        caso = config.dir_casos / args.caso
    if not caso.exists():
        print(f"caso não encontrado: {args.caso}", file=sys.stderr)
        return 2
    empresa = _empresa(args.catalogo)

    def on_evento(ev):
        print(f"[{ev.ts:%H:%M:%S}] {ev.no:20} {ev.mensagem}")

    analise = executar_caso(caso, empresa, on_evento=on_evento)
    if analise.status != "concluida":
        print(f"ERRO: {analise.erro}", file=sys.stderr)
        return 1
    saida = Path(args.saida) if args.saida else config.dir_analises / f"{analise.id}.md"
    saida.write_text(analise.dossie.conteudo_md, encoding="utf-8")
    print(f"\nAnálise {analise.id} concluída em {analise.duracao_s():.1f}s · modo {analise.modo} · custo US$ {analise.uso_llm.custo_usd:.4f}")
    print(f"Dossiê: {saida}")
    return 0


def cmd_coletar(args) -> int:
    from obranexo.connectors.pncp import PNCPClient

    destino = config.dir_casos / args.nome
    cli = PNCPClient()
    c, itens, docs = cli.coletar_caso(args.cnpj, int(args.ano), int(args.seq), destino, max_mb=args.max_mb, so_pdf=args.so_pdf)
    baixados = sum(1 for d in docs if d.caminho_local)
    print(f"{c.id}: {len(itens)} itens, {baixados}/{len(docs)} documentos baixados e congelados em {destino}")
    return 0


def _imprimir(lista) -> None:
    for c in lista:
        enc = c.data_encerramento_proposta.strftime("%d/%m/%Y") if c.data_encerramento_proposta else "—"
        print(f"{c.id:30} {(c.municipio or '')[:18]:18} enc:{enc:10} R$ {c.valor_estimado or 0:>14,.2f}  {c.objeto[:80]}")


def cmd_buscar(args) -> int:
    from obranexo.connectors.pncp import PNCPClient

    cli = PNCPClient()
    fim = datetime.now()
    ini = fim - timedelta(days=int(args.dias))
    palavras = [p.strip() for p in args.palavras.split(",") if p.strip()]
    pagina, total = 1, 1
    achados = []
    while pagina <= total and pagina <= int(args.max_paginas):
        lista, total = cli.buscar_publicacoes(ini.strftime("%Y%m%d"), fim.strftime("%Y%m%d"), uf=args.uf, pagina=pagina)
        achados += cli.filtrar_por_palavras(lista, palavras) if palavras else lista
        pagina += 1
    _imprimir(achados)
    print(f"\n{len(achados)} contratação(ões) · {min(pagina - 1, total)}/{total} página(s) consultadas")
    return 0


def cmd_abertas(args) -> int:
    from obranexo.connectors.pncp import PNCPClient

    cli = PNCPClient()
    palavras = [p.strip() for p in args.palavras.split(",") if p.strip()]
    pagina, total = 1, 1
    achados = []
    while pagina <= total and pagina <= int(args.max_paginas):
        lista, total = cli.buscar_propostas_abertas(uf=args.uf, pagina=pagina, horizonte_dias=int(args.dias))
        achados += cli.filtrar_por_palavras(lista, palavras) if palavras else lista
        pagina += 1
    _imprimir(achados)
    print(f"\n{len(achados)} contratação(ões) com propostas abertas")
    return 0


def _ler_senha(senha: str | None) -> str:
    if senha:
        return senha
    from getpass import getpass

    senha = getpass("Senha: ")
    if getpass("Repita a senha: ") != senha:
        raise ValueError("as senhas não conferem")
    return senha


def cmd_usuario(args) -> int:
    from obranexo import contas

    try:
        if args.acao == "listar":
            for u in contas.listar_usuarios():
                marcas = " ".join(m for m, v in (("admin", u["admin"]), ("desativado", not u["ativo"])) if v)
                print(f"{u['email']:36} {u['empresa'][:30]:30} {u['empresa_id']:16} {marcas}")
            return 0
        if not args.email:
            raise ValueError("informe o e-mail")
        if args.acao == "criar":
            if bool(args.empresa) == bool(args.empresa_id):
                raise ValueError("informe --empresa (cria uma empresa nova) ou --empresa-id (entra numa existente)")
            contas.validar_email(args.email)
            if contas.buscar_usuario(args.email):
                raise ValueError(f"já existe uma conta com o e-mail {args.email}")
            senha = _ler_senha(args.senha)
            empresa_id = args.empresa_id or contas.criar_empresa(args.empresa, args.cnpj)
            u = contas.criar_usuario(args.email, senha, empresa_id, args.nome or "", admin=args.admin)
            print(f"Conta criada: {u.email} · empresa {u.empresa_nome} ({u.empresa_id}){' · administrador' if u.admin else ''}")
        elif args.acao == "senha":
            contas.definir_senha(args.email, _ler_senha(args.senha))
            print("Senha trocada; as sessões abertas foram encerradas.")
        else:
            contas.definir_ativo(args.email, args.acao == "ativar")
            print(f"Conta {'ativada' if args.acao == 'ativar' else 'desativada'}: {args.email}")
    except ValueError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    return 0


def cmd_servidor(args) -> int:
    import uvicorn

    print(f"ObraNexo em http://{args.host}:{args.porta}  ·  API: http://{args.host}:{args.porta}/api/docs")
    uvicorn.run("obranexo.api.main:app", host=args.host, port=int(args.porta), reload=args.reload)
    return 0


def main(argv: list[str] | None = None) -> int:
    from obranexo.observability import logs

    logs.configurar()
    parser = argparse.ArgumentParser(prog="obranexo", description="ObraNexo — inteligência comercial agêntica")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("servidor", help="sobe a API e a interface web")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--porta", default=8000)
    p.add_argument("--reload", action="store_true", help="recarrega ao editar o código (desenvolvimento)")
    p.set_defaults(fn=cmd_servidor)
    sub.add_parser("casos", help="lista os casos congelados").set_defaults(fn=cmd_casos)
    p = sub.add_parser("analisar", help="analisa um caso congelado")
    p.add_argument("caso")
    p.add_argument("--catalogo", help="JSON/CSV/XLSX do catálogo (padrão: catálogo demo)")
    p.add_argument("--saida", help="arquivo .md de saída do dossiê")
    p.set_defaults(fn=cmd_analisar)
    p = sub.add_parser("coletar", help="baixa e congela uma contratação do PNCP")
    p.add_argument("cnpj")
    p.add_argument("ano")
    p.add_argument("seq")
    p.add_argument("nome")
    p.add_argument("--max-mb", type=float, default=None, help="não baixa anexos maiores que N MB (ficam só listados)")
    p.add_argument("--so-pdf", action="store_true", help="não baixa anexos .zip/.dwg/.rar")
    p.set_defaults(fn=cmd_coletar)
    for nome, fn in (("buscar", cmd_buscar), ("abertas", cmd_abertas)):
        p = sub.add_parser(nome)
        p.add_argument("--uf", default="GO")
        p.add_argument("--palavras", default="lumin,led,refletor,ilumina,material elétrico,material eletrico")
        p.add_argument("--max-paginas", default=10)
        # buscar: publicadas nos últimos N dias · abertas: que encerram nos próximos N dias
        p.add_argument("--dias", default=30 if nome == "buscar" else 60)
        p.set_defaults(fn=fn)
    p = sub.add_parser("usuario", help="contas de acesso à interface (o cadastro é por convite)")
    p.add_argument("acao", choices=("criar", "listar", "senha", "desativar", "ativar"))
    p.add_argument("email", nargs="?")
    p.add_argument("--empresa", help="nome da empresa nova (criar)")
    p.add_argument("--empresa-id", help="id de uma empresa existente, para outro usuário dela (criar)")
    p.add_argument("--cnpj", help="CNPJ da empresa nova, só dígitos (criar)")
    p.add_argument("--nome", help="nome da pessoa (criar)")
    p.add_argument("--admin", action="store_true", help="administra a plataforma: provedor de IA, custos e trilha (criar)")
    p.add_argument("--senha", help="sem ela, a senha é pedida no terminal (recomendado: não fica no histórico)")
    p.set_defaults(fn=cmd_usuario)
    p = sub.add_parser("grafo", help="imprime o grafo da análise (o mesmo que executa a análise) para a documentação")
    p.add_argument("--formato", choices=("md", "mermaid", "json"), default="md")
    p.set_defaults(fn=cmd_grafo)
    args = parser.parse_args(argv)
    return args.fn(args)


def cmd_grafo(args) -> int:
    import json

    from obranexo.agents.pipeline import GRAFO

    if args.formato == "mermaid":
        print(GRAFO.mermaid())
    elif args.formato == "json":
        print(json.dumps(GRAFO.descrever(), ensure_ascii=False, indent=1))
    else:
        print(GRAFO.markdown())
    return 0


if __name__ == "__main__":
    sys.exit(main())
