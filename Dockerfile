FROM alpine:3.8

RUN mkdir application
WORKDIR /application
ADD . /application

RUN apk add --no-cache tzdata python3 git bluez glib-dev make bluez-dev bluez-libs musl-dev linux-headers gcc grep && \
    python3 -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    pip3 install --upgrade pip setuptools && \
    if [ ! -e /usr/bin/pip ]; then \
      ln -s pip3 /usr/bin/pip ; \
    fi && \
    if [[ ! -e /usr/bin/python ]]; then \
      ln -sf /usr/bin/python3 /usr/bin/python; \
    fi && \
    rm -r /root/.cache && \
    mkdir /config && \
    pip install -r requirements.txt && \
    ln -s /config/config.yaml ./config.yaml && \
    apk del --no-cache bluez-dev musl-dev gcc make git glib-dev linux-headers grep python2

RUN apk add --no-cache tzdata python3 git bluez glib-dev make bluez-dev bluez-libs musl-dev linux-headers gcc grep && \
    grep -P "(?<=REQUIREMENTS).*" workers/*.py | grep -Po "(?<=\[).*(?=\])" | tr ',' '\n' | tr "'" " "| tr "\"" " " > /tmp/requirements.txt && \
    cat /tmp/requirements.txt && \
    pip install -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt && \
    apk del --no-cache bluez-dev musl-dev gcc make git glib-dev linux-headers grep python2

ADD ./start.sh /start.sh
RUN chmod +x /start.sh

ENV DEBUG false

VOLUME ["/config"]

ENTRYPOINT ["/bin/sh", "-c", "/start.sh"]
