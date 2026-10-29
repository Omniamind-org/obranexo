"""Contas: empresas, usuários e sessões de login, no SQLite data/obranexo.db.

A empresa é a unidade de isolamento: cada uma tem o próprio catálogo, análises, prospecções e conversas, em
data/empresas/<empresa_id>/. A empresa da requisição fica num contextvar (`empresa_ativa`), definido pela API
depois do login e copiado para as threads dos jobs; storage/store.py e storage/chat.py leem dele. Fora de uma
requisição (linha de comando, testes) não há empresa ativa e os dados ficam nos diretórios de sempre (data/analises…).

Senhas com scrypt (biblioteca padrão); a sessão é um token aleatório guardado só como hash SHA-256, então quem
lê o banco não consegue entrar com ele.
"""

from __future__ import annotations

import contextvars
import hashlib
import hmac
import secrets
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from obranexo.config import config

_DDL = """
CREATE TABLE IF NOT EXISTS empresas (
  id TEXT PRIMARY KEY,
  nome TEXT NOT NULL,
  cnpj TEXT,
  criada_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS usuarios (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  nome TEXT NOT NULL DEFAULT '',
  senha_hash TEXT NOT NULL,
  empresa_id TEXT NOT NULL REFERENCES empresas(id),
  admin INTEGER NOT NULL DEFAULT 0,
  ativo INTEGER NOT NULL DEFAULT 1,
  criado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessoes (
  token_hash TEXT PRIMARY KEY,
  usuario_id TEXT NOT NULL REFERENCES usuarios(id),
  criada_em TEXT NOT NULL,
  expira_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS links_conta (
  id TEXT PRIMARY KEY,
  token_hash TEXT NOT NULL UNIQUE,
  tipo TEXT NOT NULL,
  email TEXT NOT NULL,
  empresa_id TEXT REFERENCES empresas(id),
  empresa_nova TEXT,
  admin INTEGER NOT NULL DEFAULT 0,
  criado_por TEXT REFERENCES usuarios(id),
  criado_em TEXT NOT NULL,
  expira_em TEXT NOT NULL,
  usado_em TEXT
);
"""

SENHA_MIN = 8
# Links de uso único mandados por e-mail ou copiados da tela Equipe: convite para criar conta e redefinição de senha
VALIDADE_CONVITE = timedelta(days=7)
VALIDADE_REDEFINICAO = timedelta(hours=1)
# scrypt: ~16 MB e algumas dezenas de ms por senha; os parâmetros vão no próprio hash para poderem subir depois
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1

_lock = threading.Lock()
_preparados: set[str] = set()

_empresa_ativa: contextvars.ContextVar[str | None] = contextvars.ContextVar("obranexo_empresa", default=None)


def empresa_ativa() -> str | None:
    """Id da empresa da requisição atual; None fora da API (linha de comando, testes)."""
    return _empresa_ativa.get()


@contextmanager
def na_empresa(empresa_id: str | None) -> Iterator[None]:
    token = _empresa_ativa.set(empresa_id)
    try:
        yield
    finally:
        _empresa_ativa.reset(token)


def definir_empresa_ativa(empresa_id: str | None) -> None:
    """Para a dependência de login da API: vale até o fim da requisição (cada requisição tem o próprio contexto)."""
    _empresa_ativa.set(empresa_id)


def dir_empresa(empresa_id: str) -> Path:
    return config.dir_dados / "empresas" / empresa_id


# ---------------------------------------------------------------------------- senhas


def hash_senha(senha: str) -> str:
    sal = secrets.token_bytes(16)
    h = hashlib.scrypt(senha.encode(), salt=sal, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${sal.hex()}${h.hex()}"


def conferir_senha(senha: str, guardado: str) -> bool:
    try:
        algoritmo, n, r, p, sal, h = guardado.split("$")
    except ValueError:
        return False
    if algoritmo != "scrypt":
        return False
    calculado = hashlib.scrypt(senha.encode(), salt=bytes.fromhex(sal), n=int(n), r=int(r), p=int(p))
    return hmac.compare_digest(calculado.hex(), h)


# Conferido quando o e-mail não existe, para o tempo de resposta não revelar quais e-mails têm conta
_HASH_FICTICIO = hash_senha(secrets.token_urlsafe(16))


# ---------------------------------------------------------------------------- banco


def _conectar() -> sqlite3.Connection:
    caminho = config.caminho_db
    caminho.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(caminho, timeout=5)
    con.execute("PRAGMA foreign_keys = ON")
    if str(caminho) not in _preparados:
        con.executescript(_DDL)
        _preparados.add(str(caminho))
    return con


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass(frozen=True)
class Usuario:
    id: str
    email: str
    nome: str
    empresa_id: str
    empresa_nome: str
    admin: bool  # administra a plataforma: provedor de IA, custos e trilha de todas as empresas

    def publico(self) -> dict:
        return {"email": self.email, "nome": self.nome, "admin": self.admin, "empresa": {"id": self.empresa_id, "nome": self.empresa_nome}}


_SELECT_USUARIO = """
SELECT u.id, u.email, u.nome, u.empresa_id, e.nome, u.admin
FROM usuarios u JOIN empresas e ON e.id = u.empresa_id
"""


def _usuario(linha) -> Usuario | None:
    if linha is None:
        return None
    uid, email, nome, empresa_id, empresa_nome, admin = linha
    return Usuario(uid, email, nome, empresa_id, empresa_nome, bool(admin))


def normalizar_email(email: str) -> str:
    return email.strip().lower()


def validar_email(email: str) -> str:
    email = normalizar_email(email)
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError("e-mail inválido")
    return email


def criar_empresa(nome: str, cnpj: str | None = None) -> str:
    if not nome.strip():
        raise ValueError("informe o nome da empresa")
    empresa_id = f"emp_{secrets.token_hex(6)}"
    with _lock, _conectar() as con:
        con.execute("INSERT INTO empresas (id, nome, cnpj, criada_em) VALUES (?, ?, ?, ?)", (empresa_id, nome.strip(), cnpj, _agora()))
    return empresa_id


def buscar_empresa(empresa_id: str) -> dict | None:
    with _conectar() as con:
        linha = con.execute("SELECT id, nome, cnpj FROM empresas WHERE id = ?", (empresa_id,)).fetchone()
    return {"id": linha[0], "nome": linha[1], "cnpj": linha[2]} if linha else None


def listar_empresas() -> list[dict]:
    with _conectar() as con:
        linhas = con.execute("SELECT id, nome, cnpj FROM empresas ORDER BY nome").fetchall()
    return [{"id": i, "nome": n, "cnpj": c} for i, n, c in linhas]


def criar_usuario(email: str, senha: str, empresa_id: str, nome: str = "", admin: bool = False) -> Usuario:
    email = validar_email(email)
    if len(senha) < SENHA_MIN:
        raise ValueError(f"a senha precisa de pelo menos {SENHA_MIN} caracteres")
    if buscar_empresa(empresa_id) is None:
        raise ValueError(f"empresa '{empresa_id}' não existe")
    uid = f"usr_{secrets.token_hex(6)}"
    try:
        with _lock, _conectar() as con:
            con.execute(
                "INSERT INTO usuarios (id, email, nome, senha_hash, empresa_id, admin, criado_em) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (uid, email, nome.strip(), hash_senha(senha), empresa_id, int(admin), _agora()),
            )
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"já existe uma conta com o e-mail {email}") from exc
    return buscar_usuario(email)  # type: ignore[return-value]


def buscar_usuario(email: str) -> Usuario | None:
    with _conectar() as con:
        return _usuario(con.execute(_SELECT_USUARIO + " WHERE u.email = ?", (normalizar_email(email),)).fetchone())


def listar_usuarios() -> list[dict]:
    with _conectar() as con:
        linhas = con.execute(
            "SELECT u.email, u.nome, e.id, e.nome, u.admin, u.ativo, u.criado_em FROM usuarios u JOIN empresas e ON e.id = u.empresa_id ORDER BY e.nome, u.email"
        ).fetchall()
    return [{"email": a, "nome": b, "empresa_id": c, "empresa": d, "admin": bool(e), "ativo": bool(f), "criado_em": g} for a, b, c, d, e, f, g in linhas]


def definir_senha(email: str, senha: str) -> None:
    """Troca a senha e encerra todas as sessões abertas do usuário."""
    if len(senha) < SENHA_MIN:
        raise ValueError(f"a senha precisa de pelo menos {SENHA_MIN} caracteres")
    u = buscar_usuario(email)
    if u is None:
        raise ValueError(f"não há conta com o e-mail {email}")
    with _lock, _conectar() as con:
        con.execute("UPDATE usuarios SET senha_hash = ? WHERE id = ?", (hash_senha(senha), u.id))
        con.execute("DELETE FROM sessoes WHERE usuario_id = ?", (u.id,))


def definir_ativo(email: str, ativo: bool) -> None:
    u = buscar_usuario(email)
    if u is None:
        raise ValueError(f"não há conta com o e-mail {email}")
    with _lock, _conectar() as con:
        con.execute("UPDATE usuarios SET ativo = ? WHERE id = ?", (int(ativo), u.id))
        if not ativo:
            con.execute("DELETE FROM sessoes WHERE usuario_id = ?", (u.id,))


def autenticar(email: str, senha: str) -> Usuario | None:
    with _conectar() as con:
        linha = con.execute("SELECT senha_hash, ativo FROM usuarios WHERE email = ?", (normalizar_email(email),)).fetchone()
    if linha is None:
        conferir_senha(senha, _HASH_FICTICIO)
        return None
    senha_hash, ativo = linha
    if not conferir_senha(senha, senha_hash) or not ativo:
        return None
    return buscar_usuario(email)


# ---------------------------------------------------------------------------- sessões


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def abrir_sessao(usuario: Usuario) -> str:
    token = secrets.token_urlsafe(32)
    agora = datetime.now()
    expira = agora + timedelta(hours=config.sessao_horas)
    with _lock, _conectar() as con:
        con.execute("DELETE FROM sessoes WHERE expira_em < ?", (agora.isoformat(timespec="seconds"),))
        con.execute(
            "INSERT INTO sessoes (token_hash, usuario_id, criada_em, expira_em) VALUES (?, ?, ?, ?)",
            (_hash_token(token), usuario.id, agora.isoformat(timespec="seconds"), expira.isoformat(timespec="seconds")),
        )
    return token


def usuario_da_sessao(token: str | None) -> Usuario | None:
    if not token:
        return None
    with _conectar() as con:
        linha = con.execute(
            _SELECT_USUARIO + " JOIN sessoes s ON s.usuario_id = u.id WHERE s.token_hash = ? AND s.expira_em > ? AND u.ativo = 1",
            (_hash_token(token), _agora()),
        ).fetchone()
    return _usuario(linha)


def encerrar_sessao(token: str | None) -> None:
    if not token:
        return
    with _lock, _conectar() as con:
        con.execute("DELETE FROM sessoes WHERE token_hash = ?", (_hash_token(token),))


# ---------------------------------------------------------------------------- convites e redefinição de senha
# O token só existe no link entregue a quem vai usá-lo; o banco guarda o hash, como nas sessões.


def listar_usuarios_da_empresa(empresa_id: str) -> list[dict]:
    with _conectar() as con:
        linhas = con.execute(
            "SELECT email, nome, admin, ativo, criado_em FROM usuarios WHERE empresa_id = ? ORDER BY email", (empresa_id,)
        ).fetchall()
    return [{"email": a, "nome": b, "admin": bool(c), "ativo": bool(d), "criado_em": e} for a, b, c, d, e in linhas]


def _criar_link(tipo: str, email: str, validade: timedelta, criado_por: str | None, empresa_id: str | None = None,
                empresa_nova: str | None = None, admin: bool = False) -> str:
    token = secrets.token_urlsafe(32)
    agora = datetime.now()
    with _lock, _conectar() as con:
        # Um link novo do mesmo tipo para o mesmo e-mail substitui o anterior ainda não usado
        con.execute("UPDATE links_conta SET usado_em = ? WHERE tipo = ? AND email = ? AND usado_em IS NULL", (_agora(), tipo, email))
        con.execute(
            "INSERT INTO links_conta (id, token_hash, tipo, email, empresa_id, empresa_nova, admin, criado_por, criado_em, expira_em)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"lnk_{secrets.token_hex(6)}", _hash_token(token), tipo, email, empresa_id, empresa_nova, int(admin), criado_por,
             agora.isoformat(timespec="seconds"), (agora + validade).isoformat(timespec="seconds")),
        )
    return token


def _link_valido(token: str, tipo: str) -> dict | None:
    with _conectar() as con:
        linha = con.execute(
            "SELECT l.id, l.email, l.empresa_id, e.nome, l.empresa_nova, l.admin FROM links_conta l LEFT JOIN empresas e ON e.id = l.empresa_id"
            " WHERE l.token_hash = ? AND l.tipo = ? AND l.usado_em IS NULL AND l.expira_em > ?",
            (_hash_token(token), tipo, _agora()),
        ).fetchone()
    if linha is None:
        return None
    lid, email, empresa_id, empresa_nome, empresa_nova, admin = linha
    return {"id": lid, "email": email, "empresa_id": empresa_id, "empresa": empresa_nome or empresa_nova, "admin": bool(admin)}


def _marcar_usado(link_id: str, con: sqlite3.Connection) -> bool:
    """Marca o link como usado; False se outro pedido já o usou (dois cliques ao mesmo tempo)."""
    return con.execute("UPDATE links_conta SET usado_em = ? WHERE id = ? AND usado_em IS NULL", (_agora(), link_id)).rowcount == 1


def criar_convite(email: str, por: Usuario, empresa_nova: str | None = None, admin: bool = False) -> str:
    """Convite para criar conta. Sem `empresa_nova`, para a empresa de quem convida; com ela (só administrador da
    plataforma), para uma empresa que é criada quando o convite é aceito. Devolve o token do link."""
    email = validar_email(email)
    if buscar_usuario(email):
        raise ValueError(f"já existe uma conta com o e-mail {email}")
    if (empresa_nova or admin) and not por.admin:
        raise PermissionError("só um administrador da plataforma convida outra empresa ou outro administrador")
    if empresa_nova is not None and not empresa_nova.strip():
        raise ValueError("informe o nome da empresa")
    return _criar_link("convite", email, VALIDADE_CONVITE, por.id, empresa_id=None if empresa_nova else por.empresa_id,
                       empresa_nova=empresa_nova.strip() if empresa_nova else None, admin=admin)


def ver_convite(token: str) -> dict | None:
    """E-mail e empresa de um convite válido (para a tela de aceite), ou None se expirou, foi usado ou não existe."""
    link = _link_valido(token, "convite")
    return {"email": link["email"], "empresa": link["empresa"]} if link else None


def aceitar_convite(token: str, senha: str, nome: str = "") -> Usuario:
    link = _link_valido(token, "convite")
    if link is None:
        raise ValueError("convite inválido ou expirado: peça um novo")
    if len(senha) < SENHA_MIN:
        raise ValueError(f"a senha precisa de pelo menos {SENHA_MIN} caracteres")
    if buscar_usuario(link["email"]):
        raise ValueError(f"já existe uma conta com o e-mail {link['email']}: entre com ela")
    with _lock, _conectar() as con:
        if not _marcar_usado(link["id"], con):
            raise ValueError("convite inválido ou expirado: peça um novo")
    try:
        empresa_id = link["empresa_id"] or criar_empresa(link["empresa"])
        return criar_usuario(link["email"], senha, empresa_id, nome, admin=link["admin"])
    except ValueError:
        with _lock, _conectar() as con:  # o convite não foi aproveitado: continua valendo
            con.execute("UPDATE links_conta SET usado_em = NULL WHERE id = ?", (link["id"],))
        raise


def convites_pendentes(empresa_id: str) -> list[dict]:
    with _conectar() as con:
        linhas = con.execute(
            "SELECT id, email, criado_em, expira_em FROM links_conta WHERE tipo = 'convite' AND empresa_id = ? AND usado_em IS NULL AND expira_em > ?"
            " ORDER BY criado_em DESC", (empresa_id, _agora()),
        ).fetchall()
    return [{"id": a, "email": b, "criado_em": c, "expira_em": d} for a, b, c, d in linhas]


def cancelar_convite(link_id: str, empresa_id: str) -> bool:
    with _lock, _conectar() as con:
        return con.execute(
            "UPDATE links_conta SET usado_em = ? WHERE id = ? AND tipo = 'convite' AND empresa_id = ? AND usado_em IS NULL",
            (_agora(), link_id, empresa_id),
        ).rowcount == 1


def criar_redefinicao(email: str, por: Usuario | None = None) -> str | None:
    """Link para escolher uma senha nova. None quando não há conta ativa com o e-mail: quem pede pela tela de login
    recebe a mesma resposta nos dois casos, para não descobrir quais e-mails têm conta."""
    with _conectar() as con:
        linha = con.execute("SELECT ativo FROM usuarios WHERE email = ?", (normalizar_email(email),)).fetchone()
    if linha is None or not linha[0]:
        return None
    return _criar_link("redefinicao", normalizar_email(email), VALIDADE_REDEFINICAO, por.id if por else None)


def redefinir_senha(token: str, senha: str) -> Usuario:
    """Troca a senha pelo link (que vale uma vez) e encerra as sessões abertas, como definir_senha."""
    link = _link_valido(token, "redefinicao")
    if link is None:
        raise ValueError("link inválido ou expirado: peça outro")
    if len(senha) < SENHA_MIN:
        raise ValueError(f"a senha precisa de pelo menos {SENHA_MIN} caracteres")
    with _lock, _conectar() as con:
        if not _marcar_usado(link["id"], con):
            raise ValueError("link inválido ou expirado: peça outro")
    definir_senha(link["email"], senha)
    return buscar_usuario(link["email"])  # type: ignore[return-value]
