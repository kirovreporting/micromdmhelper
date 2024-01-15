FROM python:alpine3.18

EXPOSE 8008
RUN adduser -D python_runner
WORKDIR /app
ADD . /app/
RUN mkdir /app/logs && chown -R python_runner /app
RUN pip3 install -r requirements.txt
USER python_runner
CMD ["/app/dockerWrapper.sh"]
