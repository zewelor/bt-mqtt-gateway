FROM python:3.8-alpine3.12

ENV DEBUG false

RUN mkdir application
WORKDIR /application

COPY requirements.txt /application

RUN apk add --no-cache tzdata bluez bluez-libs sudo bluez-deprecated && \
    ln -s /config.yaml ./config.yaml                                 && \
    pip install -r requirements.txt

COPY . /application

RUN apk add --no-cache --virtual build-dependencies git bluez-dev musl-dev make gcc glib-dev musl-dev && \
    pip install `./gateway.py -r all`                                                                 && \
    apk del build-dependencies

COPY ./start.sh /start.sh
RUN chmod +x /start.sh

ENTRYPOINT ["/bin/sh", "-c", "/start.sh"]
