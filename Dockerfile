FROM python:3.8-alpine

ENV DEBUG false

RUN mkdir /application
COPY . /application

WORKDIR /application

RUN apk add --no-cache tzdata bluez bluez-libs sudo bluez-deprecated                                  && \
    apk add --no-cache --virtual build-dependencies git bluez-dev musl-dev make gcc glib-dev musl-dev && \
    pip install --no-cache-dir -r requirements.txt                                                    && \
    pip install --no-cache-dir `./gateway.py -r all`                                                  && \
    apk del build-dependencies

COPY ./start.sh /start.sh
RUN chmod +x /start.sh

VOLUME /application/config.yaml

ENTRYPOINT ["/bin/sh", "-c", "/start.sh"]
