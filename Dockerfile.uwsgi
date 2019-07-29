FROM python:3-stretch
LABEL maintainer="Rob Svirskas <svirskasr@hhmi.org>"
RUN pip install uwsgi
COPY ./ ./app
WORKDIR ./app
RUN pip3 install -r requirements.txt
CMD uwsgi --http 0.0.0.0:9090 --module workstation_status --callable app --master --processes 2 --threads 4
