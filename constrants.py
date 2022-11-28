import os
from dotenv import load_dotenv

load_dotenv(override=True)

NOTEBOOK_URL = f'https://colab.research.google.com/drive/{os.getenv("NOTEBOOK_ID")}?usp=sharing'

EMAIL = os.getenv('GMAIL')
PASSWORD = os.getenv('GMAIL_PASSWORD')

DATA_DIR = 'profile'
COOKIE_PATH = f'{DATA_DIR}/cookies.json'

CELL_OUTPUT_ID = os.getenv('CELL_OUTPUT_ID', 'cell-wSwVGakT24XG')
