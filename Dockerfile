FROM python:3.8-alpine3.11

RUN mkdir application
WORKDIR /application
ADD . /application

RUN apk add --no-cache tzdata bluez bluez-libs sudo bluez-deprecated

RUN apk add --no-cache --virtual build-dependencies linux-headers && \
    rm -rf /root/.cache && \
    pip install -r requirements.txt && \
    apk del build-dependencies

RUN apk add --no-cache --virtual build-dependencies git bluez-dev musl-dev make gcc glib-dev musl-dev && \
    ./gateway.py -r all | tr ' ' "\n" > /tmp/requirements.txt && \
    cat /tmp/requirements.txt && \
    pip install -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt && \
    apk del build-dependencies

ADD ./start.sh /start.sh
RUN chmod +x /start.sh

ENV DEBUG false

ENTRYPOINT ["/bin/sh", "-c", "/start.sh"]
