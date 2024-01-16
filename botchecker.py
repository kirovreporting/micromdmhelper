import requests, json, os

TG_TOKEN = os.environ.get("TG_TOKEN")
BIND_HOST = os.environ.get("BIND_HOST")
BIND_PORT = os.environ.get("BIND_PORT")
RESOURCES_PATH_DOCKER = os.environ["RESOURCES_PATH_DOCKER"]

offset = 0

def checkBot(token,offset):
    data = {
                'offset': offset,
                'limit': 1,
                'timeout': 30
            }
    response = requests.post("https://api.telegram.org/bot{TG_TOKEN}/getUpdates", data=json.dumps(data))
    if 'result' in response.json():
        os.remove(f'{RESOURCES_PATH_DOCKER}/{offset}.offset')
        offset = response.json()['result']['update_id']
        with open(f'{RESOURCES_PATH_DOCKER}/{offset}.offset', 'r'):
                pass
        return response.json
    else:
         return None

def sendToBot(jsonData):
    response = requests.post(f'{BIND_HOST}:{BIND_PORT}/', data=jsonData)
    if response.status_code == 200:
        return True
    else:
        return False
    
while True:
    check=checkBot(TG_TOKEN,offset)
    if check:
        sendToBot(check)