from flask import Flask, request, abort
import requests, base64, os, json, logging, sqlite3
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
    logging.info("Got message from telegram")
    if 'message' in request.json:
        if request.json['message']['from']['id'] in TG_WHITELIST_IDS:
            messageEntities = ""
            if 'caption_entities' in request.json['message']:
                messageEntities = request.json['message']['caption_entities']
            elif 'entities' in request.json['message']:
                messageEntities = request.json['message']['entities']
            if messageEntities != "":
                logging.info("Message has entities")
                for messageEntity in messageEntities:
                    if messageEntity['type'] == "bot_command":
                        if 'text' in request.json['message']:
                            botCommand=request.json['message']['text'][messageEntity['offset']:messageEntity['length']]
                        elif 'caption' in request.json['message']:
                            botCommand=request.json['message']['caption'][messageEntity['offset']:messageEntity['length']]
                        logging.info("Got command "+botCommand)
                        if botCommand == "/uploadprofile":
                            if 'document' in request.json['message']:
                                filePath = getAttachedFilePath(request.json['message']['document']['file_id'])
                                fileName = request.json['message']['document']['file_name']
                                logging.info("Downloading "+fileName)
                                downloadAttachedFile(filePath,fileName,PROFILES_PATH_DOCKER)
                                logging.info("Success")
                                sendMessage(request.json['message']['from']['id'],"Профиль загружен")
                            else:
                                sendMessage(request.json['message']['from']['id'],"Нет профиля для загрузки")
                        if botCommand == "/lsprofiles":
                            profiles = os.listdir(PROFILES_PATH_DOCKER)
                            composedMessage = ""
                            for profile in profiles:
                                composedMessage += profile+"\n"
                            sendMessage(request.json['message']['from']['id'],composedMessage)
                        if botCommand == "/lsdevices":
                            credentialsEncoded = base64.b64encode(str.encode("micromdm:"+MICROMDM_API_PASSWORD))
                            headers = {
                                'Authorization': str.encode('Basic ')+credentialsEncoded,
                                'Content-Type': 'application/json'
                                }
                            response = requests.post(MICROMDM_URL+"/v1/devices", headers=headers, data="{}")
                            composedMessage = ""
                            for device in response.json()['devices']:
                                composedMessage+=device['serial_number']+"\n"
                            sendMessage(request.json['message']['from']['id'],composedMessage)
                            
        else:
            logging.info("Sender is not in whitelist")


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

def sendMessage(chatID,text):
    method = "sendMessage"
    urlTelegram = f"https://api.telegram.org/bot{TG_TOKEN}/{method}"
    data = {
                'chat_id': chatID,
                'text': text
            }
    requests.post(urlTelegram, data=data, stream=True)

def installAllProfiles(udid):
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
        response = requests.post(MICROMDM_URL+"/v1/commands", headers=headers, data=json.dumps(data))
        logging.info(response.text)
    
def getAttachedFilePath(fileID):
    url = f'https://api.telegram.org/bot{TG_TOKEN}/getFile'
    params = {'file_id': fileID}
    response = requests.get(url, params=params)
    filePath = response.json()['result']['file_path']
    return filePath

def downloadAttachedFile(filePath,fileName,folderToSave):
    url = f'https://api.telegram.org/file/bot{TG_TOKEN}/{filePath}'
    logging.info("File from "+url)
    response = requests.get(url)
    with open(f"{folderToSave}/{fileName}", 'wb') as file:
        logging.info(os.getcwd())
        file.write(response.content)

app = Flask(__name__)

@app.errorhandler(Exception)
def handle_exception(e):
    # log the exception
    logging.exception('Exception occurred')
    # return a custom error page or message
    return render_template('error.html'), 500

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
TG_WHITELIST_IDS = json.loads(os.environ["TG_WHITELIST_IDS"])
PROFILES_PATH_DOCKER = os.environ.get(
    "PROFILES_PATH_DOCKER", "/app/profiles/"
)
MICROMDM_URL = os.environ["MICROMDM_URL"]
MICROMDM_API_PASSWORD = os.environ["MICROMDM_API_PASSWORD"]

if __name__ == '__main__':
    app.run(host="0.0.0.0", port="8008")
