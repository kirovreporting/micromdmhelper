import requests, json, os, logging, sys

current_working_directory = os.getcwd()
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)

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
    response = requests.post(f'https://api.telegram.org/bot{TG_TOKEN}/getUpdates', data=json.dumps(data))
    logging.info(response.json())
    if 'result' in response.json(): 
        if 'update_id' in response.json()['result'] :
            os.remove(f'{RESOURCES_PATH_DOCKER}/{offset}.offset')
            offset = int(response.json()['result']['update_id'])
            with open(f'{RESOURCES_PATH_DOCKER}/{offset}.offset', 'r'):
                    pass
            return response.json
        else:
            return None
    else:
        return None

def sendToBot(jsonData):
    response = requests.post(f'{BIND_HOST}:{BIND_PORT}/', data=jsonData)
    if response.status_code == 200:
        return True
    else:
        return False
    
logging.info("POST checker is active")
    
while True:
    logging.info("Starting POST check with offset "+str(offset))
    check=checkBot(TG_TOKEN,offset)
    if check:
        logging.info("Sending POST response to main app")
        logging.info(check)
        sendToBot(check)