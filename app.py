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
            logging.info(payload)
            parsedPayload = XML.fromstring(payload)
            computerSerial = parsedPayload[0][17].text
            computerName = parsedPayload[0][5].text
            computerUDID = parsedPayload[0][21].text
            query = '''
                INSERT INTO devices (serial, name, udid)
                VALUES ("%s","%s","%s")
                ''' % (computerSerial, computerName, computerUDID)
            try:
                execDBQuery(query)
            except sqlite3.IntegrityError:
                logging.info("Device exists in database, updating...")
                query = '''
                    UPDATE devices (name, udid)
                    VALUES ("%s","%s")
                    WHERE serial = "%s"
                ''' % (computerName, computerUDID, computerSerial)
            except Exception as e:
                logging.log("Error occured: "+get_full_class_name(e))
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
                            botCommand = request.json['message']['text'][messageEntity['offset']:messageEntity['length']]
                            commandArguments = request.json['message']['text'][messageEntity['offset']+messageEntity['length']:].split(" ")
                        elif 'caption' in request.json['message']:
                            botCommand = request.json['message']['caption'][messageEntity['offset']:messageEntity['length']]
                            commandArguments = request.json['message']['caption'][messageEntity['offset']+messageEntity['length']:].split(" ")
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
                            composedMessage = "Name — Serial — UDID\n"
                            for device in response.json()['devices']:                               
                                nameQuery = '''
                                    SELECT name
                                    FROM devices
                                    WHERE serial = "%s"
                                    ''' % (device['serial_number'])
                                try:
                                    name = execDBQuery(nameQuery)[0]
                                    if name is None:
                                        name = ""
                                except TypeError:
                                    logging.info("There is some computer that is present in MicroMDM, but missinп in DB. Fixing...")
                                    fixQuery = '''
                                        INSERT INTO devices (serial, udid)
                                        VALUES ("%s","%s")
                                        ''' % (device['serial_number'], device['udid'])
                                    execDBQuery(fixQuery)
                                    name = ""
                                udidQuery = '''
                                    SELECT udid
                                    FROM devices
                                    WHERE serial = "%s"
                                    ''' % (device['serial_number'])
                                udid = execDBQuery(udidQuery)[0]
                                composedMessage+=name+" — "+device['serial_number']+" — "+udid+"\n"
                            sendMessage(request.json['message']['from']['id'],composedMessage)
                        if botCommand == "/installprofile":
                            try:
                                udid = commandArguments[1]
                                logging.info(udid)
                                profileName = commandArguments[2]
                                logging.info("Sending profile "+profileName+" for UDID "+udid)
                            except IndexError:
                                sendMessage(request.json['message']['from']['id'],"This command needs two args (udid & profile name) separated by a space")
                                return
                            installProfile(udid,profileName)
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

def installProfile(udid,profileName):
    file = open(PROFILES_PATH_DOCKER+"/"+profileName, 'r')
    try:
        profileBytes = bytes(file.read(), 'utf-8')
    except:
        logging.info("Error occured while encoding profile "+profileName)
        return
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

def installAllProfiles(udid):
    profiles = os.listdir(PROFILES_PATH_DOCKER)
    for profile in profiles:
        installProfile(udid,profile)
    
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

def execDBQuery(query):
    db = sqlite3.connect(DB_PATH) 
    dbCursor = db.cursor()
    dbCursor.execute(query)
    result = dbCursor.fetchone()
    db.commit()
    db.close()
    return result

def get_full_class_name(obj):
    module = obj.__class__.__module__
    if module is None or module == str.__class__.__module__:
        return obj.__class__.__name__
    return module + '.' + obj.__class__.__name__

app = Flask(__name__)

@app.errorhandler(Exception)
def handle_exception(e):
    # log the exception
    logging.exception('Exception occurred')
    # return a custom error page or message
    return '', 500

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
RESOURCES_PATH_DOCKER = os.environ["RESOURCES_PATH_DOCKER"]
DB_PATH = RESOURCES_PATH_DOCKER+"/db.sqlite3"

initializeDB= '''
    CREATE TABLE IF NOT EXISTS devices
    ([serial] TEXT PRIMARY KEY, [name] TEXT, [udid] TEXT, [fvRecoveryKey] TEXT, [activationLockCodeBypassCode] TEXT)
    '''
execDBQuery(initializeDB)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port="8008")
