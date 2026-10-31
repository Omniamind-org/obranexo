"""Envio de e-mail transacional (convite, nova senha) por SMTP com STARTTLS. Opcional: sem OBRANEXO_SMTP_HOST,
nada é enviado e quem gerou o link o entrega por outro canal (a tela Equipe mostra o link para copiar)."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from obranexo.config import config
from obranexo.observability import logs


def configurado() -> bool:
    return bool(config.smtp_host and config.smtp_remetente)


def enviar(para: str, assunto: str, texto: str) -> bool:
    """True se o servidor SMTP aceitou a mensagem. Falha de envio não derruba quem pediu: o link continua válido."""
    if not configurado():
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = config.smtp_remetente, para, assunto
    msg.set_content(texto)
    try:
        with smtplib.SMTP(config.smtp_host, config.smtp_porta, timeout=15) as smtp:
            smtp.starttls()
            if config.smtp_usuario:
                smtp.login(config.smtp_usuario, config.smtp_senha or "")
            smtp.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        logs.registrar("email_falhou", logging.WARNING, para=para, erro=f"{type(exc).__name__}: {exc}"[:200])
        return False


def link(caminho: str) -> str:
    return f"{config.url_publica}/#/{caminho}"


def enviar_convite(para: str, empresa: str, token: str) -> bool:
    return enviar(para, f"Convite para o ObraNexo ({empresa})",
                  f"Você foi convidado para usar o ObraNexo pela empresa {empresa}.\n\n"
                  f"Para criar sua senha e entrar, abra o link abaixo (vale 7 dias, uma vez só):\n{link(f'convite/{token}')}\n\n"
                  "Se não esperava este convite, ignore esta mensagem.")


def enviar_redefinicao(para: str, token: str) -> bool:
    return enviar(para, "ObraNexo: escolha uma nova senha",
                  f"Recebemos um pedido para trocar a senha da conta {para} no ObraNexo.\n\n"
                  f"Para escolher a nova senha, abra o link abaixo (vale 1 hora, uma vez só):\n{link(f'redefinir/{token}')}\n\n"
                  "Se não foi você, ignore esta mensagem: a senha atual continua valendo.")
