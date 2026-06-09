import copy

from crypto_utils import (
    abrir_pacote_seguro,
    b64d,
    b64e,
    gerar_chaves,
    montar_pacote_seguro
)
from main import resolver_pergunta


def adulterar_base64(valor_b64: str) -> str:
    dados = bytearray(b64d(valor_b64))
    dados[0] ^= 0x01
    return b64e(bytes(dados))


def exigir_rejeicao(nome: str, pacote: dict, rsa_private, ecdsa_public):
    try:
        abrir_pacote_seguro(pacote, rsa_private, ecdsa_public)
    except Exception:
        print(f"[OK] {nome}: adulteração rejeitada")
        return

    raise AssertionError(f"{nome}: pacote adulterado foi aceito")


def testar_resolvedor():
    assert resolver_pergunta("Qual o valor de log2(4096)?") == "12"
    assert resolver_pergunta("Qual o valor de log2 (4096)?") == "12"
    assert resolver_pergunta("raiz quadrada de 144") == "12"
    assert resolver_pergunta("sqrt(144)") == "12"
    assert resolver_pergunta("log2(3)") is None
    assert resolver_pergunta("sqrt(2)") is None
    print("[OK] resolvedor aceita resultados exatos e rejeita truncamentos")


def testar_envelope_resposta():
    rsa_oraculo, _ = gerar_chaves()
    _, ecdsa_ut = gerar_chaves()
    resposta = "12"

    pacote = montar_pacote_seguro(
        id_unidade="ut-delta",
        mensagem=resposta,
        rsa_public_destino=rsa_oraculo.public_key(),
        ecdsa_private=ecdsa_ut,
        cmd="resposta"
    )

    assert pacote["cmd"] == "resposta"
    conteudo = abrir_pacote_seguro(
        pacote,
        rsa_oraculo,
        ecdsa_ut.public_key()
    )
    assert conteudo == resposta
    assert conteudo != '{"resposta": "12"}'
    print("[OK] resposta mantém cmd externo e cifra somente a string numérica")


def main():
    rsa_destino, _ = gerar_chaves()
    _, ecdsa_remetente = gerar_chaves()
    _, ecdsa_intruso = gerar_chaves()

    mensagem = "teste local da UT-Delta"
    pacote = montar_pacote_seguro(
        id_unidade="ut-delta",
        mensagem=mensagem,
        rsa_public_destino=rsa_destino.public_key(),
        ecdsa_private=ecdsa_remetente,
        cmd="teste_local"
    )

    mensagem_aberta = abrir_pacote_seguro(
        pacote,
        rsa_destino,
        ecdsa_remetente.public_key()
    )
    assert mensagem_aberta == mensagem
    print("[OK] geração de chaves, criação e abertura do pacote seguro")

    campos_adulterados = [
        ("ciphertext", "ciphertext_b64"),
        ("tag AES-GCM", "tag_autenticacao_b64"),
        ("nonce", "nonce_b64"),
        ("assinatura ECDSA", "assinatura_b64"),
        ("chave de sessão cifrada", "chave_sessao_cifrada_b64")
    ]

    for nome, campo in campos_adulterados:
        pacote_adulterado = copy.deepcopy(pacote)
        pacote_adulterado[campo] = adulterar_base64(pacote_adulterado[campo])
        exigir_rejeicao(
            nome,
            pacote_adulterado,
            rsa_destino,
            ecdsa_remetente.public_key()
        )

    exigir_rejeicao(
        "chave pública ECDSA incorreta",
        pacote,
        rsa_destino,
        ecdsa_intruso.public_key()
    )

    testar_resolvedor()
    testar_envelope_resposta()

    print("\nTodos os testes criptográficos locais passaram.")


if __name__ == "__main__":
    main()
