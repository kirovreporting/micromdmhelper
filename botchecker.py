import requests, dotenv, json, os

load_dotenv('.env')
TG_TOKEN = os.environ.get("TG_TOKEN")
BIND_HOST = os.environ.get("BIND_HOST")
BIND_PORT = os.environ.get("BIND_PORT")
RESOURCES_PATH_DOCKER = os.environ["RESOURCES_PATH_DOCKER"]

def checkBot(token):
    data = {
                'offset': offset,
                'limit': 1,
                'timeout': 30
            }
    response = requests.post("https://api.telegram.org/bot{TG_TOKEN}/getUpdates", data=json.dumps(data))
    os.remove("{RESOURCES_PATH_DOCKER}/{offset}.offset")
    offset = response.json['result']['update_id']
    with open("{RESOURCES_PATH_DOCKER}/{offset}.offset", 'r'):
            pass
    return response.json

def sendToBot(jsonData):
    response = requests.post("{BIND_HOST}:{BIND_PORT}/", data=jsonData)
    if response.status_code == 200:
        return True
    else:
        return False
    
while True:
    sendToBot(checkBot(TG_TOKEN))