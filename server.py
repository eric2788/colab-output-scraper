# create flask web app to get the APP_URL from colab.py
import colab
from flask import Flask, jsonify
import requests
import logging
from constrants import EMAIL, PASSWORD
from werkzeug.exceptions import HTTPException
import atexit

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

@app.errorhandler(Exception)
def handle_error(e):
    code = 500
    if isinstance(e, HTTPException):
        code = e.code
    return jsonify(code=code, msg=str(e)), code


def validate_app_url() -> bool:
    if not colab.APP_URL or not colab.APP_URL.startswith('http'):
        return False
    try:
        res = requests.get(colab.APP_URL)
        if res.status_code != 200:
            return False
        else:
            return True
    except Exception as e:
        logging.warning(e)
        return False


@app.route('/launch_colab', methods=['POST'])
def launch_colab():
    colab.run_colab(EMAIL, PASSWORD)
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
    else:
        return jsonify({
            'code': 410,
            'msg': 'url is not valid or expired'
        })


if __name__ == '__main__':
    atexit.register(colab.quit_driver)
    app.run(port=8080)
