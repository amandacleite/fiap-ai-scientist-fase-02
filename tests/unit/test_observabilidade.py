import json

from src.governance.observabilidade import MonitorExecucao


def test_manifesto_de_execucao(tmp_path):
    monitor = MonitorExecucao("teste", diretorio=tmp_path)
    monitor.registrar_tabela("municipios", 10, 2048)
    caminho = monitor.finalizar(True)
    payload = json.loads(caminho.read_text(encoding="utf-8"))
    assert payload["status"] == "SUCESSO"
    assert payload["total_linhas"] == 10
    assert payload["total_bytes"] == 2048
