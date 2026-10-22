"""Smoke test da interface Streamlit: cada página renderiza sem exceção (modo determinístico, casos congelados)."""

from pathlib import Path

import pytest

from obranexo.config import config

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"


@pytest.mark.skipif(not (config.dir_casos / "goianira_pe038_2026" / "contratacao.json").exists(), reason="caso congelado ausente")
def test_paginas_renderizam():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP), default_timeout=120).run()
    assert not at.exception, at.exception
    for pagina in ["Demandas", "Análise", "Dossiê", "Métricas", "Como funciona"]:
        at.sidebar.radio[0].set_value(pagina).run()
        assert not at.exception, f"{pagina}: {at.exception}"


@pytest.mark.skipif(not (config.dir_casos / "goianira_pe038_2026" / "contratacao.json").exists(), reason="caso congelado ausente")
def test_analise_pela_interface(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(config, "dir_analises", tmp_path)
    monkeypatch.setattr(config, "llm_provider", None)  # smoke test da UI roda sem LLM (rápido e sem cota)
    at = AppTest.from_file(str(APP), default_timeout=180).run()
    at.sidebar.radio[0].set_value("Análise").run()
    assert not at.exception
    at.selectbox[0].select("goianira_pe038_2026").run()
    at.button[0].click().run()
    assert not at.exception, at.exception
    assert any("Prioridade" in m.label for m in at.metric), "métricas da análise não apareceram"
