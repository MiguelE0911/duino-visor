from duinovisor.ui import tema as T


def test_tema_mezclar_y_fuente():
    assert T.mezclar("#000000", "#ffffff", 0) == "#000000"
    assert T.mezclar("#000000", "#ffffff", 1) == "#ffffff"
    assert T.mezclar("#000000", "#ffffff", 0.5) == "#808080"
    assert T.mezclar("#102030", "#ffffff", 5) == "#ffffff"                 # f se limita a 0..1
    assert T.elegir_fuente(["Arial", "DejaVu Sans"]) == "DejaVu Sans"      # respeta el orden de preferencia
    assert T.elegir_fuente(["Comic Sans"]) == "Helvetica"
    assert T.elegir_fuente(["segoe ui"]) == "Segoe UI"


def test_tema_aplicar_paletas_y_acentos():
    try:
        T.aplicar("oscuro", "verde")
        assert T.FONDO == T.PALETAS["oscuro"]["FONDO"] and T.ACENTO == T.ACENTOS["verde"][2]
        T.aplicar("claro", "rosa")
        assert T.SUPERFICIE == "#ffffff" and T.ACENTO == T.ACENTOS["rosa"][1]
        T.aplicar("inventado", "nada")                                    # valores raros: los de por defecto
        assert (T.tema_actual, T.acento_actual) == (T.TEMA_POR_DEFECTO, T.ACENTO_POR_DEFECTO)
    finally:
        T.aplicar()
