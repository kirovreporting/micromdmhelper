To make it work you need add `.env` file and run `docker compose up -d`

It will:
- notify you if a new device is registered
- try to install all files in the “profilesPath” folder as MDM profiles on devices right after registration.
- send you a messages with the UID of the MicroMDM commands that have been sent and a .json file containing the details
- notify you if someone has deleted the enrollment profile from the device
- upload profiles to the “profilesPath” folder with /uploadprofile command
- list uploaded profiles with /lsprofiles command
- list enrolled devices with /lsdevices command
- install selected profile with /installprofile command

ENVS:

| Name                  | Default | Description                                                                               |
|-----------------------|---------|-------------------------------------------------------------------------------------------|
| TG_TOKEN              |         | telegram bot token                                                                        |
| TG_CHAT_ID            |         | telegram chat_id                                                                          |
| TG_WHITELIST_IDS      |         | telegram ids of users allowed to send commands                                            |
| TG_POST_MODE          |         | use 0 to receive updates from tg via webhooks and 1 to receive updates with POST requests |
| PROFILES_PATH_DOCKER  |         | PATH profiles in docker                                                                   |
| MICROMDM_COMMAND_URL  |         | comands enpoint you micromdm, example: https://micromdm.youcompany.org/v1/commands        |
| MICROMDM_API_PASSWORD |         | micromdm api key                                                                          |
| BIND_HOST             | 0.0.0.0 | interfaces host to bind in docker                                                         |
| BIND_PORT             | 8001    | port to bind in docker                                                                    |
| FLASK_ENV             |         | development or producrion                                                                 |
| FLASK_DEBUG           |         | debug 1 or 0                                                                              |
