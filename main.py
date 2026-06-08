import json
import os
import re
import math
import time
import paho.mqtt.client as mqtt

from crypto_utils import (
    gerar_chaves,
    salvar_chaves,
    carregar_chaves,
    exportar_publicas_base64,
    carregar_publica_rsa_b64,
    carregar_publica_ecdsa_b64,
    montar_pacote_seguro,
    abrir_pacote_seguro
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

client = mqtt.Client()
chaves_confiadas = {}
rsa_private = None
ecdsa_private = None


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


def resolver_pergunta(pergunta: str):
    texto = pergunta.lower()
    print(f"\nPergunta recebida: {pergunta}")

    # Exemplo: log2(4096) ou log2 (4096)
    match = re.search(r"log2\s*\(\s*(\d+)\s*\)", texto)
    if match:
        n = int(match.group(1))
        return str(int(math.log2(n)))

    # Exemplo: raiz quadrada de 144
    match = re.search(r"raiz quadrada de\s*(\d+)", texto)
    if match:
        n = int(match.group(1))
        return str(int(math.sqrt(n)))

    # Exemplo: 10 + 5, 20 - 3, 7 * 8, 100 / 4
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
            resultado = a / b
            if resultado.is_integer():
                return str(int(resultado))
            return str(resultado)

    print("Não consegui resolver automaticamente.")
    resposta = input("Digite apenas o número da resposta: ").strip()
    return resposta


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

    client.publish(topico, json.dumps(pacote), retain=True)

    print(f"\nIdentidade publicada em: {topico}")


def solicitar_desafio():
    pacote = {
        "id_unidade": ID_UNIDADE,
        "cmd": "desafio"
    }

    client.publish(TOPICO_ORACULO, json.dumps(pacote))
    print("\nDesafio solicitado ao Oráculo.")


def enviar_echo_oraculo():
    enviar_mensagem_segura("oraculo", "teste", cmd="echo")


def enviar_resposta_oraculo(resposta: str):
    enviar_mensagem_segura("oraculo", resposta, cmd="resposta")


def enviar_mensagem_segura(destino: str, mensagem: str, cmd=None):
    global rsa_private, ecdsa_private

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

    client.publish(topico, json.dumps(pacote))
    print(f"\nMensagem segura enviada para {destino}.")
    print(f"Tópico: {topico}")


def processar_chave_publica(payload: dict):
    id_remetente = payload.get("id_unidade")

    if not id_remetente:
        return

    if "chave_publica_rsa" not in payload:
        return

    if "chave_publica_ecdsa" not in payload:
        return

    chaves_confiadas[id_remetente] = {
        "chave_publica_rsa": payload["chave_publica_rsa"],
        "chave_publica_ecdsa": payload["chave_publica_ecdsa"]
    }

    salvar_chaves_confiadas()

    print(f"\nChave pública recebida/salva: {id_remetente}")


def processar_revogacao(payload: dict):
    id_revogada = payload.get("id_unidade")

    if not id_revogada:
        return

    if id_revogada in chaves_confiadas:
        del chaves_confiadas[id_revogada]
        salvar_chaves_confiadas()
        print(f"\nUnidade revogada removida das chaves confiadas: {id_revogada}")
    else:
        print(f"\nRevogação recebida para {id_revogada}, mas ela não estava salva.")


def processar_mensagem_direta(payload: dict):
    global rsa_private

    remetente = payload.get("id_unidade")

    if not remetente:
        print("\nMensagem direta sem id_unidade.")
        return

    if remetente == ID_UNIDADE:
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
            resposta = resolver_pergunta(mensagem)
            print(f"Resposta calculada: {resposta}")
            confirmar = input("Enviar resposta ao Oráculo? [s/n]: ").strip().lower()

            if confirmar == "s":
                enviar_resposta_oraculo(resposta)

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
    rsa_p, ecdsa_p = gerar_chaves()
    salvar_chaves(rsa_p, ecdsa_p)
    print("\nChaves geradas e salvas em minhas_chaves.json.")


def revogar_unidade():
    id_revogada = input("ID da unidade a revogar: ").strip().lower()

    pacote = {
        "id_unidade": id_revogada
    }

    client.publish(TOPICO_REVOGACAO, json.dumps(pacote))
    print(f"\nRevogação publicada para: {id_revogada}")


def consultar_notas():
    pacote = {
        "cmd": "atualizar_notas"
    }

    client.publish(TOPICO_NOTAS, json.dumps(pacote))
    print("\nSolicitação de atualização de notas enviada.")


def listar_chaves():
    print("\nChaves confiadas:")

    if not chaves_confiadas:
        print("Nenhuma chave salva ainda.")
        return

    for unidade in chaves_confiadas:
        print(f"- {unidade}")


def menu():
    while True:
        print("\n========== UT-DELTA ==========")
        print("1 - Gerar minhas chaves")
        print("2 - Publicar identidade")
        print("3 - Enviar echo para o Oráculo")
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

    if not os.path.exists("minhas_chaves.json"):
        print("Arquivo minhas_chaves.json não encontrado.")
        print("Use a opção 1 para gerar as chaves primeiro.")
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