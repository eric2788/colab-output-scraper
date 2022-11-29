from sys import platform
import undetected_chromedriver.v2 as uc
from pyvirtualdisplay import Display
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.chrome.options import Options
from selenium.webdriver import Chrome
import logging

def init_driver() -> Chrome:
    caps = DesiredCapabilities.CHROME.copy()
    caps["goog:loggingPrefs"] = {"performance": "ALL"}  # enable performance logs

    options = Options()
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")

    driver_path = None
    display: Display = None

    if platform.startswith("linux"):
        logging.info('using linux os')
        driver_path = '/usr/bin/chromedriver'
        options.add_argument("--no-sandbox") # linux only
        # use this to replace headless
        display = Display(visible=0, size=(800, 600))
        display.start()

    driver: Chrome = uc.Chrome(desired_capabilities=caps, options=options, driver_executable_path=driver_path)
    driver.implicitly_wait(30)
    return driver