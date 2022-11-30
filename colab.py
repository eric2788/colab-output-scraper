
import logging
import os
import re
import sys
from time import sleep
from threading import Thread

from pyvirtualdisplay import Display
from selenium.common.exceptions import (JavascriptException,
                                        NoSuchElementException,
                                        TimeoutException, WebDriverException)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

from constrants import CELL_OUTPUT_ID, DATA_DIR, EMAIL, NOTEBOOK_URL, PASSWORD
from webdriver import (force_refresh_webpage, init_driver, keep_page_active,
                       load_cookie, save_cookie, wait_and_click_element, escape_recaptcha)

APP_URL = ""
STOP = False

recaptcha_checking_thread: Thread = None

logger = logging.getLogger(__name__)

url_regexp = re.compile(r'Running on public URL: (https:\/\/[a-f0-9]+\.gradio\.app)', re.S | re.M)

display: Display = None

if sys.platform.startswith('linux'):
    # use this to replace headless
    display = Display(visible=0, size=(1280, 720))
    display.start()

driver = init_driver()
recaptcha_checking_thread: Thread = None

os.makedirs(DATA_DIR, exist_ok=True)

# copy from net
def run_colab(gmail: str, password: str) -> None:

    global driver
    try:

        logger.info('开始运行colab....')

        driver.get('https://colab.research.google.com')
        load_cookie(driver)

        logger.info('正在刷新 colab notebook 页面...')
        force_refresh_webpage(driver, NOTEBOOK_URL)
        logger.info('刷新完毕')

        logger.info('开始登入 google 账号...')
        login_google_acc(gmail, password)

        sleep(3)
        try:
            wait = WebDriverWait(driver, 30)
            wait.until(expected_conditions.visibility_of(driver.find_element(By.ID, CELL_OUTPUT_ID)))
        except JavascriptException as ex:
            raise RuntimeError(
                f"Google账密验证成功，但找不到 ID 为 {CELL_OUTPUT_ID} 的储存格，可能是Colab页面没有被成功加载，又或者填写有误"
                f"当前账号：{gmail}"
            ) from ex

        logger.info('成功跳转到 colab 页面')

        running_status = driver.find_element(By.XPATH, f'//*[@id="{CELL_OUTPUT_ID}"]').get_attribute('class')
        if "running" in running_status:
            logger.info("发现有储存格正在运行，尝试终止...")
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
                logger.info('成功终止储存格运行')
            except TimeoutException:
                logger.warning('储存格终止失败，可能是储存格运行时间过长，或者储存格运行已经结束')

            sleep(3)

        logger.info('正在删除旧的输出...')

        driver.execute_script(f"""
            document.querySelector('#{CELL_OUTPUT_ID}  iron-icon[command=clear-focused-or-selected-outputs]').click()
        """)

        sleep(2)

        logger.info('删除完毕，开始运行所有储存格...')

        # run all cells
        driver.find_element(By.XPATH, '/html/body').send_keys(Keys.CONTROL + Keys.F9)

        # If Google asks you to confirm running this notebook
        try:
            wait_and_click_element(
                driver,
                by=By.XPATH, value='/html/body/colab-dialog/paper-dialog/div[2]/paper-button[2]'
            )
            logger.info('colab 出现确认运行页面，已成功点击确认')
        except TimeoutException:
            pass

        escape_recaptcha(driver)

        try:
            logger.info('正在运行并等待相关字眼出现...')
            wait = WebDriverWait(driver, 15 * 60)
            wait.until(expected_conditions.text_to_be_present_in_element(
                (By.XPATH, f'//*[@id="{CELL_OUTPUT_ID}"]//pre'),
                'Running on public URL:'
            ))
        except TimeoutException as ex:
            try:
                output = driver.find_element(By.XPATH, f'//*[@id="{CELL_OUTPUT_ID}"]//pre').text
                if not output:
                    raise RuntimeError('colab 运行超时，但是没有输出，可能被机器人挡住？') from ex
                else:
                    logger.warning('colab 运行超时，输出内容如下:')
                    for output in output.split('\n'):
                        logger.warning(output)
                    raise RuntimeError('运行逾时: 无法在output中找到相关字眼，可能是Colab运行失败') from ex
            except NoSuchElementException as exc:
                raise RuntimeError('运行逾时, 且找不到输出内容的元素') from exc

        output = driver.find_element(By.XPATH, f"//*[@id='{CELL_OUTPUT_ID}']//pre")

        urls = url_regexp.findall(output.text)
        if len(urls) == 0:
            raise RuntimeError(f"无法透过 {url_regexp.pattern} 找到地址，可能是Colab运行失败或pattern有误: {output.text}")
        
        logger.info('执行成功。最新的链接地址为 %s', urls[0])
        
        global APP_URL
        APP_URL = urls[0]

        keep_page_active(driver)
        logger.info('成功执行保持页面连接的JS代码')
    except WebDriverException as ex:
        if "session deleted" in str(ex.msg) or "page crash" in str(ex.msg):
            logger.warning('运行chromedriver报错: %s', ex.msg)
            logger.warning('正在重新初始化chromedriver...')
            driver = init_driver()
            raise RuntimeError(f'运行colab时报错: {ex}, 请重试') from ex
        else:
            raise ex
    finally:
        driver.save_screenshot(f'{DATA_DIR}/checkpoint.png')
        logger.info('成功保存上一个检查点的截图')

def login_google_acc(gmail: str, password: str) -> None:
    try:
        # No account logged in yet
        try:
            logger.info('正在寻找登入按钮...')
            # click "Sign in"
            login = WebDriverWait(driver, 5).until(
                lambda t_driver: t_driver.find_element(By.XPATH, '//*[@id="gb"]/div/div/a')
            )
            driver.get(login.get_attribute('href'))

        # Already logged in
        except TimeoutException:
            logger.info('找不到登入按钮，正在寻找目前登入用户资讯...')
            try:
                profile = driver.find_element(By.XPATH, '//*[@class="gb_A gb_Ma gb_f"]').get_attribute('aria-label')
                logger.info('目前登入账户: %s', profile)
                # logged in with correct account
                if gmail in profile:
                    logger.info('已经登入正确账户，无需再次登入')
                    return
            except NoSuchElementException:
                logger.info('找不到登入用户资讯')

            # logout current account
            logger.info('正在尝试登出当前账户...')
            logout = WebDriverWait(driver, 5).until(
                lambda t_driver: t_driver.find_element(
                    By.XPATH, '//*[@id="gb"]/div/div[1]/div[2]/div/a'
                )
            )
            driver.get(logout.get_attribute('href'))
            driver.find_element(By.XPATH, '//*[@id="signout"]').click()

            # click "Sign in"
            logger.info('正在重新登入...')
            login = WebDriverWait(driver, 5).until(
                lambda t_driver: t_driver.find_element(By.XPATH, '//*[@id="gb"]/div/div/a')
            )
            driver.get(login.get_attribute('href'))

        # if prompt, choose "Use another account" when login
        try:
            wait_and_click_element(
                driver,
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
        logger.info('填写电邮成功')

        pwd_input = WebDriverWait(driver, 5).until(expected_conditions.element_to_be_clickable(
            (By.XPATH, '//*[@id="password"]/div[1]/div/div[1]/input')
        ))
        driver.execute_script("arguments[0].click();", pwd_input)
        sleep(0.5)
        pwd_input.send_keys(password, Keys.ENTER)
        logger.info('填写密码成功')

        # check if the password is incorrect
        try:
            WebDriverWait(driver, 3).until(
                lambda t_driver: t_driver.find_element(
                    By.XPATH, '//*[@id="yDmH0d"]/c-wiz/div/div[2]/div/div[1]/div/form/span/div[1]/div[2]/div[1]'
                )
            )
            raise RuntimeError(f"Google账号 {gmail} 的密码填写有误！")
        except TimeoutException:
            logger.info("成功登入Google账号：%s", gmail)
            save_cookie(driver)

    except TimeoutException as ex:
        driver.save_screenshot('profile/timeout.png')
        raise RuntimeError(f"登陆Google账号 {gmail} 发生超时，请检查网络和账密") from ex

    # In case of Google asking you to complete your account info
    try:
        # Wait for "not now" button occurs
        wait_and_click_element(
            driver,
            by=By.XPATH, value='//*[@id="yDmH0d"]/c-wiz/div/div/div/div[2]/div[4]/div[1]/button'
        )

    # If that doesn't happen
    except TimeoutException:
        pass

def loop_check_recaptcha():
    while True:
        sleep(10)
        if not driver:
            continue
        if STOP:
            break
        escape_recaptcha(driver)

def stop_recaptcha_thread():
    if not recaptcha_checking_thread:
        logger.info('绕过recaptcha线程未启动, 已略过')
        return
    global STOP
    STOP = True
    recaptcha_checking_thread.join()
    logger.info('绕过recaptcha线程成功停止')

def start_recaptcha_thread():
    global recaptcha_checking_thread, STOP
    if recaptcha_checking_thread:
        logger.info('绕过recaptcha线程已启动, 已略过')
        return
    STOP = False
    logger.info('正在启动绕过recaptcha线程...')
    recaptcha_checking_thread = Thread(target=loop_check_recaptcha)
    recaptcha_checking_thread.start()
    logger.info('绕过recaptcha线程启动成功')

def quit_driver():
    logger.info('正在关闭chromedriver...')
    stop_recaptcha_thread()
    save_cookie(driver)
    driver.quit()
    if display:
        display.stop()
        
if __name__ == '__main__':
    run_colab(EMAIL, PASSWORD)