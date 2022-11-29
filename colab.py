import undetected_chromedriver.v2 as uc
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.common.exceptions import TimeoutException, NoAlertPresentException, JavascriptException, WebDriverException
import pathlib
from time import sleep
import regex, json, os
from sys import platform
from constrants import *
import logging
from pyvirtualdisplay import Display

APP_URL = ""

logger = logging.getLogger('colab')

url_regexp = regex.compile(r'Running\son\spublic\sURL:\s(https:\/\/[a-f0-9]+\.gradio\.app)', regex.S | regex.M)

script_directory = pathlib.Path().absolute()

caps = DesiredCapabilities.CHROME.copy()
caps["goog:loggingPrefs"] = {"performance": "ALL"}  # enable performance logs

options = Options()
options.add_argument("--disable-extensions")
options.add_argument("--disable-gpu")

driver_path = None
display: Display = None

if platform.startswith("linux"):
    logger.info('using linux os')
    driver_path = '/usr/bin/chromedriver'
    options.add_argument("--no-sandbox") # linux only
    # use this to replace headless
    display = Display(visible=0, size=(800, 600))
    display.start()

driver: Chrome = uc.Chrome(desired_capabilities=caps, options=options, driver_executable_path=driver_path)
driver.implicitly_wait(30)
#driver = webdriver.Chrome('./chromedriver', desired_capabilities=caps, options=options)

os.makedirs(DATA_DIR, exist_ok=True)

# copy from net
def run_colab(gmail: str, password: str) -> None:
    global driver
    try:
        driver.get('https://colab.research.google.com')
    except WebDriverException as e:   # session expired
        logger.warning(f'error while opening page: {e}')
        # reassign driver
        driver = uc.Chrome(desired_capabilities=caps, options=options, driver_executable_path=driver_path)
        driver.implicitly_wait(30)
        raise RuntimeError(f'打開colab網頁失敗: {e}, 請重試一次')
    
    load_cookie()

    force_refresh_webpage(NOTEBOOK_URL)

    login_google_acc(gmail, password)

    sleep(3)
    try:
        wait = WebDriverWait(driver, 30)
        wait.until(expected_conditions.visibility_of(driver.find_element(By.ID, CELL_OUTPUT_ID)))
    except JavascriptException:
        # failed to fill input box
        # mostly, this happens when Google is asking you to do extra verification i.e. phone number
        # Colab page won't be loaded normally, then result in this error.
        raise RuntimeError(
            f"Google账密验证成功，但Colab页面没有被成功加载。可能是因为Google正在要求账号进行额外验证或账号不再可用！"
            f"当前账号：{gmail}"
        )

    logger.info('successfully going to colab page...')

    running_status = driver.find_element(By.XPATH, f'//*[@id="{CELL_OUTPUT_ID}"]').get_attribute('class')
    if "running" in running_status:
        logger.info("interrupt previous execution...")
        # interrupt previous execution
        driver.find_element(By.XPATH, '/html/body').send_keys(Keys.CONTROL + 'm')
        sleep(0.3)
        driver.find_element(By.XPATH, '/html/body').send_keys('i')

        try:
            wait = WebDriverWait(driver, 30)
            wait.until(expected_conditions.text_to_be_present_in_element(
                (By.XPATH, f'//*[@id="{CELL_OUTPUT_ID}"]//pre'),
                'KeyboardInterrupt'
            ))
            logger.info('successfully interrupted previous execution.')
        except TimeoutException:
            logger.warning('cannot interrupt current exception.')

        sleep(3)

    logger.info('removing previous output...')

    driver.execute_script(f"""
        document.querySelector('#{CELL_OUTPUT_ID}  iron-icon[command=clear-focused-or-selected-outputs]').click()
    """)

    sleep(2)

    logger.info('execute completed. trying to run all cells.')

    # run all cells
    driver.find_element(By.XPATH, '/html/body').send_keys(Keys.CONTROL + Keys.F9)

    # If Google asks you to confirm running this notebook
    try:
        wait_and_click_element(
            by=By.XPATH, value='/html/body/colab-dialog/paper-dialog/div[2]/paper-button[2]'
        )
    except TimeoutException:
        pass

    try:
        wait = WebDriverWait(driver, 15 * 60)
        wait.until(expected_conditions.text_to_be_present_in_element(
            (By.XPATH, f'//*[@id="{CELL_OUTPUT_ID}"]//pre'),
            'Running on public URL:'
        ))
    except TimeoutException:
        raise RuntimeError('cannot execute the python program')

    output = driver.find_element(By.XPATH, f"//*[@id='{CELL_OUTPUT_ID}']//pre")

    list = url_regexp.findall(output.text)
    if len(list) == 0:
        raise RuntimeError(f"cannot find url by pattern {url_regexp.pattern}")
    
    logger.info(f'the latest url link is {list[0]}')
    
    global APP_URL
    APP_URL = list[0]

    keep_page_active()
    save_cookie()

def login_google_acc(gmail: str, password: str) -> None:
    try:
        # No account logged in yet
        try:
            # click "Sign in"
            login = WebDriverWait(driver, 5).until(
                lambda t_driver: t_driver.find_element(By.XPATH, '//*[@id="gb"]/div/div/a')
            )
            driver.get(login.get_attribute('href'))

        # Already logged in
        except TimeoutException:

            profile = driver.find_element(By.XPATH, '//*[@class="gb_A gb_Ma gb_f"]').get_attribute('aria-label')

            print(f'currently logged in: {profile}')

            # logged in with correct account
            if gmail in profile:
                return

            # logout current account
            logout = WebDriverWait(driver, 5).until(
                lambda t_driver: t_driver.find_element(
                    By.XPATH, '//*[@id="gb"]/div/div[1]/div[2]/div/a'
                )
            )
            driver.get(logout.get_attribute('href'))
            driver.find_element(By.XPATH, '//*[@id="signout"]').click()

            # click "Sign in"
            login = WebDriverWait(driver, 5).until(
                lambda t_driver: t_driver.find_element(By.XPATH, '//*[@id="gb"]/div/div/a')
            )
            driver.get(login.get_attribute('href'))

        # if prompt, choose "Use another account" when login
        try:
            wait_and_click_element(
                by=By.XPATH,
                value='//*[@id="view_container"]/div/div/div[2]/div/div[1]/div/form/span/section/div/div/div/div/ul'
                      '/li[@class="JDAKTe eARute W7Aapd zpCp3 SmR8" and not(@jsname="fKeql")]'
            )
        except TimeoutException:
            pass

        # input gmail and password
        gmail_input = WebDriverWait(driver, 5).until(expected_conditions.element_to_be_clickable(
            (By.XPATH, '//*[@id="identifierId"]')
        ))
        driver.execute_script("arguments[0].click();", gmail_input)
        sleep(0.5)
        gmail_input.send_keys(gmail, Keys.ENTER)

        pwd_input = WebDriverWait(driver, 5).until(expected_conditions.element_to_be_clickable(
            (By.XPATH, '//*[@id="password"]/div[1]/div/div[1]/input')
        ))
        driver.execute_script("arguments[0].click();", pwd_input)
        sleep(0.5)
        pwd_input.send_keys(password, Keys.ENTER)

        # check if the password is incorrect
        try:
            WebDriverWait(driver, 3).until(
                lambda t_driver: t_driver.find_element(
                    By.XPATH, '//*[@id="yDmH0d"]/c-wiz/div/div[2]/div/div[1]/div/form/span/div[1]/div[2]/div[1]'
                )
            )
            raise RuntimeError(f"Google账号 {gmail} 的密码填写有误！")
        except TimeoutException:
            logger.info(f"成功登入Google账号：{gmail}！")

    except TimeoutException:
        driver.save_screenshot('profile/timeout.png')
        raise RuntimeError(f"登陆Google账号 {gmail} 发生超时，请检查网络和账密！")

    # In case of Google asking you to complete your account info
    try:
        # Wait for "not now" button occurs
        wait_and_click_element(
            by=By.XPATH, value='//*[@id="yDmH0d"]/c-wiz/div/div/div/div[2]/div[4]/div[1]/button'
        )

    # If that doesn't happen
    except TimeoutException:
        pass

def force_refresh_webpage(url: str) -> None:
    driver.get(url)
    try:
        driver.switch_to.alert.accept()
    except NoAlertPresentException:
        pass

def wait_and_click_element(by: str, value: str) -> any:
    element = WebDriverWait(driver, 5).until(
        lambda t_driver: t_driver.find_element(by, value)
    )
    WebDriverWait(driver, 3).until(
        expected_conditions.element_to_be_clickable((by, value))
    )
    #element.click()
    driver.execute_script("arguments[0].click();", element)

    sleep(0.1)
    return element

def keep_page_active():
    # keep webpage active
    driver.execute_script("""
        function ConnectButton(){
            console.log("Connect pushed");
            document.querySelector("#top-toolbar > colab-connect-button").shadowRoot.querySelector("#connect").click()
        }
        setInterval(ConnectButton,60000);
    """) 

def save_cookie():
    try:
        cookies = driver.get_cookies()
        if not cookies:
            return
        with open(COOKIE_PATH, 'w') as filehandler:
            json.dump(cookies, filehandler)
    except Exception as e:
        logger.warning(f'cookie saving failed: {e}')

def load_cookie():
    try:
        with open(COOKIE_PATH, 'r') as cookiesfile:
            cookies = json.load(cookiesfile)
        for cookie in cookies:
            driver.add_cookie(cookie)
    except Exception as  e:
        logger.warning(f'cookie loading failed: {e}')


def quit_driver():
    logger.info('closing server... please wait')
    save_cookie()
    driver.quit()
    if display:
        display.stop()



if __name__ == '__main__':
    run_colab(EMAIL, PASSWORD)