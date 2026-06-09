import json
import os
import re
import math
import time
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

from crypto_utils import (
    b64d,
    b64e,
    gerar_chaves,
    salvar_chaves,
    carregar_chaves,
    exportar_publicas_base64,
    carregar_publica_rsa_b64,
    carregar_publica_ecdsa_b64,
    montar_pacote_seguro,
    abrir_pacote_seguro,
    assinar_objeto_json,
    verificar_assinatura_objeto_json
)


ID_UNIDADE = "ut-delta"
BROKER = "broker.hivemq.com"
PORTA = 1883

TOPICO_MINHA_UNIDADE = f"sisdef/direto/{ID_UNIDADE}"
TOPICO_ORACULO = "sisdef/direto/oraculo"
TOPICO_CHAVES = "sisdef/broadcast/chaves"
TOPICO_CHAVES_TODAS = "sisdef/broadcast/chaves/#"
TOPICO_REVOGACAO = "sisdef/broadcast/revogacao"
TOPICO_NOTAS = "sisdef/broadcast/notas"

ARQUIVO_CHAVES_CONFIADAS = "chaves_confiadas.json"
ARQUIVO_UNIDADES_REVOGADAS = "unidades_revogadas.json"

client = mqtt.Client()
chaves_confiadas = {}
unidades_revogadas = set()
rsa_private = None
ecdsa_private = None
desafio_pendente = False


def carregar_chaves_confiadas():
    global chaves_confiadas

    if not os.path.exists(ARQUIVO_CHAVES_CONFIADAS):
        chaves_confiadas = {}
        return

    with open(ARQUIVO_CHAVES_CONFIADAS, "r", encoding="utf-8") as f:
        chaves_confiadas = json.load(f)


def salvar_chaves_confiadas():
    with open(ARQUIVO_CHAVES_CONFIADAS, "w", encoding="utf-8") as f:
        json.dump(chaves_confiadas, f, indent=2)


def carregar_unidades_revogadas():
    global unidades_revogadas

    if not os.path.exists(ARQUIVO_UNIDADES_REVOGADAS):
        unidades_revogadas = set()
        return

    with open(ARQUIVO_UNIDADES_REVOGADAS, "r", encoding="utf-8") as f:
        dados = json.load(f)

    unidades_revogadas = {
        unidade.lower()
        for unidade in dados.get("unidades_revogadas", [])
        if isinstance(unidade, str)
    }


def salvar_unidades_revogadas():
    dados = {
        "unidades_revogadas": sorted(unidades_revogadas)
    }

    with open(ARQUIVO_UNIDADES_REVOGADAS, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2)


def aplicar_revogacao(id_revogada: str):
    id_revogada = id_revogada.lower()
    unidades_revogadas.add(id_revogada)
    salvar_unidades_revogadas()

    if id_revogada in chaves_confiadas:
        del chaves_confiadas[id_revogada]
        salvar_chaves_confiadas()
        print(f"\nUnidade revogada removida das chaves confiadas: {id_revogada}")
    else:
        print(f"\nUnidade adicionada à lista de revogadas: {id_revogada}")


def resolver_pergunta(pergunta: str):
    texto = pergunta.lower()
    print(f"\nPergunta recebida: {pergunta}")

    # log2(8192), log2 (8192), etc.
    match = re.search(r"log2\s*\(\s*(\d+)\s*\)", texto)
    if match:
        n = int(match.group(1))
        if n > 0 and n & (n - 1) == 0:
            return str(n.bit_length() - 1)
        print("\nO log2 encontrado não tem resultado inteiro exato.")
        print("Resposta NÃO enviada para evitar erro.")
        return None

    # raiz quadrada de 144, sqrt(144), etc.
    match = re.search(
        r"(?:raiz quadrada de\s*(\d+)|sqrt\s*\(\s*(\d+)\s*\))",
        texto
    )
    if match:
        n = int(match.group(1) or match.group(2))
        raiz = math.isqrt(n)
        if raiz * raiz == n:
            return str(raiz)
        print("\nA raiz quadrada encontrada não tem resultado inteiro exato.")
        print("Resposta NÃO enviada para evitar erro.")
        return None

    # 10 + 5, 20 - 3, 7 * 8, 100 / 4
    match = re.search(r"(-?\d+)\s*([\+\-\*/])\s*(-?\d+)", texto)
    if match:
        a = int(match.group(1))
        op = match.group(2)
        b = int(match.group(3))

        if op == "+":
            return str(a + b)

        if op == "-":
            return str(a - b)

        if op == "*":
            return str(a * b)

        if op == "/":
            if b == 0:
                print("\nDivisão por zero não pode ser resolvida.")
                print("Resposta NÃO enviada para evitar erro.")
                return None
            resultado = a / b
            if resultado.is_integer():
                return str(int(resultado))
            return str(resultado)

    print("\nNão consegui resolver automaticamente.")
    print("Resposta NÃO enviada para evitar erro.")
    return None


def publicar_identidade():
    global rsa_private, ecdsa_private

    rsa_public_b64, ecdsa_public_b64 = exportar_publicas_base64(
        rsa_private,
        ecdsa_private
    )

    pacote = {
        "id_unidade": ID_UNIDADE,
        "chave_publica_rsa": rsa_public_b64,
        "chave_publica_ecdsa": ecdsa_public_b64
    }

    topico = f"{TOPICO_CHAVES}/{ID_UNIDADE}"
    resultado = client.publish(topico, json.dumps(pacote), retain=True)

    print(f"\nIdentidade publicada em: {topico}")
    print("Status publish:", resultado.rc)


def solicitar_desafio():
    global desafio_pendente

    pacote = {
        "id_unidade": ID_UNIDADE,
        "cmd": "desafio"
    }

    desafio_pendente = True
    resultado = client.publish(TOPICO_ORACULO, json.dumps(pacote))

    print("\nDesafio solicitado ao Oráculo.")
    print("Status publish:", resultado.rc)


def enviar_echo_oraculo():
    enviar_mensagem_segura("oraculo", "echo-ut-delta", cmd="echo")


def enviar_resposta_oraculo(resposta: str):
    enviar_mensagem_segura("oraculo", resposta, cmd="resposta")


def enviar_mensagem_segura(destino: str, mensagem: str, cmd=None):
    global rsa_private, ecdsa_private

    destino = destino.lower()

    if destino not in chaves_confiadas:
        print(f"\nNão tenho chave pública de {destino}.")
        print("Espere a unidade publicar a chave ou confira o chaves_confiadas.json.")
        return

    dados_destino = chaves_confiadas[destino]

    rsa_public_destino = carregar_publica_rsa_b64(
        dados_destino["chave_publica_rsa"]
    )

    pacote = montar_pacote_seguro(
        id_unidade=ID_UNIDADE,
        mensagem=mensagem,
        rsa_public_destino=rsa_public_destino,
        ecdsa_private=ecdsa_private,
        cmd=cmd
    )

    if destino == "oraculo":
        topico = TOPICO_ORACULO
    else:
        topico = f"sisdef/direto/{destino}"

    resultado = client.publish(topico, json.dumps(pacote))

    print(f"\nMensagem segura enviada para {destino}.")
    print(f"Tópico: {topico}")
    print("Status publish:", resultado.rc)


def processar_chave_publica(payload: dict):
    id_remetente = payload.get("id_unidade")

    if not id_remetente:
        return

    id_remetente = id_remetente.lower()

    if id_remetente in unidades_revogadas:
        print(f"\nChave ignorada: {id_remetente} está na lista de unidades revogadas.")
        return

    if "chave_publica_rsa" not in payload:
        return

    chave_ecdsa = payload.get("chave_publica_ecdsa")

    # Algumas equipes publicaram como chave_publica_eddsa,
    # mas o conteúdo é uma chave ECDSA secp256r1.
    if chave_ecdsa is None:
        chave_ecdsa = payload.get("chave_publica_eddsa")

    if chave_ecdsa is None:
        print(f"\nChave de assinatura ausente para {id_remetente}.")
        return

    chaves_confiadas[id_remetente] = {
        "chave_publica_rsa": payload["chave_publica_rsa"],
        "chave_publica_ecdsa": chave_ecdsa
    }

    salvar_chaves_confiadas()

    print(f"\nChave pública recebida/salva: {id_remetente}")


def processar_revogacao(payload: dict):
    revogacao = payload.get("revogacao")
    assinatura_b64 = payload.get("assinatura_b64")
    remetente = payload.get("remetente")

    if (
        isinstance(revogacao, dict)
        and isinstance(assinatura_b64, str)
        and isinstance(remetente, str)
    ):
        remetente = remetente.lower()
        id_revogada = revogacao.get("unidade_revogada")
        timestamp = revogacao.get("timestamp")

        if not isinstance(id_revogada, str) or not isinstance(timestamp, str):
            print("\nRevogação assinada rejeitada: campos obrigatórios inválidos.")
            return

        if remetente == ID_UNIDADE:
            ecdsa_public_remetente = ecdsa_private.public_key()
        elif remetente in chaves_confiadas:
            ecdsa_public_remetente = carregar_publica_ecdsa_b64(
                chaves_confiadas[remetente]["chave_publica_ecdsa"]
            )
        else:
            print(
                f"\nRevogação assinada rejeitada: "
                f"chave pública de {remetente} não é confiada."
            )
            return

        try:
            assinatura = b64d(assinatura_b64)
        except Exception:
            print("\nRevogação assinada rejeitada: assinatura Base64 inválida.")
            return

        if not verificar_assinatura_objeto_json(
            revogacao,
            assinatura,
            ecdsa_public_remetente
        ):
            print("\nRevogação assinada rejeitada: assinatura ECDSA inválida.")
            return

        aplicar_revogacao(id_revogada)
        print(
            f"Revogação assinada por {remetente} validada "
            f"(timestamp: {timestamp})."
        )
        return

    # Compatibilidade com o formato simples já usado no laboratório.
    id_revogada = payload.get("id_unidade")

    if not isinstance(id_revogada, str) or not id_revogada:
        print("\nRevogação rejeitada: formato não reconhecido.")
        return

    aplicar_revogacao(id_revogada)
    print("Aviso: revogação simples aplicada sem validação de assinatura.")


def processar_mensagem_direta(payload: dict):
    global rsa_private, desafio_pendente

    remetente = payload.get("id_unidade")

    if not remetente:
        print("\nMensagem direta sem id_unidade.")
        return

    remetente = remetente.lower()

    if remetente == ID_UNIDADE:
        return

    if remetente in unidades_revogadas:
        print(f"\nMensagem rejeitada: {remetente} está revogada.")
        return

    if remetente not in chaves_confiadas:
        print(f"\nRecebi mensagem de {remetente}, mas não tenho a chave pública ECDSA dele.")
        print("Não vou abrir a mensagem.")
        return

    try:
        ecdsa_public_remetente = carregar_publica_ecdsa_b64(
            chaves_confiadas[remetente]["chave_publica_ecdsa"]
        )

        mensagem = abrir_pacote_seguro(
            pacote=payload,
            rsa_private=rsa_private,
            ecdsa_public_remetente=ecdsa_public_remetente
        )

        print("\nMensagem segura recebida.")
        print(f"Remetente: {remetente}")
        print(f"Conteúdo: {mensagem}")

        if remetente == "oraculo":
            texto = mensagem.lower()

            # Echo do Oráculo: só confirma funcionamento.
            if "oraculo esta operante" in texto or "suas chaves foram recebidas" in texto:
                print("\nEcho do Oráculo recebido com sucesso.")
                print("O Oráculo confirmou que está operante e que recebeu suas chaves.")
                return

            if not desafio_pendente:
                print(
                    "\nMensagem segura do Oráculo recebida fora de um "
                    "desafio pendente. Não respondi automaticamente."
                )
                return

            # Desafio real: calcula e envia automaticamente uma única resposta.
            try:
                resposta = resolver_pergunta(mensagem)
            finally:
                desafio_pendente = False

            if resposta is None:
                print("\nNão enviei resposta porque não consegui calcular automaticamente.")
                return

            print(f"Resposta calculada: {resposta}")

            enviar_resposta_oraculo(resposta)

            print("\nResposta enviada automaticamente ao Oráculo.")
            return

    except Exception as e:
        print("\nErro ao processar mensagem segura.")
        print(f"Detalhe: {e}")


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("\nConectado ao MQTT.")

        client.subscribe(TOPICO_MINHA_UNIDADE)
        client.subscribe(TOPICO_CHAVES_TODAS)
        client.subscribe(TOPICO_REVOGACAO)
        client.subscribe(TOPICO_NOTAS)

        print(f"Inscrito em: {TOPICO_MINHA_UNIDADE}")
        print(f"Inscrito em: {TOPICO_CHAVES_TODAS}")
        print(f"Inscrito em: {TOPICO_REVOGACAO}")
        print(f"Inscrito em: {TOPICO_NOTAS}")
    else:
        print(f"Erro ao conectar. Código: {rc}")


def on_message(client, userdata, msg):
    print("\n=== MENSAGEM MQTT RECEBIDA ===")
    print("Tópico:", msg.topic)
    print("Payload bruto:", msg.payload.decode("utf-8", errors="ignore"))

    try:
        texto = msg.payload.decode("utf-8")

        if not texto:
            print("Payload vazio.")
            return

        payload = json.loads(texto)

    except Exception as e:
        print("\nMensagem recebida, mas não era JSON válido.")
        print("Erro:", e)
        return

    topico = msg.topic

    if topico.startswith(TOPICO_CHAVES + "/"):
        print("Tipo detectado: chave pública")
        processar_chave_publica(payload)
        return

    if topico == TOPICO_REVOGACAO:
        print("Tipo detectado: revogação")
        processar_revogacao(payload)
        return

    if topico == TOPICO_NOTAS:
        print("Tipo detectado: notas")
        print("\nPlacar recebido:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    if topico == TOPICO_MINHA_UNIDADE:
        print("Tipo detectado: mensagem direta para UT-Delta")
        processar_mensagem_direta(payload)
        return

    print("Mensagem recebida em tópico não tratado.")


def gerar_minhas_chaves():
    global rsa_private, ecdsa_private

    rsa_private, ecdsa_private = gerar_chaves()
    salvar_chaves(rsa_private, ecdsa_private)

    print("\nChaves geradas e salvas em minhas_chaves.json.")
    print("As chaves em memória também foram atualizadas.")
    print("Agora publique a identidade novamente usando a opção 2.")


def revogar_unidade():
    id_revogada = input("ID da unidade a revogar: ").strip().lower()

    if not id_revogada:
        print("\nRevogação cancelada: informe uma unidade.")
        return

    revogacao = {
        "unidade_revogada": id_revogada,
        "timestamp": datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        ).replace("+00:00", "Z")
    }

    pacote = {
        "remetente": ID_UNIDADE,
        "revogacao": revogacao,
        "assinatura_b64": b64e(
            assinar_objeto_json(revogacao, ecdsa_private)
        )
    }

    print("\nRevogação assinada preparada:")
    print(json.dumps(pacote, indent=2, ensure_ascii=False))

    confirmacao = input(
        f"Publicar em {TOPICO_REVOGACAO}? [s/N]: "
    ).strip().lower()

    if confirmacao not in {"s", "sim"}:
        print("\nPublicação cancelada. Nenhuma mensagem MQTT foi enviada.")
        return

    resultado = client.publish(TOPICO_REVOGACAO, json.dumps(pacote))

    print(f"\nRevogação assinada publicada para: {id_revogada}")
    print("Status publish:", resultado.rc)


def consultar_notas():
    pacote = {
        "cmd": "atualizar_notas"
    }

    resultado = client.publish(TOPICO_NOTAS, json.dumps(pacote))

    print("\nSolicitação de atualização de notas enviada.")
    print("Status publish:", resultado.rc)


def listar_chaves():
    print("\nChaves confiadas:")

    if not chaves_confiadas:
        print("Nenhuma chave salva ainda.")
    else:
        for unidade in sorted(chaves_confiadas.keys()):
            print(f"- {unidade}")

    if unidades_revogadas:
        print("\nUnidades revogadas:")
        for unidade in sorted(unidades_revogadas):
            print(f"- {unidade}")
    else:
        print("\nNenhuma unidade revogada.")


def menu():
    while True:
        print("\n========== UT-DELTA ==========")
        print("1 - Gerar minhas chaves")
        print("2 - Publicar identidade")
        print("3 - Enviar echo criptografado para o Oráculo")
        print("4 - Solicitar desafio ao Oráculo")
        print("5 - Enviar mensagem para outra UT")
        print("6 - Listar chaves confiadas")
        print("7 - Revogar unidade")
        print("8 - Consultar notas")
        print("9 - Sair")

        opcao = input("Escolha: ").strip()

        if opcao == "1":
            gerar_minhas_chaves()

        elif opcao == "2":
            publicar_identidade()

        elif opcao == "3":
            enviar_echo_oraculo()

        elif opcao == "4":
            solicitar_desafio()

        elif opcao == "5":
            destino = input("Destino, ex: ut-alfa: ").strip().lower()
            mensagem = input("Mensagem: ")
            enviar_mensagem_segura(destino, mensagem)

        elif opcao == "6":
            listar_chaves()

        elif opcao == "7":
            revogar_unidade()

        elif opcao == "8":
            consultar_notas()

        elif opcao == "9":
            print("Saindo...")
            client.loop_stop()
            client.disconnect()
            break

        else:
            print("Opção inválida.")


def iniciar():
    global rsa_private, ecdsa_private

    carregar_chaves_confiadas()
    carregar_unidades_revogadas()

    if not os.path.exists("minhas_chaves.json"):
        print("Arquivo minhas_chaves.json não encontrado.")
        print("Gerando chaves automaticamente...")
        gerar_minhas_chaves()

    rsa_private, ecdsa_private = carregar_chaves()

    client.on_connect = on_connect
    client.on_message = on_message

    print("Conectando ao broker MQTT...")
    client.connect(BROKER, PORTA, 60)

    client.loop_start()

    time.sleep(1)

    menu()


if __name__ == "__main__":
    iniciar()
