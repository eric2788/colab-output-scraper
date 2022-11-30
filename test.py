from webdriver import init_driver, escape_recaptcha
from unittest import TestCase, main
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait
from time import sleep

class EscapeRecaptchaTest(TestCase):

    def setUp(self):
        self.driver = init_driver()


    def test_recaptcha(self):
        self.driver.get('https://recaptcha-demo.appspot.com/recaptcha-v2-checkbox.php')
        wait = WebDriverWait(self.driver, 10)
        wait.until(expected_conditions.frame_to_be_available_and_switch_to_it(
            (By.XPATH, "//iframe[starts-with(@name, 'a-') and starts-with(@src, 'https://www.google.com/recaptcha')]")
        ))
        wait = WebDriverWait(self.driver, 10)
        wait.until(
            expected_conditions.element_to_be_clickable((
                By.XPATH, "//div[@class='recaptcha-checkbox-checkmark']"
            ))
        )

        sleep(1)

        element = self.driver.find_element(By.XPATH, "//div[@class='recaptcha-checkbox-checkmark']")
        self.driver.execute_script('arguments[0].click()', element)

        sleep(5)

        anchor = self.driver.find_element(By.ID, 'recaptcha-anchor').get_attribute('class')
        self.assertIn('recaptcha-checkbox-checked', anchor)

        self.driver.switch_to.default_content()
        self.driver.find_element(By.XPATH, '//button[@type="submit"]').click()

        sleep(5)

        wait = WebDriverWait(self.driver, 10)
        wait.until(expected_conditions.text_to_be_present_in_element((By.XPATH, '//main'), 'Success'))

    def tearDown(self):
        self.driver.quit()

if __name__ == '__main__':
    main()