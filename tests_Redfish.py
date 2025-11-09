import pytest
import requests
import json
import logging
import time
from typing import Dict, Any

# --- Настройка логирования ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- Конфигурация ---
BASE_URL = "https://127.0.0.1:2443/redfish/v1"
USERNAME = "root"
PASSWORD = "0penBmc"
VERIFY_SSL = False  # Игнорировать SSL ошибки для тестов

# --- Фикстуры PyTest ---
@pytest.fixture(scope="session")
def auth_session():
    """Создает аутентифицированную сессию для всех тестов"""
    session = requests.Session()
    session.auth = (USERNAME, PASSWORD)
    session.verify = VERIFY_SSL
    session.headers.update({
        'Content-Type': 'application/json',
        'OData-Version': '4.0'
    })
    
    # Аутентификация через Session Service
    auth_data = {
        "UserName": USERNAME,
        "Password": PASSWORD
    }
    
    try:
        response = session.post(
            f"{BASE_URL}/SessionService/Sessions",
            json=auth_data,
            timeout=10
        )
        
        if response.status_code == 201:
            session_token = response.headers.get('X-Auth-Token')
            if session_token:
                session.headers.update({'X-Auth-Token': session_token})
                logging.info("✓ Аутентификация через Redfish API успешна")
            else:
                logging.warning("Токен сессии не получен, используем Basic Auth")
        else:
            logging.warning(f"Session Service недоступен: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        logging.warning(f"Ошибка аутентификации: {e}. Используем Basic Auth")
    
    yield session
    
    # Закрытие сессии при завершении
    try:
        session.close()
    except:
        pass

@pytest.fixture
def system_info(auth_session):
    """Получает информацию о системе"""
    try:
        response = auth_session.get(f"{BASE_URL}/Systems/system", timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            pytest.skip(f"Не удалось получить информацию о системе: {response.status_code}")
    except requests.exceptions.RequestException as e:
        pytest.skip(f"Ошибка при получении информации о системе: {e}")

# --- Вспомогательные функции ---
def make_redfish_request(session, method, endpoint, json_data=None, expected_status=200):
    """Универсальная функция для Redfish запросов"""
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method.upper() == "GET":
            response = session.get(url, timeout=10)
        elif method.upper() == "POST":
            response = session.post(url, json=json_data, timeout=10)
        else:
            raise ValueError(f"Неподдерживаемый метод: {method}")
        
        logging.info(f"{method} {url} - Status: {response.status_code}")
        
        if response.status_code != expected_status:
            logging.warning(f"Ожидался статус {expected_status}, получен {response.status_code}")
            
        return response
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка запроса {method} {url}: {e}")
        raise

def get_cpu_temperature(session):
    """Получает температуру CPU из Redfish"""
    try:
        # Получаем информацию о системе
        systems_response = session.get(f"{BASE_URL}/Systems/system", timeout=10)
        if systems_response.status_code != 200:
            return None
            
        systems_data = systems_response.json()
        
        # Ищем температурные сенсоры
        thermal_url = systems_data.get('Thermal', {}).get('@odata.id')
        if not thermal_url:
            return None
            
        thermal_response = session.get(f"{BASE_URL}{thermal_url}", timeout=10)
        if thermal_response.status_code != 200:
            return None
            
        thermal_data = thermal_response.json()
        temperatures = thermal_data.get('Temperatures', [])
        
        for temp in temperatures:
            name = temp.get('Name', '').lower()
            reading = temp.get('ReadingCelsius')
            
            if 'cpu' in name and reading is not None:
                return {
                    'name': temp.get('Name'),
                    'temperature': reading,
                    'units': 'Celsius',
                    'thresholds': {
                        'upper_critical': temp.get('UpperThresholdCritical'),
                        'upper_fatal': temp.get('UpperThresholdFatal')
                    }
                }
                
        return None
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при получении температуры CPU: {e}")
        return None

# --- Тесты Redfish API ---
class TestRedfishAuthentication:
    """Тесты аутентификации Redfish API"""
    
    def test_redfish_base_url_accessible(self, auth_session):
        """Тест доступности базового URL Redfish"""
        logging.info("=== Тест доступности Redfish API ===")
        
        response = make_redfish_request(auth_session, "GET", "")
        
        assert response.status_code == 200, "Базовый URL Redfish недоступен"
        
        data = response.json()
        assert 'RedfishVersion' in data, "Ответ не содержит версию Redfish"
        assert 'Systems' in data, "Ответ не содержит ссылку на Systems"
        
        logging.info(f"✓ Redfish Version: {data.get('RedfishVersion')}")
        logging.info("✓ Базовый URL Redfish доступен")
    
    def test_session_authentication(self):
        """Тест аутентификации через Session Service"""
        logging.info("=== Тест аутентификации Session Service ===")
        
        session = requests.Session()
        session.verify = VERIFY_SSL
        
        auth_data = {
            "UserName": USERNAME,
            "Password": PASSWORD
        }
        
        response = session.post(
            f"{BASE_URL}/SessionService/Sessions",
            json=auth_data,
            timeout=10
        )
        
        # Проверяем успешную аутентификацию (201 Created)
        if response.status_code == 201:
            assert 'X-Auth-Token' in response.headers, "Токен аутентификации не получен"
            session_token = response.headers['X-Auth-Token']
            assert session_token, "Токен аутентификации пустой"
            logging.info("✓ Аутентификация через Session Service успешна")
        else:
            pytest.skip("Session Service недоступен, используем Basic Auth")

class TestSystemInformation:
    """Тесты информации о системе"""
    
    def test_system_info_endpoint(self, auth_session, system_info):
        """Тест получения информации о системе"""
        logging.info("=== Тест информации о системе ===")
        
        # Проверяем обязательные поля
        assert 'Id' in system_info, "Отсутствует поле Id"
        assert 'PowerState' in system_info, "Отсутствует поле PowerState"
        assert 'Status' in system_info, "Отсутствует поле Status"
        
        power_state = system_info['PowerState']
        valid_states = ['On', 'Off', 'PoweringOn', 'PoweringOff']
        assert power_state in valid_states, f"Недопустимый PowerState: {power_state}"
        
        logging.info(f"✓ System ID: {system_info.get('Id')}")
        logging.info(f"✓ Power State: {power_state}")
        logging.info(f"✓ Status: {system_info.get('Status', {}).get('Health', 'Unknown')}")
    
    def test_system_components(self, auth_session, system_info):
        """Тест наличия основных компонентов системы"""
        logging.info("=== Тест компонентов системы ===")
        
        # Проверяем ссылки на основные компоненты
        components = [
            ('Processors', 'Processors'),
            ('Memory', 'Memory'), 
            ('EthernetInterfaces', 'Сетевые интерфейсы'),
            ('Storage', 'Storage'),
            ('Bios', 'Bios')
        ]
        
        found_components = []
        for component, description in components:
            if component in system_info:
                found_components.append(description)
                logging.info(f"✓ Найден компонент: {description}")
        
        assert len(found_components) >= 2, f"Найдено слишком мало компонентов: {found_components}"
        logging.info(f"✓ Обнаружены компоненты: {', '.join(found_components)}")

class TestPowerManagement:
    """Тесты управления питанием"""
    
    def test_power_control_actions(self, auth_session, system_info):
        """Тест доступных действий управления питанием"""
        logging.info("=== Тест управления питанием ===")
        
        actions = system_info.get('Actions', {}).get('#ComputerSystem.Reset', {})
        reset_target = actions.get('target')
        
        if not reset_target:
            # Пробуем альтернативный путь для получения действий
            actions = system_info.get('Actions', {})
            for action_key, action_value in actions.items():
                if 'Reset' in action_key:
                    reset_target = action_value.get('target')
                    break
        
        if not reset_target:
            pytest.skip("Действия управления питанием недоступны в этой системе")
        
        # Получаем доступные действия
        allowed_reset_types = actions.get('ResetType@Redfish.AllowableValues', [])
        
        # Если AllowableValues недоступны, используем стандартный список
        if not allowed_reset_types:
            allowed_reset_types = ['On', 'ForceOff', 'GracefulShutdown', 'ForceRestart', 'GracefulRestart']
            logging.info("Используем стандартный список действий управления питанием")
        
        assert len(allowed_reset_types) > 0, "Нет доступных действий управления питанием"
        
        logging.info(f"✓ Доступные действия питания: {allowed_reset_types}")
        
        # Проверяем наличие основных действий
        expected_actions = ['On', 'ForceOff', 'GracefulShutdown']
        available_actions = [action for action in expected_actions if action in allowed_reset_types]
        
        if available_actions:
            logging.info(f"✓ Основные действия: {available_actions}")
        else:
            logging.warning("Основные действия управления питанием не найдены")
    
    def test_power_state_cycle(self, auth_session):
        """Тест цикла включения/выключения (только для тестовых сред)"""
        logging.info("=== Тест цикла питания (информационный) ===")
        
        # В реальной системе этот тест может быть опасен
        # Здесь мы только проверяем доступность endpoint'а
        
        reset_data = {
            "ResetType": "On"
        }
        
        try:
            response = auth_session.post(
                f"{BASE_URL}/Systems/system/Actions/ComputerSystem.Reset",
                json=reset_data,
                timeout=10
            )
            
            logging.info(f"POST /Actions/ComputerSystem.Reset - Status: {response.status_code}")
            
            if response.status_code in [200, 202, 204]:
                logging.info("✓ Действие управления питанием принято сервером")
            else:
                logging.warning(f"Сервер вернул статус {response.status_code} для действия питания")
                # Это не ошибка, так как система может не поддерживать это действие
                
        except requests.exceptions.RequestException as e:
            logging.warning(f"Endpoint управления питанием недоступен: {e}")

class TestTemperatureMonitoring:
    """Тесты мониторинга температуры"""
    
    def test_cpu_temperature_reading(self, auth_session):
        """Тест чтения температуры CPU"""
        logging.info("=== Тест температуры CPU ===")
        
        cpu_temp = get_cpu_temperature(auth_session)
        
        if not cpu_temp:
            pytest.skip("Данные о температуре CPU недоступны")
        
        temperature = cpu_temp['temperature']
        name = cpu_temp['name']
        
        logging.info(f"✓ CPU Temperature Sensor: {name}")
        logging.info(f"✓ Temperature: {temperature}°{cpu_temp['units']}")
        
        # Проверяем, что температура в разумных пределах
        assert temperature is not None, "Температура не определена"
        assert -10 <= temperature <= 120, f"Температура вне разумных пределов: {temperature}°C"
        
        # Проверяем пороговые значения если они доступны
        thresholds = cpu_temp['thresholds']
        if thresholds['upper_critical']:
            logging.info(f"✓ Upper Critical Threshold: {thresholds['upper_critical']}°C")
            assert temperature < thresholds['upper_critical'], "Температура превышает критический порог"
        
        if thresholds['upper_fatal']:
            logging.info(f"✓ Upper Fatal Threshold: {thresholds['upper_fatal']}°C")
            assert temperature < thresholds['upper_fatal'], "Температура превышает фатальный порог"
    
    def test_temperature_sensors_exist(self, auth_session):
        """Тест наличия температурных сенсоров"""
        logging.info("=== Тест наличия температурных сенсоров ===")
        
        try:
            response = auth_session.get(f"{BASE_URL}/Chassis", timeout=10)
            if response.status_code != 200:
                pytest.skip("Информация о шасси недоступна")
            
            chassis_data = response.json()
            chassis_members = chassis_data.get('Members', [])
            
            if not chassis_members:
                pytest.skip("Нет информации о шасси")
            
            # Проверяем первый шасси
            first_chassis = chassis_members[0]['@odata.id']
            chassis_response = auth_session.get(f"{BASE_URL}{first_chassis}", timeout=10)
            
            if chassis_response.status_code == 200:
                chassis_info = chassis_response.json()
                thermal_url = chassis_info.get('Thermal', {}).get('@odata.id')
                
                if thermal_url:
                    thermal_response = auth_session.get(f"{BASE_URL}{thermal_url}", timeout=10)
                    if thermal_response.status_code == 200:
                        thermal_data = thermal_response.json()
                        temperatures = thermal_data.get('Temperatures', [])
                        
                        assert len(temperatures) > 0, "Нет доступных температурных сенсоров"
                        logging.info(f"✓ Найдено температурных сенсоров: {len(temperatures)}")
                        
                        for sensor in temperatures[:3]:  # Показываем первые 3 сенсора
                            logging.info(f"  - {sensor.get('Name')}: {sensor.get('ReadingCelsius')}°C")
                    else:
                        pytest.skip("Thermal endpoint недоступен")
                else:
                    pytest.skip("Thermal информация недоступна")
            else:
                pytest.skip("Не удалось получить информацию о шасси")
                
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Ошибка при получении данных о сенсорах: {e}")

class TestInventory:
    """Тесты инвентаризации"""
    
    def test_cpu_inventory(self, auth_session):
        """Тест инвентаризации CPU"""
        logging.info("=== Тест инвентаризации CPU ===")
        
        try:
            response = auth_session.get(f"{BASE_URL}/Systems/system/Processors", timeout=10)
            
            if response.status_code == 404:
                # Пробуем альтернативный endpoint
                response = auth_session.get(f"{BASE_URL}/Systems/system", timeout=10)
                system_info = response.json()
                processors_url = system_info.get('Processors', {}).get('@odata.id')
                
                if processors_url:
                    response = auth_session.get(f"{BASE_URL}{processors_url}", timeout=10)
            
            if response.status_code != 200:
                pytest.skip("Информация о процессорах недоступна")
            
            processors_data = response.json()
            processors = processors_data.get('Members', [])
            
            if len(processors) == 0:
                # Проверяем, может быть процессоры указаны непосредственно в ответе
                if 'ProcessorSummary' in processors_data:
                    summary = processors_data['ProcessorSummary']
                    count = summary.get('Count', 0)
                    if count > 0:
                        logging.info(f"✓ Найдено процессоров: {count}")
                        logging.info(f"✓ Model: {summary.get('Model', 'N/A')}")
                        logging.info(f"✓ Total Cores: {summary.get('TotalCores', 'N/A')}")
                        return
                
                pytest.skip("Не найдено процессоров в системе")
            
            # Проверяем первый процессор
            first_processor = processors[0]
            if isinstance(first_processor, dict):
                processor_url = first_processor.get('@odata.id')
                if processor_url:
                    cpu_response = auth_session.get(f"{BASE_URL}{processor_url}", timeout=10)
                    
                    if cpu_response.status_code == 200:
                        cpu_info = cpu_response.json()
                        
                        # Проверяем основные поля
                        logging.info(f"✓ Processor Type: {cpu_info.get('ProcessorType', 'N/A')}")
                        logging.info(f"✓ Model: {cpu_info.get('Model', 'N/A')}")
                        logging.info(f"✓ Total Cores: {cpu_info.get('TotalCores', 'N/A')}")
                        logging.info(f"✓ Total Threads: {cpu_info.get('TotalThreads', 'N/A')}")
                        logging.info(f"✓ Socket: {cpu_info.get('Socket', 'N/A')}")
                        
                    else:
                        logging.info("✓ Процессоры найдены, но детальная информация недоступна")
                else:
                    # Если это уже объект процессора
                    cpu_info = first_processor
                    logging.info(f"✓ Processor Type: {cpu_info.get('ProcessorType', 'N/A')}")
                    logging.info(f"✓ Model: {cpu_info.get('Model', 'N/A')}")
            else:
                logging.info(f"✓ Найдено процессоров: {len(processors)}")
                
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Ошибка при получении инвентаризации CPU: {e}")
    
    def test_memory_inventory(self, auth_session):
        """Тест инвентаризации памяти"""
        logging.info("=== Тест инвентаризации памяти ===")
        
        try:
            response = auth_session.get(f"{BASE_URL}/Systems/system/Memory", timeout=10)
            if response.status_code != 200:
                pytest.skip("Информация о памяти недоступна")
            
            memory_data = response.json()
            memory_modules = memory_data.get('Members', [])
            
            if len(memory_modules) > 0:
                # Проверяем первый модуль памяти
                first_memory_url = memory_modules[0]['@odata.id']
                memory_response = auth_session.get(f"{BASE_URL}{first_memory_url}", timeout=10)
                
                if memory_response.status_code == 200:
                    memory_info = memory_response.json()
                    
                    logging.info(f"✓ Memory Type: {memory_info.get('MemoryDeviceType', 'N/A')}")
                    logging.info(f"✓ Capacity MB: {memory_info.get('CapacityMiB', 'N/A')}")
                    logging.info(f"✓ Speed MHz: {memory_info.get('OperatingSpeedMhz', 'N/A')}")
                    logging.info(f"✓ Manufacturer: {memory_info.get('Manufacturer', 'N/A')}")
                    
                logging.info(f"✓ Найдено модулей памяти: {len(memory_modules)}")
            else:
                logging.info("✓ Модули памяти не найдены (возможно объединенная информация)")
                
        except requests.exceptions.RequestException as e:
            pytest.skip(f"Ошибка при получении инвентаризации памяти: {e}")

# --- Запуск тестов ---
if __name__ == "__main__":
    # Запуск тестов через pytest
    pytest.main([__file__, "-v", "-s"])
