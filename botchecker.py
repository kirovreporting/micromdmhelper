import requests, json, os, logging, sys,time

current_working_directory = os.getcwd()
logging.basicConfig(
    format="%(asctime)s botchecker %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)

TG_TOKEN = os.environ.get("TG_TOKEN")
BIND_HOST = os.environ.get("BIND_HOST")
BIND_PORT = os.environ.get("BIND_PORT")
RESOURCES_PATH_DOCKER = os.environ["RESOURCES_PATH_DOCKER"]

offset = 0

def checkBot(token):
    global offset
    data = {
                'offset': int(offset),
                'timeout': 50
            }
    headers={
        'Content-type':'application/json'
    }
    logging.debug(data)
    response = requests.post(f'https://api.telegram.org/bot{TG_TOKEN}/getUpdates', data=json.dumps(data), timeout=None, headers=headers)
    logging.debug(response.json())
    updates = response.json()['result']
    for update in updates:
        logging.info("Got update, now forwarding...")
        if sendToBot(update):
            offset = int(update['update_id'])
            logging.info(f'Update {offset} delivered')
            offset += 1
    logging.debug("New offset is "+str(offset))


def sendToBot(data):
    urlApp = f'http://{BIND_HOST}:{BIND_PORT}/'
    headers={
        'Content-type':'application/json'
    }
    response = requests.post(urlApp, data=json.dumps(data), headers=headers)
    if response.status_code == 200:
        return True
    else:
        return False
    
logging.info("POST checker is active")
time.sleep(3)
while True:
    logging.debug("Starting POST check with offset "+str(offset))
    checkBot(TG_TOKEN)
