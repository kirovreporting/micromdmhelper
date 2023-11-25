from flask import Flask, request, abort
import requests, base64, os, json, logging
import xml.etree.ElementTree as XML

current_working_directory = os.getcwd()
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
    filename=f"{current_working_directory}/logs/micromdmhelper.log",
)

def responseMicroMDM(request):
    if 'acknowledge_event' in request.json:
        if request.json['acknowledge_event']['status'] != 'Idle':
            payload = base64.b64decode(request.json['acknowledge_event']['raw_payload'])
            sendDocument(payload, request.json['acknowledge_event']['command_uuid'])
    if 'topic' in request.json:
        if request.json['topic'] == 'mdm.Authenticate':
            payload = base64.b64decode(request.json['checkin_event']['raw_payload'])
            parsedPayload = XML.fromstring(payload)
            computerSerial = parsedPayload[0][17].text
            computerName = parsedPayload[0][5].text
            sendDocument(payload, "Device registered!\nUDID: "+request.json['checkin_event']['udid']+"\nSerial: "+computerSerial+"\nName: "+computerName)
        if request.json['topic'] == 'mdm.TokenUpdate':
            installAllProfiles(request.json['checkin_event']['udid'])
        if request.json['topic'] == 'mdm.CheckOut':
            payload = base64.b64decode(request.json['checkin_event']['raw_payload'])
            sendDocument(payload, "Device deleted MDM profile!\nUDID: "+request.json['checkin_event']['udid'])

def responseTelegram(request):
    print(request.json['entities'])

def sendDocument(document,caption):
    method = "sendDocument"
    urlTelegram = f"https://api.telegram.org/bot{TG_TOKEN}/{method}"
    file = open('payload.xml', 'wb')
    file.write(document)
    file.close()
    file = open('payload.xml', 'r')
    data = {
                'chat_id': TG_CHAT_ID,
                'filename': "payload.xml",
                'caption': caption
            }
    requests.post(urlTelegram, data=data, files={'document': file}, stream=True)

def installAllProfiles(udid):
    urlMicromdmCommands = MICROMDM_COMMAND_URL
    profiles = os.listdir(PROFILES_PATH_DOCKER)
    for profile in profiles:
        file = open(PROFILES_PATH_DOCKER+profile, 'r')
        profileBytes = bytes(file.read(), 'utf-8')
        profileEncoded = base64.b64encode(profileBytes)
        credentialsEncoded = base64.b64encode(str.encode("micromdm:"+MICROMDM_API_PASSWORD))
        headers = {
            'Authorization': str.encode('Basic ')+credentialsEncoded,
            'Content-Type': 'application/json'
            }
        data = {
                'udid': udid,
                'payload': bytes.decode(profileEncoded),
                'request_type': "InstallProfile"
            }
        response = requests.post(urlMicromdmCommands, headers=headers, data=json.dumps(data))
        print(response.text)

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def micromdmWebhook():
    logging.info(request.json)
    responseMicroMDM(request)
    return ''

@app.route('/', methods=['POST'])
def telegramWebhook():
    logging.info(request.json)
    responseTelegram(request)
    return '', 200

TG_TOKEN = os.environ["TG_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]
TG_WHITELIST_IDS = os.environ["TG_WHITELIST_IDS"]
PROFILES_PATH_DOCKER = os.environ.get(
    "PROFILES_PATH_DOCKER", "/app/profiles/"
)
MICROMDM_COMMAND_URL = os.environ["MICROMDM_COMMAND_URL"]
MICROMDM_API_PASSWORD = os.environ["MICROMDM_API_PASSWORD"]

if __name__ == '__main__':
    app.run(host="0.0.0.0", port="8008")
