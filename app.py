from flask import Flask, request, abort
import requests, base64, os, sys, json, logging, sqlite3, plistlib, xml.etree.ElementTree as XML

current_working_directory = os.getcwd()
logging.basicConfig(
    format="%(asctime)s main %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)

def responseMicroMDM(request):
    logging.info(request.json)
    if 'acknowledge_event' in request.json:
        if request.json['acknowledge_event']['status'] != 'Idle':
            payload = base64.b64decode(request.json['acknowledge_event']['raw_payload'])
            sendDocument(payload, request.json['acknowledge_event']['command_uuid'])
    if 'topic' in request.json:
        if request.json['topic'] == 'mdm.Authenticate':
            payload = base64.b64decode(request.json['checkin_event']['raw_payload'])
            logging.info(payload)
            parsedPayload = parsePlist(payload)
            if "Mac" in parsedPayload["ProductName"]:
                computerSerial = parsedPayload["SerialNumber"]
                computerName = parsedPayload["DeviceName"]
                computerUDID = parsedPayload["UDID"]
                query = '''
                    INSERT INTO devices (serial, name, udid)
                    VALUES ("%s","%s","%s")
                    ''' % (computerSerial, computerName, computerUDID)
                try:
                    execDBQuery(query)
                except sqlite3.IntegrityError:
                    logging.info("Device exists in database, updating...")
                    query = '''
                        UPDATE devices 
                        SET name = "%s",
                            udid = "%s"
                        WHERE serial = "%s"
                    ''' % (computerName, computerUDID, computerSerial)
                except Exception as e:
                    logging.exception("Error occured: "+getFullClassName(e), exc_info=e)
                sendDocument(payload, "Computer registered!\nUDID: "+computerUDID+"\nSerial: "+computerSerial+"\nName: "+computerName)
            else:
                deviceSerial = parsedPayload["SerialNumber"]
                deviceUDID = parsedPayload["UDID"]
                deviceModel = parsedPayload["ProductName"]
                query = '''
                    INSERT INTO devices (serial, udid)
                    VALUES ("%s","%s")
                    ''' % (deviceSerial, deviceUDID)
                try:
                    execDBQuery(query)
                except sqlite3.IntegrityError:
                    logging.info("Device exists in database, updating...")
                    query = '''
                        UPDATE devices
                        SET udid = '{0}'
                        WHERE serial = '{1}'
                    '''.format(deviceUDID, deviceSerial)
                    execDBQuery(query)
                except Exception as e:
                    logging.exception("Error occured: "+getFullClassName(e), exc_info=e)
                sendDocument(payload, "Device registered!\nUDID: "+deviceUDID+"\nSerial: "+deviceSerial+"\nModel: "+deviceModel)
                installAllProfiles(request.json['checkin_event']['udid'])
        if request.json['topic'] == 'mdm.TokenUpdate':
            deviceUDID = request.json['checkin_event']['udid']
            payload = base64.b64decode(request.json['checkin_event']['raw_payload'])
            parsedPayload = parsePlist(payload)
            logging.info(parsedPayload)
            if "UnlockToken" in parsedPayload:
                logging.info("Got unlock token for "+deviceUDID)
                mdmToken = parsedPayload["Token"]
                unlockToken = parsedPayload["UnlockToken"]
                query = '''
                            UPDATE devices
                            SET mdmToken = '{0}',
                                unlockToken = '{1}'
                            WHERE udid = '{2}'
                        '''.format(mdmToken, unlockToken, deviceUDID)
                execDBQuery(query)
        if request.json['topic'] == 'mdm.CheckOut':
            payload = base64.b64decode(request.json['checkin_event']['raw_payload'])
            sendDocument(payload, "Device deleted MDM profile!\nUDID: "+request.json['checkin_event']['udid'])

def responseTelegram(request):
    logging.info("Got message from telegram")
    logging.info(request.json)
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
                        if 'document' in request.json['message']:
                            document = request.json['message']['document']
                        else:
                            document = None
                        mdmCommand(botCommand,request.json['message']['chat']['id'],commandArguments,document)
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
                'text': text,
                'parse_mode': 'Markdown'
            }
    requests.post(urlTelegram, data=data, stream=True)

def installProfile(udid,profileName):
    logging.info("Sending profile "+profileName+" for UDID "+udid)
    try:
        file = open(PROFILES_PATH_DOCKER+"/"+profileName, 'r')
    except Exception as e:
        logging.info("Error occured while reading profile "+profileName, exc_info=e)
        return
    try:
        profileBytes = bytes(file.read(), 'utf-8')
    except Exception as e:
        logging.exception("Error occured while encoding profile "+profileName, exc_info=e)
        return
    profileEncoded = base64.b64encode(profileBytes)
    headers = {
        'Authorization': str.encode('Basic ')+CREDENTIALS_ENCODED,
        'Content-Type': 'application/json'
        }
    data = {
            'udid': udid,
            'payload': bytes.decode(profileEncoded),
            'request_type': "InstallProfile"
        }
    response = requests.post(MICROMDM_URL+"/v1/commands", headers=headers, data=json.dumps(data))
    logging.info(response.text)

def removeProfile(udid,profileName):
    profileID = ""
    try:
        profileFile = open(PROFILES_PATH_DOCKER+"/"+profileName, "rb").read()
        parsedProfile = plistlib.loads(profileFile)
        profileID = parsedProfile["PayloadIdentifier"]
    except Exception as e:
        logging.exception("Error occured while reading profile "+profileName, exc_info=e)
        return
    headers = {
        'Authorization': str.encode('Basic ')+CREDENTIALS_ENCODED,
        'Content-Type': 'application/json'
        }
    data = {
            'udid': udid,
            'identifier': profileID,
            'request_type': "RemoveProfile"
        }
    response = requests.post(MICROMDM_URL+"/v1/commands", headers=headers, data=json.dumps(data))
    logging.info(response.text)

def restartDevice(udid):
    headers = {
        'Authorization': str.encode('Basic ')+CREDENTIALS_ENCODED,
        'Content-Type': 'application/json'
        }
    data = {
            'udid': udid,
            'request_type': "RestartDevice"
        }
    response = requests.post(MICROMDM_URL+"/v1/commands", headers=headers, data=json.dumps(data))
    logging.info(response.text)

def clearPasscode(udid):
    query = '''
            SELECT unlockToken
            FROM devices
            WHERE udid = '{0}'
            '''.format(udid)
    unlockToken = execDBQuery(query)[0][0]
    headers = {
        'Authorization': str.encode('Basic ')+CREDENTIALS_ENCODED,
        'Content-Type': 'application/json'
        }
    data = {
            'udid': udid,
            'request_type': "ClearPasscode",
            'unlock_token': unlockToken
        }
    logging.info(data)
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
    logging.info(query)
    db = sqlite3.connect(DB_PATH)
    try: 
        dbCursor = db.cursor()
        dbCursor.execute(query)
        result = dbCursor.fetchall()
        db.commit()
        db.close()
        return result
    except Exception as e:
        db.close()
        raise e

def parsePlist(xml):
    parsedPayload = XML.fromstring(xml)
    dictionary = {}
    for i in range(0,len(parsedPayload[0]),2):
        key=parsedPayload[0][i].text
        value=parsedPayload[0][i+1].text
        if value is not None: value = value.strip().replace("\n\t", "")
        dictionary.update({key: value})
    return dictionary

def getFullClassName(obj):
    module = obj.__class__.__module__
    if module is None or module == str.__class__.__module__:
        return obj.__class__.__name__
    return module + '.' + obj.__class__.__name__

def getGroupUUIDList(name):
    devicesUUID = []
    match name:
        case "!all":
            udidQuery = '''
                SELECT udid
                FROM devices
                '''
            queryResult = execDBQuery(udidQuery)
            for record in queryResult:
                devicesUUID.append(record[0])
    return devicesUUID

def mdmCommand(name,chat,arguments,document):
    logging.info("Got command "+name)
    match name:
        case "/lsprofiles":
            profiles = os.listdir(PROFILES_PATH_DOCKER)
            composedMessage = ""
            for profile in profiles:
                composedMessage += "`"+profile+"`"
                # profileFile = open(PROFILES_PATH_DOCKER+"/"+profile, "rb").read()
                # parsedProfile = plistlib.loads(profileFile)
                # profileID = parsedProfile["PayloadIdentifier"]
                composedMessage += "\n"
            if composedMessage == "":
                composedMessage = "No profiles uploaded"
            else:
                composedMessage = "Filename\n" + composedMessage
            sendMessage(chat,composedMessage)
        case "/rmprofile":
            devices = []
            try:
                udid = arguments[1]
                profileName = " ".join(arguments[2:])
                logging.info("Removing profile "+profileName+" from UDID "+udid)
            except IndexError:
                sendMessage(chat,"This command needs two args (udid & profile name) separated by a space")
                return
            if udid[0] == "!":
                devices = getGroupUUIDList(udid)
            else:
                devices.appent(udid)
            for device in devices:
                logging.info(device)
                if profileName == "!!!ALL!!!":
                    profiles = os.listdir(PROFILES_PATH_DOCKER)
                    for profile in profiles:
                        removeProfile(device[0],profile)
                else:
                    removeProfile(device[0],profileName)
        case "/uploadprofile":
            if document:
                filePath = getAttachedFilePath(document['file_id'])
                fileName = document['file_name']
                logging.info("Downloading "+fileName)
                downloadAttachedFile(filePath,fileName,PROFILES_PATH_DOCKER)
                logging.info("Success")
                sendMessage(chat,"Profile uploaded")
            else:
                sendMessage(chat,"No profile to upload")
        case "/lsdevices":
            headers = {
                'Authorization': str.encode('Basic ')+CREDENTIALS_ENCODED,
                'Content-Type': 'application/json'
                }
            response = requests.post(MICROMDM_URL+"/v1/devices", headers=headers, data="{}")
            composedMessage = ""
            try:
                for device in response.json()['devices']:                               
                    nameQuery = '''
                        SELECT name
                        FROM devices
                        WHERE serial = "%s"
                        ''' % (device['serial_number'])
                    try:
                        name = execDBQuery(nameQuery)[0][0]
                        if name is None:
                            name = ""
                    except (TypeError, IndexError):
                        logging.info("There is some device that is present in MicroMDM, but missinп in DB. Fixing...")
                        fixQuery = '''
                            INSERT INTO devices (serial, udid)
                            VALUES ("%s","%s")
                            ''' % (device['serial_number'], device['udid'])
                        execDBQuery(fixQuery)
                        name = ""
                    except Exception as e:
                        logging.exception("Exception occured while reading DB query output: "+getFullClassName(e), exc_info=e)
                    udidQuery = '''
                        SELECT udid
                        FROM devices
                        WHERE serial = "%s"
                        ''' % (device['serial_number'])
                    udid = execDBQuery(udidQuery)[0][0]
                    composedMessage+=name+" — "+device['serial_number']+" — `"+udid+"`\n"
            except:
                logging.exception("Error occured: "+getFullClassName(e), exc_info=e)
                composedMessage = "No devices enrolled"
            else:
                composedMessage = "Name — Serial — UDID\n" + composedMessage
            sendMessage(chat,composedMessage)
        case "/installprofile":
            devices = []
            try:
                udid = arguments[1]
                profileName = " ".join(arguments[2:])
            except IndexError:
                sendMessage(chat,"This command needs two args (udid & profile name) separated by a space")
                return
            if udid[0] == "!":
                devices = getGroupUUIDList(udid)
            else:
                devices.append(udid)
            for device in devices:
                logging.info(device)
                if profileName == "!all":
                    profiles = os.listdir(PROFILES_PATH_DOCKER)
                    for profile in profiles:
                        installProfile(device,profile)
                else:
                    installProfile(device,profileName)
        case "/restartdevice":
            devices = []
            try:
                udid = arguments[1]
                profileName = " ".join(arguments[2:])
            except IndexError:
                sendMessage(chat,"This command needs device uuid as an argument to work")
                return
            if udid[0] == "!":
                devices = getGroupUUIDList(udid)
            else:
                devices.append(udid)
            for device in devices:
                logging.info(device)
                restartDevice(device)
        case "/clearpasscode":
            devices = []
            try:
                udid = arguments[1]
                profileName = " ".join(arguments[2:])
            except IndexError:
                sendMessage(chat,"This command needs device uuid as an argument to work")
                return
            if udid[0] == "!":
                devices = getGroupUUIDList(udid)
            else:
                devices.append(udid)
            for device in devices:
                logging.info(device)
                clearPasscode(device)            
        case _:
            sendMessage(chat,"Unknown command")


app = Flask(__name__)

@app.errorhandler(Exception)
def handle_exception(e):
    # log the exception
    logging.exception('Exception occurred')
    # return a custom error page or message
    return '', 500

@app.route('/webhook', methods=['POST'])
def micromdmWebhook():
    responseMicroMDM(request)
    return ''

@app.route('/', methods=['POST'])
def telegramWebhook():
    responseTelegram(request)
    return '', 200

BIND_HOST = os.environ["BIND_HOST"]
BIND_PORT = os.environ["BIND_PORT"]
TG_TOKEN = os.environ["TG_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]
TG_WHITELIST_IDS = json.loads(os.environ["TG_WHITELIST_IDS"])
PROFILES_PATH_DOCKER = os.environ.get(
    "PROFILES_PATH_DOCKER", "/app/profiles/"
)
MICROMDM_URL = os.environ["MICROMDM_URL"]
MICROMDM_API_PASSWORD = os.environ["MICROMDM_API_PASSWORD"]
CREDENTIALS_ENCODED = base64.b64encode(str.encode("micromdm:"+MICROMDM_API_PASSWORD))
RESOURCES_PATH_DOCKER = os.environ["RESOURCES_PATH_DOCKER"]
DB_PATH = RESOURCES_PATH_DOCKER+"/db.sqlite3"

initializeDB= '''
    CREATE TABLE IF NOT EXISTS devices
    ([serial] TEXT PRIMARY KEY, [name] TEXT, [udid] TEXT, [fvRecoveryKey] TEXT, [activationLockCodeBypassCode] TEXT, [mdmToken] TEXT, [unlockToken] TEXT)
    '''
execDBQuery(initializeDB)

if __name__ == '__main__':
    app.run(host=BIND_HOST, port=BIND_PORT)
