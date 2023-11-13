from flask import Flask, request, abort
import requests, base64, os, json

def response(request):
    if 'acknowledge_event' in request.json:
        if request.json['acknowledge_event']['status'] != 'Idle':
            payload = base64.b64decode(request.json['acknowledge_event']['raw_payload'])
            sendDocument(payload, request.json['acknowledge_event']['command_uuid'])       
    if 'topic' in request.json:
        if request.json['topic'] == 'mdm.Authenticate':
            payload = base64.b64decode(request.json['checkin_event']['raw_payload'])
            sendDocument(payload, "Device registered!\nUDID: "+request.json['checkin_event']['udid'])
            installAllProfiles(request.json['checkin_event']['udid'])
        if request.json['topic'] == 'mdm.CheckOut':
            payload = base64.b64decode(request.json['checkin_event']['raw_payload'])
            sendDocument(payload, "Device deleted MDM profile!\nUDID: "+request.json['checkin_event']['udid'])

def sendDocument(document,caption):
    method = "sendDocument"
    urlTelegram = f"https://api.telegram.org/bot{TOKEN}/{method}"
    file = open('payload.xml', 'wb')
    file.write(document)
    file.close()
    file = open('payload.xml', 'r')
    data = {
                'chat_id': CHAT_ID,
                'filename': "payload.xml",
                'caption': caption
            }
    requests.post(urlTelegram, data=data, files={'document': file}, stream=True)

def installAllProfiles(udid):
    urlMicromdmCommands = MICROMDM_COMMAND_URL
    profiles = os.listdir(PROFILES_PATH);
    for profile in profiles:
        file = open(PROFILES_PATH+profile, 'r')
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

def loadConfig():
    try:
        with open('config.json', 'r') as configFile:
            global config
            config = json.load(configFile)
    except FileNotFoundError:
        print("Config file not found")
        exit()

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    print(request.json)
    response(request)
    return ''

config = None
loadConfig()

TOKEN = config["token"]
CHAT_ID = config["chatID"]
PROFILES_PATH = config["profilesPath"]
MICROMDM_COMMAND_URL = config["micromdmCommandUrl"]
MICROMDM_API_PASSWORD = config["micromdmApiPass"]
HOST = config["host"]
PORT = config["port"]

if __name__ == '__main__':
    app.run(host=HOST, port=PORT)
