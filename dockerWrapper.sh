#!/bin/bash

# Start the first process
python3 /app/app.py &

# Start the second process
if [[ $TG_POST_MODE == 1 ]]
then
    python3 /app/botchecker.py &
fi

# Wait for any process to exit
wait -n

# Exit with status of process that exited first
exit $?