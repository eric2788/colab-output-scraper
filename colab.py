import undetected_chromedriver.v2 as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from pyvirtualdisplay import Display
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.common.exceptions import TimeoutException, NoAlertPresentException, JavascriptException, WebDriverException, NoSuchElementException
from time import sleep
import regex, json, os, sys
from constrants import *
import logging
from webdriver import init_driver

APP_URL = ""

logger = logging.getLogger('colab')

url_regexp = regex.compile(r'Running\son\spublic\sURL:\s(https:\/\/[a-f0-9]+\.gradio\.app)', regex.S | regex.M)

display: Display = None

if sys.platform.startswith('linux'):
    # use this to replace headless
    display = Display(visible=0, size=(800, 600))
    display.start()

driver = init_driver()

os.makedirs(DATA_DIR, exist_ok=True)

# copy from net
def run_colab(gmail: str, password: str) -> None:
    global driver
    try:

        logger.info('开始运行colab....')

        driver.get('https://colab.research.google.com')
        load_cookie()

        logger.info('正在刷新 colab notebook 页面...')
        force_refresh_webpage(NOTEBOOK_URL)
        logger.info('刷新完毕')

        logger.info('开始登入 google 账号...')
        login_google_acc(gmail, password)

        sleep(3)
        try:
            wait = WebDriverWait(driver, 30)
            wait.until(expected_conditions.visibility_of(driver.find_element(By.ID, CELL_OUTPUT_ID)))
        except JavascriptException:
            raise RuntimeError(
                f"Google账密验证成功，但找不到 ID 为 {CELL_OUTPUT_ID} 的储存格，可能是Colab页面没有被成功加载，又或者填写有误"
                f"当前账号：{gmail}"
            )

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
                by=By.XPATH, value='/html/body/colab-dialog/paper-dialog/div[2]/paper-button[2]'
            )
            logger.info('colab 出现确认运行页面，已成功点击确认')
        except TimeoutException:
            pass

        try:
            logger.info('正在运行并等待相关字眼出现...')
            wait = WebDriverWait(driver, 15 * 60)
            wait.until(expected_conditions.text_to_be_present_in_element(
                (By.XPATH, f'//*[@id="{CELL_OUTPUT_ID}"]//pre'),
                'Running on public URL:'
            ))
        except TimeoutException:
            try:
                output = driver.find_element(By.XPATH, f'//*[@id="{CELL_OUTPUT_ID}"]//pre').text
                if not output:
                    raise RuntimeError('colab 运行超时，但是没有输出')
                else:
                    logger.warning(f'colab 运行超时，输出内容如下:')
                    for output in output.split('\n'):
                        logger.warning(output)
                    raise RuntimeError('运行逾时: 无法在output中找到相关字眼，可能是Colab运行失败')
            except NoSuchElementException:
                raise RuntimeError(f'运行逾时, 且找不到输出内容的元素')

        output = driver.find_element(By.XPATH, f"//*[@id='{CELL_OUTPUT_ID}']//pre")

        list = url_regexp.findall(output.text)
        if len(list) == 0:
            raise RuntimeError(f"无法透过 {url_regexp.pattern} 找到地址，可能是Colab运行失败或pattern有误: {output.text}")
        
        logger.info(f'执行成功。最新的链接地址为 {list[0]}')
        
        global APP_URL
        APP_URL = list[0]

        keep_page_active()
    except WebDriverException as e:
        if "session deleted" in str(e.msg) or "page crash" in str(e.msg):
            logger.warn(f'运行chromedriver报错: {e}')
            logger.warn('正在重新初始化chromedriver...')
            driver = init_driver()
            raise RuntimeError(f'运行colab时报错: {e}, 请重试')
        else:
            raise e
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
                logger.info(f'目前登入账户: {profile}')
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
            logger.info(f"成功登入Google账号：{gmail}")
            save_cookie()

    except TimeoutException:
        driver.save_screenshot('profile/timeout.png')
        raise RuntimeError(f"登陆Google账号 {gmail} 发生超时，请检查网络和账密")

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
    logger.info('成功执行保持页面连接的JS代码')

def save_cookie():
    try:
        cookies = driver.get_cookies()
        if not cookies:
            return
        with open(COOKIE_PATH, 'w') as filehandler:
            json.dump(cookies, filehandler)
            logger.info('成功保存Cookie')
    except Exception as e:
        logger.warning(f'保存Cookie失败: {e}')

def load_cookie():
    try:
        with open(COOKIE_PATH, 'r') as cookiesfile:
            cookies = json.load(cookiesfile)
        for cookie in cookies:
            driver.add_cookie(cookie)
        logger.info('成功加载Cookie')
    except Exception as  e:
        logger.warning(f'加载Cookie失败: {e}')

def quit_driver():
    logger.info('正在关闭chromedriver...')
    save_cookie()
    driver.quit()
    if display:
        display.stop()

if __name__ == '__main__':
    run_colab(EMAIL, PASSWORD)