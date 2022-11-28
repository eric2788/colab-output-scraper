import os
from dotenv import load_dotenv

load_dotenv(override=True)

if os.getenv('NOTEBOOK_ID') == None:
    raise ValueError('NOTEBOOK_ID is not set')

NOTEBOOK_URL = f'https://colab.research.google.com/drive/{os.getenv("NOTEBOOK_ID")}?usp=sharing'

EMAIL = os.getenv('GMAIL')
PASSWORD = os.getenv('GMAIL_PASSWORD')

DATA_DIR = 'profile'
COOKIE_PATH = f'{DATA_DIR}/cookies.json'

DEBUG_MODE = os.getenv('DEBUG', 'false') == 'true'

CELL_OUTPUT_ID = os.getenv('CELL_OUTPUT_ID', 'cell-wSwVGakT24XG')
