## Guia Rápido de MQTT 🌐

**MQTT (Message Queuing Telemetry Transport)** é um protocolo leve de mensagens usado principalmente para comunicação entre dispositivos em redes IoT (Internet das Coisas). Ele é baseado no modelo **publicador/assinante**, o que o torna eficiente e ideal para ambientes com largura de banda limitada.

Pense no MQTT (Message Queuing Telemetry Transport) como um **mural de avisos digital e super eficiente**  Em vez de uma pessoa ligar diretamente para outra (comunicação ponto-a-ponto), as pessoas publicam mensagens em categorias específicas no mural, e quem estiver interessado em uma categoria, fica de olho nela para ler as novas mensagens assim que aparecem.

Os componentes principais são:

1.  **Broker:** É o servidor central, o nosso "mural de avisos". Ele é responsável por receber todas as mensagens e distribuí-las para quem estiver interessado.
2.  **Client:** É qualquer programa ou dispositivo (no nosso caso, nosso script Python) que se conecta ao Broker. Um cliente pode tanto publicar mensagens quanto se inscrever para recebê-las.

O servidor (Broker) tem `tópicos` - que um string, como `ufcg/cc/dlt`. Que cada barra representa um nivel é seria como uma "categoria" de um forum. Os clientes podem :
-  Publicar (Publish): É o ato de um cliente criar/enviar uma mensagem para um tópico específico no Broker.
-  Inscrever-se (Subscribe): É o ato de um cliente dizer ao Broker: "Ei, me avise sempre que uma nova mensagem for publicada neste tópico".


### Como vamos usar no nosso Laboratório?

*   **Broker:** Usaremos um Broker público e gratuito para testes, localizado em `broker.hivemq.com`. Ele não requer cadastro.
*   **Tópicos:** Para evitar que nossa turma interfira com outros usuários do Broker público, vamos padronizar nossos tópicos. A estrutura está descrita na tarefa.
*   **Dados:** As mensagens (payloads) que enviamos via MQTT são strings. Portanto, nosso pacote de dados criptografado (que estará em formato JSON ou similar) deverá ser codificado em **Base64** antes de ser publicado.


### "Hello World" em Python

Vamos criar dois scripts simples para entender o fluxo: um que publica uma mensagem e outro que se inscreve para recebê-la.

**Pré-requisito: Instalar a biblioteca `paho-mqtt`**

Abra seu terminal ou prompt de comando e execute:
```bash
pip install paho-mqtt
```

#### Envio de menssagens (`publisher.py`)

Este script vai se conectar, publicar uma única mensagem em nosso tópico e se desconectar.

```python
import paho.mqtt.client as mqtt
import time


BROKER_ADDRESS = "broker.hivemq.com"
TOPIC = "ufcg/cc/dlt/menssagens" 
MESSAGE = "Olá, mundo da criptografia! Esta é uma mensagem de teste."

client = mqtt.Client()
client.connect(BROKER_ADDRESS, 1883, 60)


client.loop_start()
client.publish(TOPIC, MESSAGE)
time.sleep(1) # garanir que a menssagem seja publicada

client.loop_stop() #desconexao
client.disconnect()
print("Mensagem publicada e cliente desconectado.")
```

O método `publish()` envia mensagens para um **tópico**, este metodo pode enviar menssagens com dois comportamentos distintos.

No exemplo, utilizamos desse modo:

```python
client.publish(TOPIC, MESSAGE)
```

Essa chamada **publica uma mensagem normal**. Se nenhum cliente estiver assinando o tópico no momento da publicação, a mensagem será simplesmente descartada. Ou seja, só quem estiver conectado e assinando o tópico no momento recebe a mensagem.


No exemplot abaixo (com `retain=True`), a mensagem é **retida no broker**. Isso significa que o broker armazena essa mensagem como a “última conhecida” para o tópico e a entrega automaticamente a qualquer novo cliente que assinar esse tópico, mesmo depois que a mensagem original foi publicada.

```python
client.publish(TOPIC, MESSAGE, retain=True)
```

> 🧠 Talvez comunicar as chaves pubblicas do exercicio seja interessante enviar com `retain=True`

# Recebendo Mensagens MQTT em Múltiplos Tópicos com Python

O código abaixo utiliza um broker MQTT para **escutar múltiplos tópicos simultaneamente**. 


```python
import paho.mqtt.client as mqtt

BROKER_ADDRESS = "broker.hivemq.com"
TOPICOS = [
    "ufcg/cc/dlt/wall",
    "ufcg/cc/dlt/menssagens",
]

# --- Funções de Callback ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        for topico in TOPICOS:
            client.subscribe(topico)
    else:
        print(f"Falha na conexão. Código de retorno: {rc}")

def on_message(client, userdata, msg):
    mensagem = msg.payload.decode()
    print("-" * 30)
    print(f"📥 Tópico: {msg.topic}")
    print(f"📨 Conteúdo: {mensagem}")
    print("-" * 30)

# --- Cliente MQTT ---
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER_ADDRESS, 1883, 60)
client.loop_forever()
```

Como o código funciona?

- **Lista de tópicos**: os tópicos estão definidos na lista `TOPICOS`. O cliente irá assinar cada um deles assim que se conectar com sucesso ao broker.
- **Callback `on_connect`**: chamada quando o cliente se conecta ao broker. Se a conexão for bem-sucedida (`rc == 0`), ele faz a inscrição (`subscribe`) em cada tópico da lista.
- **Callback `on_message`**: chamada toda vez que uma mensagem chega em qualquer um dos tópicos. O conteúdo da mensagem é decodificado e impresso no console.
- **Loop principal**: `client.loop_forever()` mantém o cliente rodando em segundo plano para escutar e processar mensagens continuamente.


É importante destacar MQTT aceita dois curingas (wildcards) para inscrição em tópicos:
* `+` (plus): representa **um único nível** no tópico. Se você utilizar o tópico com o wildcard:

```python
client.subscribe("ufcg/cc/dlt/chaves/+")
```

Você receberá todos os sub-topicos, por exemplo:

* `ufcg/cc/dlt/chaves/UT-Alfa`
* `ufcg/cc/dlt/chaves/UT-Bravo`
* `ufcg/cc/dlt/chaves/qualquer-outro-id`

O mesmo vale para qualquer tópico - e.g., mensagens:

```python
client.subscribe("ufcg/cc/dlt/mensagens/para/+")
```
