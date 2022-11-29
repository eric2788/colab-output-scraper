from sys import platform
import undetected_chromedriver.v2 as uc
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.chrome.options import Options
from selenium.webdriver import Chrome

def init_driver() -> Chrome:
    caps = DesiredCapabilities.CHROME.copy()
    caps["goog:loggingPrefs"] = {"performance": "ALL"}  # enable performance logs

    options = Options()
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")

    driver_path = None
    

    if platform.startswith("linux"):
        driver_path = '/usr/bin/chromedriver'
        options.add_argument("--no-sandbox") # linux only
    driver: Chrome = uc.Chrome(desired_capabilities=caps, options=options, driver_executable_path=driver_path)
    driver.implicitly_wait(30)
    return driver