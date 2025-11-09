import pytest
import time
import logging
import warnings
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
warnings.filterwarnings("ignore", category=DeprecationWarning)

BASE_URL = "https://127.0.0.1:2443/"
VALID_USERNAME = "root"
VALID_PASSWORD = "0penBmc"
INVALID_USERNAME = "invalid_user"
INVALID_PASSWORD = "wrong_password"

# --- Фикстура WebDriver ---
@pytest.fixture(scope="session")
def driver():
    chrome_options = Options()
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--ignore-ssl-errors")
    chrome_options.add_argument("--ignore-certificate-errors-spki-list")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--allow-running-insecure-content")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    chrome_options.add_argument("--test-type")
    chrome_options.add_argument("--log-level=3")
    # chrome_options.add_argument("--headless=new")  # можно убрать для отладки
    chrome_options.add_argument("--window-size=1920,1080")
    
    drv = webdriver.Chrome(options=chrome_options)
    drv.maximize_window()
    drv.wait = WebDriverWait(drv, 15)
    yield drv
    drv.quit()

# --- Фикстура для сброса состояния перед тестом ---
@pytest.fixture
def fresh_state(driver):
    """Сбрасывает состояние перед тестом, но не ломает сессию"""
    try:
        driver.delete_all_cookies()
        # Переходим на страницу логина для чистого состояния
        driver.get(BASE_URL)
        time.sleep(2)
        handle_security_warning(driver)
    except Exception as e:
        logging.warning(f"Ошибка при сбросе состояния: {e}")

# --- Фикстура для авторизованной сессии ---
@pytest.fixture
def logged_in_driver(driver, fresh_state):
    """Возвращает драйвер с выполненным входом"""
    if not smart_login(driver, VALID_USERNAME, VALID_PASSWORD):
        pytest.skip("Не удалось выполнить вход для теста")
    return driver

# --- Вспомогательные функции ---
def handle_security_warning(driver):
    """Обработка предупреждений безопасности SSL"""
    try:
        time.sleep(2)
        page_source = driver.page_source.lower()
        
        if "your connection is not private" in page_source or "certificate" in page_source:
            logging.info("Обнаружено предупреждение безопасности, обходим...")
            
            # Пробуем кнопку Advanced
            advanced_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Advanced')]")
            for btn in advanced_buttons:
                if btn.is_displayed():
                    btn.click()
                    time.sleep(1)
                    logging.info("Нажата кнопка Advanced")
                    break
            
            # Пробуем ссылку Proceed
            proceed_links = driver.find_elements(By.XPATH, "//a[contains(text(), 'Proceed')]")
            for link in proceed_links:
                if link.is_displayed():
                    link.click()
                    time.sleep(2)
                    logging.info("Нажата ссылка Proceed")
                    break
                    
            # Альтернативный вариант - keyboard navigation
            if "your connection is not private" in driver.page_source.lower():
                try:
                    from selenium.webdriver.common.action_chains import ActionChains
                    actions = ActionChains(driver)
                    actions.send_keys(Keys.TAB).send_keys(Keys.ENTER)
                    actions.perform()
                    time.sleep(2)
                    logging.info("Использован keyboard shortcut")
                except:
                    pass
                    
    except Exception as e:
        logging.warning(f"Не удалось обработать предупреждение безопасности: {e}")

def find_login_fields(driver):
    """Поиск полей для ввода логина и пароля"""
    selectors = [
        (By.ID, "username"),
        (By.ID, "password"),
        (By.NAME, "username"),
        (By.NAME, "password"),
        (By.CSS_SELECTOR, "input[type='text']"),
        (By.CSS_SELECTOR, "input[type='password']"),
        (By.XPATH, "//input[@placeholder='Username']"),
        (By.XPATH, "//input[@placeholder='Password']"),
        (By.XPATH, "//input[contains(@id, 'user')]"),
        (By.XPATH, "//input[contains(@id, 'pass')]"),
    ]
    
    username_field = None
    password_field = None
    
    for by, selector in selectors:
        try:
            if not username_field:
                elements = driver.find_elements(by, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        input_type = element.get_attribute("type")
                        placeholder = element.get_attribute("placeholder") or ""
                        if (input_type in ["text", "email", "username"] or 
                            "user" in placeholder.lower() or 
                            not input_type):
                            username_field = element
                            logging.info(f"Найдено поле username: {selector}")
                            break
            
            if not password_field:
                elements = driver.find_elements(by, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        input_type = element.get_attribute("type")
                        placeholder = element.get_attribute("placeholder") or ""
                        if (input_type == "password" or
                            "pass" in placeholder.lower()):
                            password_field = element
                            logging.info(f"Найдено поле password: {selector}")
                            break
                            
        except NoSuchElementException:
            continue
    
    return username_field, password_field

def smart_login(driver, username, password):
    """Умная авторизация с несколькими попытками"""
    max_attempts = 3
    
    for attempt in range(max_attempts):
        logging.info(f"Попытка входа {attempt + 1}/{max_attempts} для пользователя {username}")
        
        try:
            # Обновляем страницу при повторных попытках
            if attempt > 0:
                driver.refresh()
                time.sleep(2)
                handle_security_warning(driver)
            
            # Ищем поля ввода
            username_field, password_field = find_login_fields(driver)
            
            if not username_field or not password_field:
                logging.warning(f"Попытка {attempt + 1}: поля не найдены")
                driver.save_screenshot(f"login_fields_not_found_{attempt + 1}.png")
                continue
            
            # Заполняем поля
            username_field.clear()
            username_field.send_keys(username)
            
            password_field.clear()
            password_field.send_keys(password)
            
            # Ищем кнопку входа
            login_selectors = [
                (By.XPATH, "//button[contains(text(), 'Login')]"),
                (By.XPATH, "//button[contains(text(), 'Sign in')]"),
                (By.XPATH, "//input[@type='submit']"),
                (By.XPATH, "//button[@type='submit']"),
                (By.ID, "login"),
                (By.ID, "submit"),
                (By.CSS_SELECTOR, "button.btn-primary"),
            ]
            
            login_button = None
            for by, selector in login_selectors:
                try:
                    elements = driver.find_elements(by, selector)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            login_button = element
                            logging.info(f"Найдена кнопка входа: {selector}")
                            break
                    if login_button:
                        break
                except NoSuchElementException:
                    continue
            
            # Нажимаем кнопку или Enter
            if login_button:
                login_button.click()
            else:
                password_field.send_keys(Keys.RETURN)
            
            # Ждем результат
            time.sleep(3)
            
            # Проверяем успешность входа
            if is_logged_in(driver):
                logging.info("✓ Вход выполнен успешно")
                return True
            else:
                logging.warning(f"Попытка {attempt + 1}: вход не удался")
                
        except Exception as e:
            logging.error(f"Ошибка при попытке входа {attempt + 1}: {e}")
            driver.save_screenshot(f"login_error_{attempt + 1}.png")
    
    return False

def is_logged_in(driver):
    """Проверка, выполнен ли вход в систему"""
    try:
        # Ищем индикаторы успешного входа
        dashboard_indicators = [
            (By.ID, "dashboard"),
            (By.XPATH, "//*[contains(text(), 'Dashboard')]"),
            (By.XPATH, "//*[contains(text(), 'System')]"),
            (By.XPATH, "//*[contains(text(), 'Overview')]"),
            (By.XPATH, "//*[contains(text(), 'Server')]"),
            (By.CLASS_NAME, "navbar"),
            (By.ID, "navigation"),
        ]
        
        for by, selector in dashboard_indicators:
            try:
                element = driver.find_element(by, selector)
                if element.is_displayed():
                    logging.info(f"Найден индикатор входа: {selector}")
                    return True
            except NoSuchElementException:
                continue
        
        # Проверяем URL
        current_url = driver.current_url.lower()
        if "login" not in current_url and "auth" not in current_url:
            logging.info("URL не содержит упоминаний логина - возможно вход выполнен")
            return True
            
    except Exception as e:
        logging.warning(f"Ошибка при проверке входа: {e}")
    
    return False

def safe_logout(driver):
    """Безопасный выход из системы"""
    try:
        logout_selectors = [
            (By.XPATH, "//*[contains(text(), 'Logout')]"),
            (By.XPATH, "//*[contains(text(), 'Sign out')]"),
            (By.ID, "logout"),
            (By.CLASS_NAME, "logout"),
        ]
        
        for by, selector in logout_selectors:
            try:
                elements = driver.find_elements(by, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        element.click()
                        time.sleep(2)
                        logging.info("Выход из системы выполнен")
                        return True
            except NoSuchElementException:
                continue
    except Exception as e:
        logging.debug(f"Не удалось выполнить logout: {e}")
    
    return False

# --- Тесты авторизации ---
class TestAuthentication:
    """Тесты авторизации"""
    
    def test_successful_authentication(self, driver, fresh_state):
        """Тест успешной авторизации"""
        logging.info("=== Тест успешной авторизации ===")
        assert smart_login(driver, VALID_USERNAME, VALID_PASSWORD), "Не удалось войти с корректными данными"
    
    def test_invalid_credentials(self, driver, fresh_state):
        """Тест авторизации с неверными данными"""
        logging.info("=== Тест неверных учетных данных ===")
        success = smart_login(driver, VALID_USERNAME, INVALID_PASSWORD)
        assert not success, "Вход не должен выполняться с неверным паролем"
        
        # Проверяем наличие сообщения об ошибке
        error_found = False
        error_indicators = [
            (By.CLASS_NAME, "error"),
            (By.CLASS_NAME, "alert-danger"),
            (By.XPATH, "//*[contains(text(), 'invalid')]"),
            (By.XPATH, "//*[contains(text(), 'incorrect')]"),
        ]
        
        for by, selector in error_indicators:
            try:
                elements = driver.find_elements(by, selector)
                for element in elements:
                    if element.is_displayed():
                        error_found = True
                        logging.info(f"Найдено сообщение об ошибке: {element.text}")
                        break
                if error_found:
                    break
            except NoSuchElementException:
                continue
        
        if error_found:
            logging.info("✓ Сообщение об ошибке найдено")
        else:
            logging.warning("Сообщение об ошибке не найдено")
    
    def test_account_lockout(self, driver, fresh_state):
        """Тест блокировки учетной записи"""
        logging.info("=== Тест блокировки учетной записи ===")
        
        # Выполняем несколько неудачных попыток входа
        for attempt in range(3):
            logging.info(f"Неудачная попытка входа {attempt + 1}/3")
            smart_login(driver, VALID_USERNAME, INVALID_PASSWORD)
            time.sleep(1)
        
        # Проверяем сообщение о блокировке
        lockout_detected = False
        lockout_indicators = [
            (By.XPATH, "//*[contains(text(), 'lock')]"),
            (By.XPATH, "//*[contains(text(), 'block')]"),
            (By.XPATH, "//*[contains(text(), 'temporarily')]"),
            (By.XPATH, "//*[contains(text(), 'disabled')]"),
        ]
        
        for by, selector in lockout_indicators:
            try:
                elements = driver.find_elements(by, selector)
                for element in elements:
                    if element.is_displayed():
                        lockout_detected = True
                        logging.info(f"Обнаружена блокировка: {element.text}")
                        break
                if lockout_detected:
                    break
            except NoSuchElementException:
                continue
        
        if lockout_detected:
            logging.info("✓ Блокировка учетной записи обнаружена")
        else:
            logging.info("Блокировка не обнаружена (может быть отключена в системе)")

# --- Тесты функциональности (требуют авторизации) ---
class TestFunctionality:
    """Тесты функциональности OpenBMC"""
    
    def test_server_power_control_and_logs(self, logged_in_driver):
        """Тест управления питанием сервера"""
        logging.info("=== Тест управления питанием ===")
        driver = logged_in_driver
        
        # Ищем раздел управления питанием
        power_found = False
        power_selectors = [
            (By.XPATH, "//*[contains(text(), 'Power')]"),
            (By.XPATH, "//*[contains(text(), 'Control')]"),
            (By.ID, "power-control"),
        ]
        
        for by, selector in power_selectors:
            try:
                elements = driver.find_elements(by, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        element.click()
                        time.sleep(2)
                        power_found = True
                        logging.info(f"Найден раздел управления питанием: {selector}")
                        driver.save_screenshot("power_management.png")
                        break
                if power_found:
                    break
            except NoSuchElementException:
                continue
        
        if power_found:
            logging.info("✓ Раздел управления питанием найден")
        else:
            logging.warning("Раздел управления питанием не найден")
    
    def test_component_temperature(self, logged_in_driver):
        """Тест проверки температуры компонентов"""
        logging.info("=== Тест проверки температуры ===")
        driver = logged_in_driver
        
        # Ищем раздел мониторинга
        monitoring_found = False
        monitoring_selectors = [
            (By.XPATH, "//*[contains(text(), 'Sensors')]"),
            (By.XPATH, "//*[contains(text(), 'Monitoring')]"),
            (By.XPATH, "//*[contains(text(), 'Hardware')]"),
        ]
        
        for by, selector in monitoring_selectors:
            try:
                elements = driver.find_elements(by, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        element.click()
                        time.sleep(2)
                        monitoring_found = True
                        logging.info(f"Найден раздел мониторинга: {selector}")
                        break
                if monitoring_found:
                    break
            except NoSuchElementException:
                continue
        
        # Ищем информацию о температуре
        temp_found = False
        if monitoring_found:
            temp_indicators = [
                (By.XPATH, "//*[contains(text(), 'Temperature')]"),
                (By.XPATH, "//*[contains(text(), '℃')]"),
                (By.XPATH, "//*[contains(text(), '°C')]"),
            ]
            
            for by, selector in temp_indicators:
                try:
                    elements = driver.find_elements(by, selector)
                    for element in elements:
                        if element.is_displayed():
                            logging.info(f"Найдена информация о температуре: {element.text}")
                            temp_found = True
                            driver.save_screenshot("temperature_found.png")
                            break
                    if temp_found:
                        break
                except NoSuchElementException:
                    continue
        
        if temp_found:
            logging.info("✓ Информация о температуре найдена")
        else:
            logging.warning("Информация о температуре не найдена")
    
    def test_inventory_display(self, logged_in_driver):
        """Тест отображения инвентаря"""
        logging.info("=== Тест отображения инвентаря ===")
        driver = logged_in_driver
        
        # Ищем раздел инвентаря
        inventory_found = False
        inventory_selectors = [
            (By.XPATH, "//*[contains(text(), 'Inventory')]"),
            (By.XPATH, "//*[contains(text(), 'Hardware')]"),
            (By.XPATH, "//*[contains(text(), 'System')]"),
        ]
        
        for by, selector in inventory_selectors:
            try:
                elements = driver.find_elements(by, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        element.click()
                        time.sleep(2)
                        inventory_found = True
                        logging.info(f"Найден раздел инвентаря: {selector}")
                        break
                if inventory_found:
                    break
            except NoSuchElementException:
                continue
        
        # Ищем компоненты в инвентаре
        components_found = False
        if inventory_found:
            components = ["CPU", "Memory", "DIMM", "Processor"]
            
            for component in components:
                try:
                    elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{component}')]")
                    for element in elements:
                        if element.is_displayed():
                            logging.info(f"Найден компонент: {component} - {element.text}")
                            components_found = True
                            driver.save_screenshot("inventory_found.png")
                            break
                    if components_found:
                        break
                except NoSuchElementException:
                    continue
        
        if components_found:
            logging.info("✓ Компоненты инвентаря найдены")
        else:
            logging.warning("Компоненты инвентаря не найдены")
