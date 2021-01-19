''' workstation_status.py
    Flask app to siaplay Fly Light image processing pipeline status
'''

from datetime import datetime, timezone, timedelta
import json
from time import time
import concurrent.futures
from flask import Flask, render_template, request, jsonify, Response
from flask_swagger import swagger
import requests
from requests.exceptions import Timeout
from requests_html import HTMLSession

# pylint: disable=C0103,W0703,R1710,W0707

__version__ = '0.4.0'
app = Flask(__name__)
app.config.from_pyfile("config.cfg")
app.config['STARTTIME'] = time()
app.config['STARTDT'] = datetime.now()
# Configuration
CONFIG = {'config': {'url': app.config['CONFIG_ROOT']}}
LOCAL_TIMEZONE = datetime.now(timezone.utc).astimezone().tzinfo
TIME_PATTERN = '%Y-%m-%dT%H:%M:%S.%f%z'
HOST_STATUS = dict()
SERVER = dict()


# *****************************************************************************
# * Flask                                                                     *
# *****************************************************************************

@app.before_request
def before_request():
    ''' If needed, initilize global variables.
    '''
    # pylint: disable=W0603
    global CONFIG, SERVER
    app.config['COUNTER'] += 1
    endpoint = request.endpoint if request.endpoint else '(Unknown)'
    app.config['ENDPOINTS'][endpoint] = app.config['ENDPOINTS'].get(endpoint, 0) + 1
    if 'jacs' not in CONFIG:
        try:
            data = call_responder('config', 'config/rest_services')
        except Exception as err:
            return render_template('error.html', urlroot=request.url_root,
                                   message='Invalid response from %s for %s: %s' \
                                   % ('configuration server', 'rest_services', str(err)))
        if 'config' in data:
            CONFIG = data['config']
        else:
            return render_template('error.html', urlroot=request.url_root,
                                   message='No response from configuration server %s for %s' \
                                   % (CONFIG['config']['url'], 'reset_services'))
        try:
            data = call_responder('config', 'config/servers')
        except Exception as err:
            return render_template('error.html', urlroot=request.url_root,
                                   message='Invalid response from %s for %s: %s' \
                                   % ('configuration server', 'servers', str(err)))
        if 'config' in data:
            SERVER = data['config']
        else:
            return render_template('error.html', urlroot=request.url_root,
                                   message='No response from configuration server %s for %s' \
                                    % (CONFIG['config']['url'], 'reset_services'))

# ******************************************************************************
# * Utility functions                                                          *
# ******************************************************************************

def call_responder(server, endpoint):
    ''' Call a responder
        Keyword arguments:
          server: server
          endpoint: REST endpoint
    '''
    url = CONFIG[server]['url'] + endpoint
    try:
        req = requests.get(url)
    except requests.exceptions.RequestException as err: # pragma no cover
        return render_template('error.html', urlroot=request.url_root,
                               message=err)
    try:
        return req.json()
    except Exception as err:
        msg = "Bad response from %s/%s: status code=%d" \
              % (CONFIG[server]['url'], endpoint, req.status_code)
        print(msg)
        raise Exception(msg)


def call_jmx(hostnum):
    ''' Call JMX to get host stats
        Keyword arguments:
          hostnum: host number
    '''
    session = HTMLSession()
    url = app.config['HOST_PREFIX'] + str(hostnum) + app.config['HOST_SUFFIX']
    err = ipmc = qdepth = 0
    try:
        req = session.get(url, timeout=5)
        tbl = req.html.find('table')[4]
        ipmc = tbl.find('tr')[1].find('td')[3].text
        qdepth = tbl.find('tr')[9].find('td')[3].text
        print("Got info for " + app.config['HOST_PREFIX'] + str(hostnum))
        HOST_STATUS[hostnum] = [err, qdepth, ipmc]
    except Timeout:
        HOST_STATUS[hostnum] = [2, 0, 0]
    except Exception as err:
        HOST_STATUS[hostnum] = [1, qdepth, ipmc]


def get_status_count(status, found, show, tmp, statusdict):
    ''' Get in-process count for a given status
        Keyword arguments:
          status: process status
          found: found dictionary (contains count)
          show: HTML for button or link
          tmp: template
          statusdict: status dictionary
    '''
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
    if not this_count:
        this_count = '<span style="color: #aaa">0</span>'
    statusdict[status.lower()] = tmp % (show, color, link, status, this_count, show)


def get_processing_status():
    ''' Get count stats for JACS hosts
    '''
    for hostnum in app.config['HOST_NUMBERS']:
        HOST_STATUS[hostnum] = [2, -1, -1]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        executor.map(call_jmx, app.config['HOST_NUMBERS'], timeout=20)
    procrows = []
    qtot = 0
    ctot = 0
    bad = 0
    for hostnum in app.config['HOST_NUMBERS']:
        host = 'jacs-data' + str(hostnum)
        host_link = '<a href="%s" target="_blank">%s</a>' % \
            (app.config['HOST_PREFIX'] + str(hostnum) + app.config['HOST_SUFFIX'], host)
        (unavailable, qdepth, ipmc) = HOST_STATUS[hostnum]
        qtot += int(qdepth)
        ctot += int(ipmc)
        if unavailable:
            bad += 1
            qdepth = ipmc = '-'
            if unavailable == 1:
                status = 'OFFLINE'
                color = '#f90;'
            else:
                status = 'TIMEOUT'
                color = '#f40;'
        elif int(ipmc):
            status = 'Active'
            color = '#9f0'
        else:
            status = 'Idle'
            color = '#09f'
        status = '<span style="color: %s">%s</span>' % (color, status)
        procrows.append([host_link, qdepth, ipmc, status])
    if procrows:
        procrows.append(['TOTAL', qtot, ctot, ''])
    available = len(app.config['HOST_NUMBERS']) - bad
    color = '#f90;' if bad else '#9f0;'
    available = '<span style="color: %s">%s/%s</span>' % (color, str(available),
                                                          str(len(app.config['HOST_NUMBERS'])))
    return available, procrows


def get_elapsed_time(sample, status, text_only):
    ''' Get elapsed time (update time -> now)
        Keyword arguments:
          sampls: sample dictionary
          status: process status
          text_only: not HTML styles if true
    '''
    locpdt = datetime.strptime(sample['updatedDate'], TIME_PATTERN)
    locpdt = locpdt.replace(tzinfo=timezone.utc).astimezone(tz=LOCAL_TIMEZONE)
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
            etime = '<span style="color:#' +  app.config['GRADIENT'][selected] \
                    + ';">' + etime + '</span>'
        elif status == 'Processing' and (days > 0 or hours > app.config['PROCESSING_LIMIT']):
            etime = '<span style="color:#' +  app.config['GRADIENT'][selected] \
                    + ';">' + etime + '</span>'
    return timestamp, etime


def generate_sample_list(status, newlist, text_only, result):
    ''' Generate a list of samples for a given status
        Keyword arguments:
          status: process status
          newlist: sprted list of samples
          text_only: not HTML styles if true
          result: result array
    '''
    for sample in newlist:
        (timestamp, etime) = get_elapsed_time(sample, status, text_only)
        owner = sample['ownerKey'].split(':')[1]
        response = call_responder('jacs', 'info/sample/search?name=' + sample['name'])
        name_link = sample['name']
        if not text_only:
            addr = SERVER['webstation']['address'] + '/search?term=' + name_link
            name_link = "<a href=%s target=_blank>%s</a>" % (addr, name_link)
        if 'line' in response[0]:
            line_link = response[0]['line']
            if not text_only:
                addr = SERVER['informatics']['address'] + '/cgi-bin/lineman.cgi?line=' + line_link
                line_link = "<a href=%s target=_blank>%s</a>" % (addr, line_link)
        else:
            line_link = ''
        if 'slideCode' in response[0]:
            slide_link = response[0]['slideCode']
            if not text_only:
                addr = SERVER['webstation']['address'] + '/search?term=' + slide_link
                slide_link = "<a href=%s target=_blank>%s</a>" % (addr, slide_link)
        else:
            slide_link = ''
        result.append([name_link, line_link, slide_link, response[0]['dataSet'],
                       owner, timestamp, etime])


def generate_image_list(newlist, text_only, result):
    ''' Generate a list of unindexed from SAGE
        Keyword arguments:
          newlist: sprted list of samples
          text_only: not HTML styles if true
          result: result array
    '''
    for image in newlist:
        line_link = image['line']
        if not text_only:
            addr = SERVER['informatics']['address'] + '/cgi-bin/lineman.cgi?line=' + line_link
            line_link = "<a href=%s target=_blank>%s</a>" % (addr, line_link)
        slide_link = image['slide_code']
        if not text_only:
            addr = SERVER['webstation']['address'] + '/search?term=' + slide_link
            slide_link = "<a href=%s target=_blank>%s</a>" % (addr, slide_link)
        result.append([image['name'], line_link, slide_link, image['data_set'],
                       image['created_by'], image['create_date']])


# *****************************************************************************
# * Endpoints                                                                 *
# *****************************************************************************

@app.route("/help")
def show_swagger():
    ''' Show documentation
    '''
    return render_template('swagger_ui.html')


@app.route("/spec")
def spec():
    ''' Show specification
    '''
    return get_doc_json()


@app.route('/doc')
def get_doc_json():
    ''' Show documentation
    '''
    swag = swagger(app)
    swag['info']['version'] = __version__
    swag['info']['title'] = "Fly Light Image Processing Pipeline"
    return jsonify(swag)


@app.route('/')
def show_summary():
    ''' Default route
    '''
    START_TIME = time()
    print('Received request %s' % (datetime.now()))
    # Avaiting indexing
    statusdict = dict()
    tmp = '<div class="status"><%s role="button" class="btn btn-%s" href="%s">' \
          + '<span style="color: #fff;">%s</span> ' \
          + '<span class="badge badge-light">%s</span></%s></div>'
    link = '#'
    show = 'button'
    this_count = 0
    status = 'TMOGged'
    if app.config['SHOW_UNINDEXED']:
        try:
            response = call_responder('sage', 'unindexed_images/fast')
        except Exception as err:
            return render_template('error.html', urlroot=request.url_root,
                                   message='Invalid response from %s for %s: %s' \
                                   % ('SAGE responder', 'unindexed_images', str(err)))
        if 'row_count' not in response['rest']:
            return render_template('error.html', urlroot=request.url_root,
                                   message='Invalid response from %s for %s' \
                                   % ('SAGE responder', 'unindexed_images'))
        print("SAGE call: %s" % (response['rest']['elapsed_time']))
        if response['rest']['row_count']:
            link = request.url_root + 'unindexed'
            show = 'a'
            this_count = response['rest']['row_count']
        if not this_count:
            this_count = '<span style="color: #aaa">0</span>'
    statusdict[status.lower()] = tmp % (show, 'primary', link, status, this_count, show)
    # Status counts
    try:
        response = call_responder('jacs', 'info/sample?totals=true')
    except Exception as err:
        return render_template('error.html', urlroot=request.url_root,
                               message='Invalid response getting status counts: %s' \
                               % (str(err)))
    found = dict()
    msg = "Bad response from %s %s" \
          % ('/'.join([CONFIG['jacs']['url'], 'info/sample?totals=true']),
             json.dumps(response))
    for status in response:
        try:
            found[status['_id']] = status['count']
        except Exception as err:
            return render_template('error.html', urlroot=request.url_root,
                                   message='%s: %s' % (type(err).__name__, msg))
    for status in app.config['STATUS_ORDER']:
        if status == 'TMOGged':
            continue
        get_status_count(status, found, show, tmp, statusdict)
    (available, procrows) = get_processing_status()
    print("Elapsed time: %s" % (str(timedelta(seconds=(time()-START_TIME)))))
    return render_template('summary.html', urlroot=request.url_root, statuses=statusdict,
                           available=available, procrows=procrows,
                           display=app.config['LIMIT_DISPLAY'],
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
    if status not in app.config['STATUSES']:
        return render_template('sample_none.html', urlroot=request.url_root, status=status)
    result = []
    response = call_responder('jacs', 'info/sample?totals=false&status=' + status)
    newlist = sorted(response, key=lambda k: k['updatedDate'], reverse=True)
    text_only = False
    if len(newlist) > app.config['LIMIT_DOWNLOAD']:
        return render_template('sample_warning.html',
                               urlroot=request.url_root, numsamples=len(newlist),
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
