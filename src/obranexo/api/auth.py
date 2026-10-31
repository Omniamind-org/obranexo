"""Login da API: rotas de entrada e saída e as dependências que protegem os demais endpoints.

A sessão vai num cookie HttpOnly (o EventSource das análises não manda cabeçalho, mas manda cookie); clientes de
API podem usar o mesmo token em `Authorization: Bearer`. SameSite=Lax impede que outro site faça POST com o cookie.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from obranexo import contas
from obranexo.config import config

COOKIE = "obranexo_sessao"

# Tentativas de login: 5 erros em 15 min por e-mail ou por IP bloqueiam até a janela passar
_JANELA_S, _MAX_ERROS = 15 * 60, 5
_erros: dict[str, deque[float]] = {}
_lock = threading.Lock()

rotas = APIRouter(prefix="/api/auth", tags=["login"])


def _token(request: Request) -> str | None:
    autorizacao = request.headers.get("authorization", "")
    if autorizacao.lower().startswith("bearer "):
        return autorizacao[7:].strip()
    return request.cookies.get(COOKIE)


# Assíncrona de propósito: roda na tarefa da requisição, então a empresa definida aqui chega ao endpoint
# (que o FastAPI executa numa thread com uma cópia desse contexto) e, pelos jobs, às threads das análises.
async def exige_login(request: Request) -> contas.Usuario:
    usuario = contas.usuario_da_sessao(_token(request))
    if usuario is None:
        raise HTTPException(401, "faça login para continuar", headers={"WWW-Authenticate": "Bearer"})
    contas.definir_empresa_ativa(usuario.empresa_id)
    request.state.usuario = usuario
    return usuario


async def exige_admin(usuario: Annotated[contas.Usuario, Depends(exige_login)]) -> contas.Usuario:
    if not usuario.admin:
        raise HTTPException(403, "apenas administradores da plataforma")
    return usuario


def _bloqueado(*chaves: str) -> bool:
    limite = time.monotonic() - _JANELA_S
    with _lock:
        for chave in chaves:
            fila = _erros.get(chave)
            while fila and fila[0] < limite:
                fila.popleft()
            if fila and len(fila) >= _MAX_ERROS:
                return True
    return False


def _registrar_erro(*chaves: str) -> None:
    with _lock:
        for chave in chaves:
            _erros.setdefault(chave, deque()).append(time.monotonic())


def _abrir(response: Response, usuario: contas.Usuario) -> dict[str, Any]:
    token = contas.abrir_sessao(usuario)
    response.set_cookie(COOKIE, token, max_age=config.sessao_horas * 3600, httponly=True, samesite="lax", secure=config.cookie_seguro, path="/")
    return {"usuario": usuario.publico(), "token": token}


class PedidoLogin(BaseModel):
    email: str = Field(max_length=254)
    senha: str = Field(max_length=200)


@rotas.post("/login")
def login(pedido: PedidoLogin, request: Request, response: Response) -> dict[str, Any]:
    """Entra com e-mail e senha. Devolve o usuário e grava o cookie de sessão (o token também vem no corpo, para clientes de API)."""
    chaves = (f"email:{contas.normalizar_email(pedido.email)}", f"ip:{request.client.host if request.client else '?'}")
    if _bloqueado(*chaves):
        raise HTTPException(429, "muitas tentativas; aguarde alguns minutos")
    usuario = contas.autenticar(pedido.email, pedido.senha)
    if usuario is None:
        _registrar_erro(*chaves)
        raise HTTPException(401, "e-mail ou senha incorretos")
    return _abrir(response, usuario)


@rotas.post("/logout")
def logout(request: Request, response: Response) -> dict[str, Any]:
    contas.encerrar_sessao(_token(request))
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@rotas.get("/eu")
def eu(usuario: Annotated[contas.Usuario, Depends(exige_login)]) -> dict[str, Any]:
    """Quem está logado e em qual empresa."""
    return usuario.publico()


class PedidoCadastro(BaseModel):
    empresa: str = Field(min_length=2, max_length=200)
    cnpj: str | None = Field(None, pattern=r"^\d{14}$")
    nome: str = Field("", max_length=200)
    email: str = Field(max_length=254)
    senha: str = Field(min_length=contas.SENHA_MIN, max_length=200)


@rotas.post("/cadastro", status_code=201)
def cadastro(pedido: PedidoCadastro, response: Response) -> dict[str, Any]:
    """Cria a empresa e o primeiro usuário e já entra. Só com OBRANEXO_CADASTRO_ABERTO=1; sem isso, contas por convite."""
    if not config.cadastro_aberto:
        raise HTTPException(403, "cadastro fechado: peça um convite à equipe do ObraNexo")
    if contas.buscar_usuario(pedido.email):
        raise HTTPException(409, "já existe uma conta com esse e-mail")
    try:
        contas.validar_email(pedido.email)  # antes de criar a empresa, para não deixar empresa sem usuário
        empresa_id = contas.criar_empresa(pedido.empresa, pedido.cnpj)
        usuario = contas.criar_usuario(pedido.email, pedido.senha, empresa_id, pedido.nome)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _abrir(response, usuario)


# ---------------------------------------------------------------------------- convite e nova senha (sem login)
# O token vem sempre no corpo: na URL ele iria para o log de acesso do servidor.


class PedidoToken(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class PedidoAceite(PedidoToken):
    senha: str = Field(min_length=contas.SENHA_MIN, max_length=200)
    nome: str = Field("", max_length=200)


class PedidoRecuperar(BaseModel):
    email: str = Field(max_length=254)


class PedidoRedefinir(PedidoToken):
    senha: str = Field(min_length=contas.SENHA_MIN, max_length=200)


@rotas.post("/convites/ver")
def ver_convite(pedido: PedidoToken) -> dict[str, Any]:
    """E-mail e empresa do convite, para a tela de aceite."""
    convite = contas.ver_convite(pedido.token)
    if convite is None:
        raise HTTPException(404, "convite inválido ou expirado: peça um novo")
    return convite


@rotas.post("/convites/aceitar")
def aceitar_convite(pedido: PedidoAceite, response: Response) -> dict[str, Any]:
    """Cria a conta do convidado com a senha escolhida e já entra."""
    try:
        usuario = contas.aceitar_convite(pedido.token, pedido.senha, pedido.nome)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _abrir(response, usuario)


@rotas.post("/recuperar", status_code=202)
def recuperar_senha(pedido: PedidoRecuperar, request: Request) -> dict[str, Any]:
    """Manda o link de nova senha, se houver conta com o e-mail. A resposta é a mesma com ou sem conta."""
    from obranexo import notificacoes

    chaves = (f"recuperar:{contas.normalizar_email(pedido.email)}", f"recuperar-ip:{request.client.host if request.client else '?'}")
    if _bloqueado(*chaves):
        raise HTTPException(429, "muitos pedidos; aguarde alguns minutos")
    _registrar_erro(*chaves)  # conta pedidos, não erros: no máximo 5 por e-mail e por IP a cada 15 min
    token = contas.criar_redefinicao(pedido.email)
    if token:
        notificacoes.enviar_redefinicao(contas.normalizar_email(pedido.email), token)
    return {"ok": True, "email_configurado": notificacoes.configurado()}


@rotas.post("/redefinir")
def redefinir_senha(pedido: PedidoRedefinir, response: Response) -> dict[str, Any]:
    """Troca a senha pelo link recebido, encerra as outras sessões e já entra."""
    try:
        usuario = contas.redefinir_senha(pedido.token, pedido.senha)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _abrir(response, usuario)
