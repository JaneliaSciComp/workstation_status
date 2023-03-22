FROM python:3.11
ADD . /api
WORKDIR /api
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
EXPOSE 8000
CMD ["gunicorn", "-w 2", "-b", "0.0.0.0:8000", "workstation_status:app"]
