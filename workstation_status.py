from datetime import datetime, timezone
import sys
from time import time
import concurrent.futures
from flask import Flask, render_template, request, jsonify, Response
from flask_swagger import swagger
import requests
from requests_html import HTMLSession


__version__ = '0.1.0'
app = Flask(__name__)
app.config.from_pyfile("config.cfg")
app.config['STARTTIME'] = time()
app.config['STARTDT'] = datetime.now()
# Configuration
CONFIG = {'config': {'url': app.config['CONFIG_ROOT']}}
LOCAL_TIMEZONE = datetime.now(timezone.utc).astimezone().tzinfo
TIME_PATTERN = '%Y-%m-%dT%H:%M:%S.%f%z'
host_status = dict()


# *****************************************************************************
# * Flask                                                                     *
# *****************************************************************************

@app.before_request
def before_request():
    global CONFIG
    app.config['COUNTER'] += 1
    endpoint = request.endpoint if request.endpoint else '(Unknown)'
    app.config['ENDPOINTS'][endpoint] = app.config['ENDPOINTS'].get(endpoint, 0) + 1
    if 'jacs' not in CONFIG:
        data = call_responder('config', 'config/rest_services')
        try:
            CONFIG = data['config']
        except Exception as err:
            return render_template('error.html', urlroot=request.url_root,
                                    message='No response from configuration server %s' % CONFIG['config']['url'])

# ******************************************************************************
# * Utility functions                                                          *
# ******************************************************************************

def call_responder(server, endpoint):
    url = CONFIG[server]['url'] + endpoint
    try:
        req = requests.get(url)
    except requests.exceptions.RequestException as err: # pragma no cover
        return render_template('error.html', urlroot=request.url_root,
                               message=err)
    try:
        if req.status_code == 200:
            return req.json()
    except:
        return render_template('error.html', urlroot=request.url_root,
                               message=("Bad response from %s: status code=%d" % (CONFIG[server]['url'], req.status_code)))


def call_jmx(hostnum):
    session = HTMLSession()
    url = app.config['HOST_PREFIX'] + str(hostnum) + app.config['HOST_SUFFIX']
    err = ipmc = qdepth = 0
    try:
        req = session.get(url)
        tbl = req.html.find('table')[4]
        ipmc = tbl.find('tr')[1].find('td')[3].text
        qdepth = tbl.find('tr')[9].find('td')[3].text
    except: # pragma no cover
        err = 1
    host_status[hostnum] = [err, qdepth, ipmc]


def generate_sample_list(status, newlist, text_only, result):
    for sample in newlist:
        locpdt = datetime.strptime(sample['updatedDate'],
                                   TIME_PATTERN).replace(tzinfo=timezone.utc).astimezone(tz=LOCAL_TIMEZONE)
        timestamp = locpdt.strftime(TIME_PATTERN).split('.')[0].replace('T', ' ')
        elapsed = (datetime.now().replace(tzinfo=LOCAL_TIMEZONE) - locpdt).total_seconds()
        days, hoursrem = divmod(elapsed, 3600 * 24)
        hours, rem = divmod(hoursrem, 3600)
        minutes, seconds = divmod(rem, 60)
        etime = "{:0>2}:{:0>2}:{:0>2}".format(int(hours), int(minutes), int(seconds))
        if days:
            etime = "%d day%s, %s" % (days, '' if days == 1 else 's', etime)
        if not text_only:
            selected = int(days - 1)
            if selected < 0:
                selected = 0
            elif selected > 9:
                selected = 9
            if status == 'Queued' and (days > 0):
                etime = '<span style="color:#' +  app.config['GRADIENT'][selected] + ';">' + etime + '</span>'
            elif status == 'Processing' and (days > 0 or hours > app.config['PROCESSING_LIMIT']):
                etime = '<span style="color:#' +  app.config['GRADIENT'][selected] + ';">' + etime + '</span>'
        owner = sample['ownerKey'].split(':')[1]
        response = call_responder('jacs', 'info/sample/search?name=' + sample['name'])
        name_link = sample['name']
        if not text_only:
            addr = 'http://webstation.int.janelia.org/search?term=' + name_link
            name_link = "<a href=%s target=_blank>%s</a>" % (addr, name_link)
        if 'line' in response[0]:
            line_link = response[0]['line']
            if not text_only:
                addr = app.config['INFORMATICS'] + '/cgi-bin/lineman.cgi?line=' + line_link
                line_link = "<a href=%s target=_blank>%s</a>" % (addr, line_link)
        else:
            line_link = ''
        if 'slideCode' in response[0]:
            slide_link = response[0]['slideCode']
            if not text_only:
                addr = app.config['INFORMATICS'] + '/slide_search.php?term=slide_code&id=' + slide_link
                slide_link = "<a href=%s target=_blank>%s</a>" % (addr, slide_link)
        else:
            slide_link = ''
        result.append([name_link, line_link, slide_link, response[0]['dataSet'], owner, timestamp, etime])


def generate_image_list(newlist, text_only, result):
    for image in newlist:
        line_link = image['line']
        if not text_only:
            addr = app.config['INFORMATICS'] + '/cgi-bin/lineman.cgi?line=' + line_link
            line_link = "<a href=%s target=_blank>%s</a>" % (addr, line_link)
        slide_link = image['slide_code']
        if not text_only:
            addr = app.config['INFORMATICS'] + '/slide_search.php?term=slide_code&id=' + slide_link
            slide_link = "<a href=%s target=_blank>%s</a>" % (addr, slide_link)
        result.append([image['name'], line_link, slide_link, image['data_set'], image['created_by'], image['create_date']])

# *****************************************************************************
# * Endpoints                                                                 *
# *****************************************************************************

@app.route("/help")
def show_swagger():
    return render_template('swagger_ui.html')


@app.route("/spec")
def spec():
    return get_doc_json()


@app.route('/doc')
def get_doc_json():
    swag = swagger(app)
    swag['info']['version'] = __version__
    swag['info']['title'] = "Workstation status"
    return jsonify(swag)


@app.route('/')
def show_summary():
    # Avaiting indexing
    statusdict = dict()
    tmp = '<div class="status"><%s role="button" class="btn btn-%s" href="%s"><span style="color: #fff;">%s</span> <span class="badge badge-light">%s</span></%s></div>'
    link = '#'
    show = 'button'
    this_count = 0
    status = 'TMOGged'
    if app.config['SHOW_UNINDEXED']:
        response = call_responder('sage', 'unindexed_images')
        if response['rest']['row_count']:
            link = request.url_root + 'unindexed'
            show = 'a'
            this_count = response['rest']['row_count']
    statusdict[status.lower()] = tmp % (show, 'primary', link, status, this_count, show)
    # Status counts
    response = call_responder('jacs', 'info/sample?totals=true')
    found = dict()
    for status in response:
        found[status['_id']] = status['count']
    for status in app.config['STATUS_ORDER']:
        if status == 'TMOGged':
            continue
        this_count = 0
        if status in found:
            this_count = found[status]
        color = 'dark'
        link = '#'
        show = 'button'
        if this_count and (this_count <= app.config['LIMIT_DOWNLOAD']):
            link = request.url_root + 'status/' + status
            show = 'a'
        if status in app.config['STATUS_COLOR']:
            color = app.config['STATUS_COLOR'][status]
        statusdict[status.lower()] = tmp % (show, color, link, status, this_count, show)
    # Processing status
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        executor.map(call_jmx, app.config['HOST_NUMBERS'])
    procrows = []
    qtot = 0
    ctot = 0
    bad = 0
    for hostnum in app.config['HOST_NUMBERS']:
        host = 'jacs-data' + str(hostnum)
        host_link = '<a href="%s" target="_blank">%s</a>' % \
            (app.config['HOST_PREFIX'] + str(hostnum) + app.config['HOST_SUFFIX'], host)
        (unavailable, qdepth, ipmc) = host_status[hostnum]
        qtot += int(qdepth)
        ctot += int(ipmc)
        procrows.append([host_link, qdepth, ipmc])
        if unavailable:
            bad += 1
            qdepth = ipmc = '-'
    if procrows:
        procrows.append(['TOTAL', qtot, ctot])
    available = len(app.config['HOST_NUMBERS']) - bad
    color = '#f90;' if bad else '#9f0;'
    available = '<span style="color: %s">%s/%s</span>' % (color, str(available), str(len(app.config['HOST_NUMBERS'])))
    return render_template('summary.html', urlroot=request.url_root, statuses=statusdict,
                           available=available, procrows=procrows, display=app.config['LIMIT_DISPLAY'],
                           download=app.config['LIMIT_DOWNLOAD'])


@app.route('/unindexed')
def show_unindexed():
    '''
    Show unindexed images
    Show images awaiting indexing.
    ---
    tags:
      - Samples
    responses:
      200:
          description: Image list
    '''
    result = []
    response = call_responder('sage', 'unindexed_images')
    text_only = False
    if response['rest']['row_count'] > app.config['LIMIT_DISPLAY']:
        text_only = True
    generate_image_list(response['images'], text_only, result)
    if text_only:
        def generate():
            result.insert(0, app.config['IMAGE_HEADER'])
            for row in result:
                yield "\t".join(row) + '\n'
        return Response(generate(), mimetype='text/csv',
                        headers={"Content-Disposition":
                                 "attachment;filename=images.tsv"})
    return render_template('image_list.html', urlroot=request.url_root,
                           numimages=response['rest']['row_count'],
                           result=result)


@app.route('/unindexed/download/')
def download_unindexed():
    '''
    Download unindexed images
    Download a file with a tab-delimited list of unindexed images.
    ---
    tags:
      - Samples
    responses:
      200:
          description: Image list
    '''
    result = []
    response = call_responder('sage', 'unindexed_images')
    generate_image_list(response['images'], True, result)
    def generate():
        result.insert(0, app.config['IMAGE_HEADER'])
        for row in result:
            yield "\t".join(row) + '\n'
    return Response(generate(), mimetype='text/csv',
                    headers={"Content-Disposition":
                             "attachment;filename=images.tsv"})


@app.route('/status/<status>')
def show_status(status):
    '''
    Show samples in a given status
    Show a list of samples for a given status.
    ---
    tags:
      - Samples
    parameters:
      - in: path
        name: status
        type: string
        required: true
        description: Sample status
    responses:
      200:
          description: Sample list
    '''
    #if status not in app.config['STATUSES']:
    #    return render_template('sample_none.html', urlroot=request.url_root, status=status)
    result = []
    response = call_responder('jacs', 'info/sample?totals=false&status=' + status)
    newlist = sorted(response, key=lambda k: k['updatedDate'], reverse=True)
    text_only = False
    if len(newlist) > app.config['LIMIT_DOWNLOAD']:
        return render_template('sample_warning.html', urlroot=request.url_root, numsamples=len(newlist),
                               status=status)
    if len(newlist) > app.config['LIMIT_DISPLAY']:
        text_only = True
    generate_sample_list(status, newlist, text_only, result)
    if text_only:
        def generate():
            result.insert(0, app.config['STATUS_HEADER'])
            for row in result:
                yield "\t".join(row) + '\n'
        return Response(generate(), mimetype='text/csv',
                        headers={"Content-Disposition":
                                 "attachment;filename=%s.tsv" % status.lower()})
    return render_template('sample_list.html', urlroot=request.url_root,
                           numsamples=len(newlist),
                           status=status, result=result)


@app.route('/status/download/<status>')
def download_status(status):
    '''
    Download samples in a given status
    Download a file with a tab-delimited list of samples for a given status.
    ---
    tags:
      - Samples
    parameters:
      - in: path
        name: status
        type: string
        required: true
        description: Sample status
    responses:
      200:
          description: Sample list
    '''
    if status not in app.config['STATUSES']:
        return render_template('sample_none.html', urlroot=request.url_root, status=status)
    result = []
    response = call_responder('jacs', 'info/sample?totals=false&status=' + status)
    newlist = sorted(response, key=lambda k: k['updatedDate'], reverse=True)
    generate_sample_list(status, newlist, True, result)
    def generate():
        result.insert(0, app.config['STATUS_HEADER'])
        for row in result:
            yield "\t".join(row) + '\n'
    return Response(generate(), mimetype='text/csv',
                    headers={"Content-Disposition":
                             "attachment;filename=%s.tsv" % status.lower()})

# *****************************************************************************

if __name__ == '__main__':
    app.run(debug=True)
