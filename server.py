# create flask web app to get the APP_URL from colab.py
import colab
from flask import Flask, jsonify
from waitress import serve
import requests
import logging
from constrants import EMAIL, PASSWORD, DEBUG_MODE
from werkzeug.exceptions import HTTPException
import signal
from threading import Lock

if DEBUG_MODE:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

logger = logging.getLogger(__name__)

colab_lock = Lock()


@app.errorhandler(Exception)
def handle_error(e):
    code = 500
    logging.error('resolved error: %s', e)
    if isinstance(e, HTTPException):
        code = e.code
    elif not isinstance(e, RuntimeError):
        logging.exception(e)
    return jsonify(code=code, msg=str(e)), code


def validate_app_url() -> bool:
    if not colab.APP_URL or not colab.APP_URL.startswith('http'):
        return False
    try:
        res = requests.get(colab.APP_URL, timeout=30)
        return res.status_code != 200
    except Exception as e:
        logging.warning(e)
        return False


@app.route('/launch_colab', methods=['POST'])
def launch_colab():

    if colab_lock.locked():
        return jsonify({
            'code': 400,
            'msg': 'colab is launching, please wait until finish'
        }), 400

    with colab_lock:
        colab.run_colab(EMAIL, PASSWORD)  # 5 ~ 10 mins

    return jsonify({
        'code': 200,
        'msg': 'success',
        'url': colab.APP_URL
    })


@app.route('/get_url', methods=['GET'])
def get_url():
    if validate_app_url():
        return jsonify({
            'code': 200,
            'msg': 'success',
            'url': colab.APP_URL
        })
    return jsonify({
        'code': 410,
        'msg': 'url is not valid or expired'
    })

if __name__ == '__main__':

    logger.info('starting web server...')

    signal.signal(signal.SIGTERM, lambda signum, frame: colab.quit_driver())

    args = {
        'host': '0.0.0.0',
        'port': 8080,
    }

    colab.start_recaptcha_thread()

    if DEBUG_MODE:
        app.run(**args, debug=DEBUG_MODE, use_reloader=False)
    else:
        serve(app, **args)
