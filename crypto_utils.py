import base64
import json
import os
from cryptography.hazmat.primitives.asymmetric import rsa, padding, ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidSignature


def b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def b64d(data: str) -> bytes:
    return base64.b64decode(data.encode("utf-8"))


def gerar_chaves():
    rsa_private = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )

    ecdsa_private = ec.generate_private_key(ec.SECP256R1())

    return rsa_private, ecdsa_private


def salvar_chaves(rsa_private, ecdsa_private, caminho="minhas_chaves.json"):
    rsa_private_der = rsa_private.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    ecdsa_private_der = ecdsa_private.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    dados = {
        "rsa_private_der_b64": b64e(rsa_private_der),
        "ecdsa_private_der_b64": b64e(ecdsa_private_der)
    }

    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2)


def carregar_chaves(caminho="minhas_chaves.json"):
    with open(caminho, "r", encoding="utf-8") as f:
        dados = json.load(f)

    rsa_private = serialization.load_der_private_key(
        b64d(dados["rsa_private_der_b64"]),
        password=None
    )

    ecdsa_private = serialization.load_der_private_key(
        b64d(dados["ecdsa_private_der_b64"]),
        password=None
    )

    return rsa_private, ecdsa_private


def exportar_publicas_base64(rsa_private, ecdsa_private):
    rsa_public_der = rsa_private.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    ecdsa_public_der = ecdsa_private.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    return b64e(rsa_public_der), b64e(ecdsa_public_der)


def carregar_publica_rsa_b64(chave_b64: str):
    return serialization.load_der_public_key(b64d(chave_b64))


def carregar_publica_ecdsa_b64(chave_b64: str):
    return serialization.load_der_public_key(b64d(chave_b64))


def cifrar_chave_sessao(chave_aes: bytes, rsa_public):
    return rsa_public.encrypt(
        chave_aes,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )


def decifrar_chave_sessao(chave_sessao_cifrada: bytes, rsa_private):
    return rsa_private.decrypt(
        chave_sessao_cifrada,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )


def assinar_mensagem(mensagem: str, ecdsa_private):
    return ecdsa_private.sign(
        mensagem.encode("utf-8"),
        ec.ECDSA(hashes.SHA256())
    )


def verificar_assinatura(mensagem: str, assinatura: bytes, ecdsa_public) -> bool:
    try:
        ecdsa_public.verify(
            assinatura,
            mensagem.encode("utf-8"),
            ec.ECDSA(hashes.SHA256())
        )
        return True
    except InvalidSignature:
        return False


def montar_pacote_seguro(id_unidade: str, mensagem: str, rsa_public_destino, ecdsa_private, cmd=None):
    chave_aes = AESGCM.generate_key(bit_length=256)
    aesgcm = AESGCM(chave_aes)

    nonce = os.urandom(12)

    cifrado_com_tag = aesgcm.encrypt(
        nonce,
        mensagem.encode("utf-8"),
        associated_data=None
    )

    ciphertext = cifrado_com_tag[:-16]
    tag = cifrado_com_tag[-16:]

    chave_sessao_cifrada = cifrar_chave_sessao(chave_aes, rsa_public_destino)
    assinatura = assinar_mensagem(mensagem, ecdsa_private)

    pacote = {
        "id_unidade": id_unidade,
        "ciphertext_b64": b64e(ciphertext),
        "tag_autenticacao_b64": b64e(tag),
        "nonce_b64": b64e(nonce),
        "chave_sessao_cifrada_b64": b64e(chave_sessao_cifrada),
        "assinatura_b64": b64e(assinatura)
    }

    if cmd is not None:
        pacote["cmd"] = cmd

    return pacote


def abrir_pacote_seguro(pacote: dict, rsa_private, ecdsa_public_remetente):
    chave_sessao_cifrada = b64d(pacote["chave_sessao_cifrada_b64"])
    chave_aes = decifrar_chave_sessao(chave_sessao_cifrada, rsa_private)

    ciphertext = b64d(pacote["ciphertext_b64"])
    tag = b64d(pacote["tag_autenticacao_b64"])
    nonce = b64d(pacote["nonce_b64"])

    aesgcm = AESGCM(chave_aes)

    mensagem_bytes = aesgcm.decrypt(
        nonce,
        ciphertext + tag,
        associated_data=None
    )

    mensagem = mensagem_bytes.decode("utf-8")

    assinatura = b64d(pacote["assinatura_b64"])

    assinatura_valida = verificar_assinatura(
        mensagem,
        assinatura,
        ecdsa_public_remetente
    )

    if not assinatura_valida:
        raise ValueError("Assinatura inválida.")

    return mensagem