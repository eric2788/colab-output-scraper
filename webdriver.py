import json
import logging
from sys import platform
from time import sleep

import undetected_chromedriver.v2 as uc
from selenium.common.exceptions import (JavascriptException,
                                        NoAlertPresentException,
                                        NoSuchElementException,
                                        TimeoutException, WebDriverException)
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

from constrants import COOKIE_PATH, DISABLE_DEV_SHM

logger = logging.getLogger(__name__)


def init_driver(version:int = 107) -> Chrome:
    caps = DesiredCapabilities.CHROME.copy()
    caps["goog:loggingPrefs"] = {
        "performance": "ALL"}  # enable performance logs

    options = Options()
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    #options.add_argument("--start-maximized")
    #options.add_argument(
    #    '--user-agent="Mozilla/5.0 (Windows Phone 10.0; Android 4.2.1; Microsoft; Lumia 640 XL LTE) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Mobile Safari/537.36 Edge/12.10166"')

    driver_path = None

    if platform.startswith("linux"):
        driver_path = '/usr/bin/chromedriver'
        options.add_argument("--no-sandbox")  # linux only
        if DISABLE_DEV_SHM:
            options.add_argument('--disable-dev-shm-usage')
    # pylint: disable=no-member
    driver: Chrome = uc.Chrome(
        desired_capabilities=caps,
        options=options,
        driver_executable_path=driver_path,
        version_main=version
    )
    driver.implicitly_wait(30)
    print('user-agent:', driver.execute_script("return navigator.userAgent;"))
    print('webdriver detected:', driver.execute_script("return navigator.webdriver;"))
    return driver


def force_refresh_webpage(driver: Chrome, url: str) -> None:
    driver.get(url)
    try:
        driver.switch_to.alert.accept()
    except NoAlertPresentException:
        pass


def wait_and_click_element(driver: Chrome, by: str, value: str,
                           wait: int = 5,
                           click_with_js: bool = True
                           ) -> bool:
    try:
        element = WebDriverWait(driver, wait).until(
                lambda t_driver: t_driver.find_element(by, value)
        )

        sleep(3)

        WebDriverWait(driver, 3).until(
            expected_conditions.element_to_be_clickable((by, value))
        )
        
        if click_with_js:
            driver.execute_script("arguments[0].click();", element)
        else:
            element.click()
       
        sleep(0.1)
        return True
    except TimeoutException:
        return False

def keep_page_active(driver: Chrome):
    # keep webpage active
    driver.execute_script("""
        function ConnectButton(){
            console.log("Connect pushed");
            document.querySelector("#top-toolbar > colab-connect-button").shadowRoot.querySelector("#connect").click()
        }
        setInterval(ConnectButton,60000);
    """)


def save_cookie(driver: Chrome):
    try:
        cookies = driver.get_cookies()
        if not cookies:
            return
        with open(COOKIE_PATH, 'w', encoding='utf8') as filehandler:
            json.dump(cookies, filehandler)
            logger.info('成功保存Cookie')
    except Exception as ex:
        logger.warning('保存Cookie失败: %s', ex)


def load_cookie(driver: Chrome):
    try:
        with open(COOKIE_PATH, 'r', encoding='utf8') as cookiesfile:
            cookies = json.load(cookiesfile)
        for cookie in cookies:
            driver.add_cookie(cookie)
        logger.info('成功加载Cookie')
    except Exception as ex:
        logger.warning('加载Cookie失败: %s', ex)


def escape_runtime_disconnect(driver: Chrome):
    try:
        dialog = WebDriverWait(driver, 20).until(expected_conditions.visibility_of_element_located(By.TAG_NAME, 'colab-yesno-dialog'))

    except TimeoutException:
        pass

def escape_recaptcha(driver: Chrome):
    try:
        # WebDriverWait(driver, 20).until(expected_conditions.frame_to_be_available_and_switch_to_it(
        #    (By.XPATH, "//iframe[starts-with(@name, 'a-') and starts-with(@src, 'https://www.google.com/recaptcha')]")
        # ))
        WebDriverWait(driver, 20).until(expected_conditions.visibility_of_element_located((By.TAG_NAME, 'colab-recaptcha-dialog')))
        logger.info('发现 Google reCAPTCHA, 尝试跳过...')

        WebDriverWait(driver, 20).until(expected_conditions.frame_to_be_available_and_switch_to_it(
            (By.XPATH, "//iframe[starts-with(@name, 'a-') and starts-with(@src, 'https://www.google.com/recaptcha')]")
        ))

        try:
            wait = WebDriverWait(driver, 10)
            checkmark = wait.until(expected_conditions.element_to_be_clickable((
                        By.XPATH, "//div[@class='recaptcha-checkbox-checkmark']"
            )))
            driver.execute_script('arguments[0].click()', checkmark)
            logger.info('跳过成功')
        except WebDriverException as e:
            if isinstance(e, NoSuchElementException):
                logger.warning('找不到recaptcha按钮元素: %s', e.msg)
            elif isinstance(e, TimeoutException) or isinstance(e, JavascriptException):
                logger.warning('绕过验证码按钮无法点击: %s', e.msg)
            logger.warning('将尝试直接使用JS代码点击')
            try:
                driver.execute_script("document.querySelector('div.recaptcha-checkbox-checkmark').click()")
                logger.info('跳过成功')
            except JavascriptException as e:
                logger.warning("使用JS代码点击依然失败: %s", e.msg)
        finally:
            driver.switch_to.default_content()
    except TimeoutException:
        pass
