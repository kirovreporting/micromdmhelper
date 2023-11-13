To make it work you need python3 & flask installed. Specify all the variables in config.json and place it in the same folder as app.py; start it with python3 app.py. 

It will:
- notify you if a new device is registered
- try to install all files in the “profilesPath” folder as MDM profiles on devices right after registration.
- send you a messages with the UID of the MicroMDM commands that have been sent and a .json file containing the details
- notify you if someone has deleted the enrollment profile from the device