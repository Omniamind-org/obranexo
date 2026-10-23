"""Regressão com descrições REAIS do teste cego (pregões abertos no PNCP em 23/10/2026).

Cada caso aqui foi um erro encontrado rodando o sistema em editais que ele nunca tinha visto.
"""

import pytest

from obranexo.models import Operador
from obranexo.rules.extrair import extrair_requisitos, inferir_categoria


def _req(descricao):
    return {r.atributo: r for r in extrair_requisitos(descricao)}


# ------------------------------------------------------------ categoria pelo núcleo da descrição

@pytest.mark.parametrize(
    ("descricao", "esperada"),
    [
        # Acessórios que citam o produto principal: antes viravam luminária e casavam com uma luminária do catálogo
        ("SUPORTE PARA 1 PÉTALA PARA LUMINÁRIA DE ILUMINAÇÃO PÚBLICA", "outro"),
        ("BRAÇO PARA ILUMINAÇÃO PÚBLICA, COM 1,50 METRO DE COMPRIMENTO, RETO, CONFECCIONADO EM AÇO CARBONO GALVANIZADO, "
         "PRÓPRIO PARA FIXAÇÃO DE LUMINÁRIAS EM POSTES.", "braco_luminaria"),
        ("ADAPTADOR PORCELANA E40 PARA E27", "outro"),
        ("GRAMPO METALICO TIPO U PARA HASTE DE ATERRAMENTO DE ATE 5/8\", CONDUTOR 6 A 35 MM2", "outro"),
        ("Espaçador De Cabos Espaçador De Cabos, Material:Polimérico, Tipo:Losangular", "outro"),
        ("Passa Fio material: pvc, comprimento: 10, aplicação: passagem cabo/fio", "outro"),
        # Produtos principais continuam corretos
        ("Luminária para iluminação pública a LED potência máxima de 50W", "luminaria_publica_led"),
        ("LUMINÁRIA PÚBLICA LED 100 WTS, POTÊNCIA 100 WTS", "luminaria_publica_led"),
        ("Plafonier Plafonier, Material Corpo:Pvc, Cor:Branca, Base E-27.", "luminaria_interna"),
        ("PROJETOR DE LED 100W PARA ÁREA EXTERNA, TENSÃO BIVOLT", "refletor_led"),
        ("REFLETOR LED MODULAR PROFISSIONAL PARA ILUMINAÇÃO DE ESTÁDIOS", "refletor_led"),
        ("Relé Fotoelétrico Térmico 220 V", "rele_fotoeletrico"),
        ("CABO DE COBRE, FLEXIVEL, CLASSE 4 OU 5, ISOLACAO EM PVC/A, SECAO NOMINAL 10 MM2", "cabo"),
        ("ELETRODUTO/DUTO PEAD FLEXIVEL PAREDE SIMPLES, CORRUGACAO HELICOIDAL", "eletroduto"),
        ("KIT PAINEL DE LED", "luminaria_interna"),
        ("POSTE DE AÇO REDONDO GALVANIZADO 7 M.", "poste"),
    ],
)
def test_categoria_pelo_nucleo(descricao, esperada):
    assert inferir_categoria(descricao) == esperada


# ------------------------------------------------------------ formato CATMAT (rótulo: valor, sem unidade)

def test_cabo_catmat_secao_sem_unidade():
    d = ("Cabo Elétrico Flexível tipo: tripolar chato, cor da cobertura: preta, tensão isolamento: 750, seção nominal: 16, "
         "material do condutor: cobre eletrolítico, bitola: 16,0, normas técnicas: nbr 7288")
    assert _req(d)["secao_mm2"].valor == 16
    d2 = "Cabo Elétrico Isolado material condutor: cobre nu, têmpera condutor: mole, seção nominal: 2,5, tensão isolamento: 750"
    r2 = _req(d2)
    assert r2["secao_mm2"].valor == 2.5
    assert "tensao_v" not in r2  # 750 é tensão de isolamento, não de alimentação


def test_refletor_catmat_sem_unidades():
    d = ("Refletor material corpo: alumínio, material refletor: vidro, formato: retangular, tipo lâmpada: led, potência lâmpada: 100, "
         "tensão alimentação: 110/220, grau proteção: ip-67, ângulo de abertura da lente: 120°, fluxo luminoso: 2.700, "
         "eficiência luminosa: ~27, índice de reprodução de cor - irc: ≥ 70, temperatura de cor: 6.500")
    r = _req(d)
    assert r["potencia_w"].valor == 100
    assert r["tensao_v"].valor == [110.0, 220.0]
    assert r["fluxo_lm"].valor == 2700
    assert r["eficiencia_lm_w"].valor == 27
    assert r["irc"].valor == 70 and r["irc"].operador == Operador.MAIOR_IGUAL
    assert r["cct_k"].valor == 6500
    assert r["ip"].valor == "IP67"


# ------------------------------------------------------------ separadores e faixas

def test_refletor_500w_separadores():
    d = ("REFLETOR MODULAR LED 500W, POTÊNCIA: 500W, TEMPERATURA DE COR: 5.500K, TENSÃO DE FUNCIONAMENTO: 85V~265V, "
         "FREQUÊNCIA: 50/60HZ, EFICIÊNCIA LUMINOSA: 165LM/W, FLUXO LUMINOSO: 82.500 LÚMENS, ÂNGULO DE ABERTURA: 90°, "
         "FATOR DE POTÊNCIA: > 0,99, ÍNDICE DE REPRODUÇÃO DE COR: >80, TEMPERATURA DE FUNCIONAMENTO: -10°C A +40°C, "
         "ÍNDICE DE PROTEÇÃO: IP-66, PROTETOR SURTO: 6KV, VIDA ÚTIL: 70.000 HORAS.")
    r = _req(d)
    assert r["tensao_v"].valor == [85.0, 265.0]
    assert r["fator_potencia"].valor == 0.99 and r["fator_potencia"].operador == Operador.MAIOR_IGUAL
    assert r["irc"].valor == 80 and r["irc"].operador == Operador.MAIOR_IGUAL
    assert r["cct_k"].valor == 5500
    assert r["fluxo_lm"].valor == 82500
    assert r["eficiencia_lm_w"].valor == 165


def test_faixa_de_temperatura_de_cor():
    d = "PROJETOR DE LED 100W PARA ÁREA EXTERNA, TENSÃO BIVOLT, TEMPERATURA DE COR DE 4000K A 5000K, FLUXO LUMINOSO MÍNIMO DE 14.000 LUMENS"
    r = _req(d)
    assert r["cct_k"].valor == [4000.0, 5000.0] and r["cct_k"].operador == Operador.ENTRE


@pytest.mark.parametrize(
    ("descricao", "tipo"),
    [
        ("Cabo Elétrico Flexível tipo: fotovoltaico unifilar, aplicação: instalação solar, seção nominal: 6", "fotovoltaico"),
        ("CABO ISOLADO PP 3 X 2,5 MM2", "pp"),
        ("CABO DE COBRE NU 35 MM2 MEIO-DURO", "nu"),
        ("Cabo Lógico Blindado, Aplicação:Para Rede Cat6e", "logico"),
        # CATMAT: "cobre nu" é o material do condutor de um cabo ISOLADO — não é cabo nu
        ("Cabo Elétrico Isolado material condutor: cobre nu, seção nominal: 2,5, material isolamento condutor: termoplástico de pvc", None),
        ("CABO DE COBRE, FLEXIVEL, CLASSE 4 OU 5, ISOLACAO EM PVC/A, SECAO NOMINAL 10 MM2", None),
        # Não é cabo: "condutor" só aparece no meio
        ("GRAMPO METALICO TIPO U PARA HASTE DE ATERRAMENTO, CONDUTOR SOLAR", None),
    ],
)
def test_tipo_de_cabo(descricao, tipo):
    r = _req(descricao)
    assert (r["tipo_cabo"].valor if "tipo_cabo" in r else None) == tipo


def test_cabo_solar_nao_casa_com_cabo_predial():
    from obranexo.catalog.loader import produto_de_dict
    from obranexo.models import Requisito, ResultadoItem
    from obranexo.rules.compare import comparar_item

    predial = produto_de_dict({"sku": "CB-6", "nome": "Cabo 6", "categoria": "cabo", "atributos": {"secao_mm2": 6, "tipo_cabo": "flexivel isolado PVC 750V (cabinho)"}})
    pp = produto_de_dict({"sku": "CB-PP", "nome": "PP", "categoria": "cabo", "atributos": {"secao_mm2": 2.5, "tipo_cabo": "PP flexivel multipolar"}})

    def reqs(desc):
        return [Requisito(id=f"r{i}", item_id="i", atributo=b.atributo, operador=b.operador, valor=b.valor, obrigatorio=b.obrigatorio)
                for i, b in enumerate(extrair_requisitos(desc))]

    solar = reqs("Cabo Elétrico Flexível tipo: fotovoltaico unifilar, seção nominal: 6")
    assert comparar_item(solar, predial)[0] == ResultadoItem.INCOMPATIVEL
    cabo_pp = reqs("CABO ISOLADO PP 3 X 2,5 MM2")
    assert comparar_item(cabo_pp, pp)[0] == ResultadoItem.COMPATIVEL


def test_item_sem_especificacao_tecnica_nao_vira_compativel(tmp_path, monkeypatch):
    """Só cláusulas gerais do edital (garantia, prazo) não provam compatibilidade."""
    from obranexo.agents.contexto import Contexto
    from obranexo.agents.pipeline import _casar
    from obranexo.catalog.loader import produto_de_dict
    from obranexo.config import Config
    from obranexo.documents.extract import IndiceDocumentos
    from obranexo.llm.client import criar_llm_client
    from obranexo.models import Analise, Contratacao, Empresa, ItemDemanda, Requisito, ResultadoItem

    cfg = Config(llm_provider=None, gemini_api_key=None, anthropic_api_key=None)
    item = ItemDemanda(id="c#1", contratacao_id="c", numero_item=1, descricao="Plafonier, Cor: Branca", categoria_inferida="luminaria_interna")
    analise = Analise(id="t", empresa_id="e", contratacao=Contratacao(id="c", orgao_cnpj="0", orgao_nome="O", ano=2026, sequencial=1, objeto="x"), itens=[item])
    analise.requisitos.append(Requisito(id="r1", item_id="c#1", atributo="garantia_anos", operador=Operador.MAIOR_IGUAL, valor=1, fonte_extracao="investigador"))
    empresa = Empresa(id="e", nome="E", produtos=[produto_de_dict({"sku": "PLF", "nome": "Plafon", "categoria": "luminaria_interna", "atributos": {"garantia_anos": 2}})])
    ctx = Contexto(analise=analise, empresa=empresa, indice=IndiceDocumentos(), llm=criar_llm_client(cfg), cfg=cfg)
    _casar(ctx, [item])
    corr = analise.correspondencias[0]
    assert corr.resultado == ResultadoItem.INDETERMINADO
    assert corr.observacoes and "especificação técnica" in corr.observacoes[0]
