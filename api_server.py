"""
🌐 API СЕРВЕР ДЛЯ ANDROID ПРИЛОЖЕНИЯ
Запускается на Render.com, подключается к локальному LDAP серверу в сети t2
"""

import os
import requests
import logging
import json
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
import urllib3

# Отключаем предупреждения о самоподписанных сертификатах
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ================== НАСТРОЙКА ЛОГГИНГА ==================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ================== КОНФИГУРАЦИЯ ==================

class Config:
    """Конфигурация из переменных окружения Render.com"""
    
    # 🔐 URL вашего локального LDAP сервера (самое важное!)
    LDAP_SERVER_URL = os.environ.get('LDAP_SERVER_URL', '')
    # Формат: https://ВАШ_ВНЕШНИЙ_IP:8443/api/ldap/auth
    # Пример: https://95.165.123.456:8443/api/ldap/auth
    
    # 📊 Данные регионов (опционально)
    DATA_API_URL = os.environ.get('DATA_API_URL', '')
    
    # ⚙️ Настройки запросов
    REQUEST_TIMEOUT = int(os.environ.get('REQUEST_TIMEOUT', 15))  # Увеличил таймаут
    VERIFY_SSL = os.environ.get('VERIFY_SSL', 'false').lower() == 'true'
    
    # 🔧 Фолбэк режим (если LDAP недоступен)
    FALLBACK_MODE = os.environ.get('FALLBACK_MODE', 'true').lower() == 'true'
    
    # 📝 Тестовые пользователи для фолбэка
    FALLBACK_USERS = {
        'admin': 'admin123',
        'test@t2.ru': 'Test123!',
        'danil.vasilchenko@t2.ru': 'Daniil2024!',
        'user@t2.ru': 'User123!'
    }
    
    # 📍 Фолбэк данные регионов
    FALLBACK_REGIONS = {
        'BRT': {
            'region_name': 'Бурятия',
            'base_layer': '📡 Основной слой: 142 БС\n✅ Работают: 139\n⚠️ Проблемы: 3',
            'non_priority': '📶 Технологии: 4G-92%, 3G-8%',
            'stats': {
                'total_bs': 150,
                'base_layer_count': 142,
                'power_problems': 3,
                'non_priority_percentage': 5
            }
        },
        'OMS': {
            'region_name': 'Омская область',
            'base_layer': '📡 Основной слой: 215 БС\n✅ Работают: 210\n⚠️ Проблемы: 5',
            'non_priority': '📶 Технологии: 4G-95%, 3G-5%',
            'stats': {
                'total_bs': 230,
                'base_layer_count': 215,
                'power_problems': 5,
                'non_priority_percentage': 2
            }
        },
        'TEST': {
            'region_name': 'Тестовый регион',
            'base_layer': '📡 Тестовые данные\n✅ Все работает\n⚠️ Нет проблем',
            'non_priority': '📶 Технологии: 4G-100%',
            'stats': {
                'total_bs': 100,
                'base_layer_count': 100,
                'power_problems': 0,
                'non_priority_percentage': 0
            }
        }
    }

# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================

def make_secure_request(url, method='GET', data=None, headers=None):
    """
    Безопасный HTTP запрос с поддержкой самоподписанных сертификатов
    """
    try:
        logger.info(f"📡 {method} запрос к: {url}")
        
        request_kwargs = {
            'timeout': Config.REQUEST_TIMEOUT,
            'verify': Config.VERIFY_SSL,  # Важно: False для самоподписанных
            'headers': headers or {'Content-Type': 'application/json'}
        }
        
        if method.upper() == 'POST' and data:
            request_kwargs['json'] = data
        
        start_time = datetime.now()
        
        if method.upper() == 'POST':
            response = requests.post(url, **request_kwargs)
        elif method.upper() == 'GET':
            response = requests.get(url, **request_kwargs)
        else:
            return {'success': False, 'error': f'Неподдерживаемый метод: {method}'}
        
        response_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"📨 Ответ {response.status_code} за {response_time:.2f}с")
        
        if response.status_code == 200:
            return {
                'success': True,
                'data': response.json(),
                'status_code': response.status_code,
                'response_time': response_time
            }
        else:
            return {
                'success': False,
                'error': f'HTTP {response.status_code}',
                'status_code': response.status_code,
                'response_text': response.text[:200]
            }
            
    except requests.exceptions.SSLError as e:
        logger.error(f"🔒 Ошибка SSL: {e}")
        return {
            'success': False,
            'error': 'Ошибка SSL сертификата',
            'details': 'Используйте самоподписанный сертификат или настройте verify=False'
        }
    except requests.exceptions.Timeout:
        logger.error(f"⏰ Таймаут {Config.REQUEST_TIMEOUT}с")
        return {
            'success': False,
            'error': f'Таймаут подключения ({Config.REQUEST_TIMEOUT}с)',
            'details': 'LDAP сервер не ответил. Проверьте доступность и порты.'
        }
    except requests.exceptions.ConnectionError as e:
        logger.error(f"🔌 Ошибка подключения: {e}")
        return {
            'success': False,
            'error': 'Ошибка подключения',
            'details': f'Не удалось подключиться к серверу. Проверьте URL и доступность.'
        }
    except Exception as e:
        logger.error(f"❌ Ошибка запроса: {e}")
        return {
            'success': False,
            'error': 'Внутренняя ошибка запроса',
            'details': str(e)[:100]
        }

def check_fallback_credentials(username, password):
    """Проверка учетных данных в фолбэк режиме"""
    if username in Config.FALLBACK_USERS:
        if Config.FALLBACK_USERS[username] == password:
            return {
                'success': True,
                'username': username,
                'display_name': username.split('@')[0] if '@' in username else username,
                'email': username if '@' in username else f'{username}@t2.ru',
                'department': 'Технический отдел',
                'title': 'Пользователь системы',
                'auth_source': 'fallback_mode'
            }
    
    return {
        'success': False,
        'error': 'Неверные учетные данные',
        'error_code': 'INVALID_CREDENTIALS'
    }

# ================== API ENDPOINTS ==================

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    """
    🔐 Основная точка аутентификации
    Подключается к вашему локальному LDAP серверу
    """
    start_time = datetime.now()
    
    try:
        # Получаем данные
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Требуется JSON тело запроса',
                'error_code': 'NO_JSON_BODY'
            }), 400
        
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({
                'success': False,
                'error': 'Требуется имя пользователя и пароль',
                'error_code': 'MISSING_CREDENTIALS'
            }), 400
        
        client_ip = request.remote_addr
        logger.info(f"🔐 Запрос авторизации от {client_ip}, пользователь: {username}")
        
        # 🔧 ШАГ 1: Пробуем подключиться к LDAP серверу
        if Config.LDAP_SERVER_URL:
            logger.info(f"📡 Подключаюсь к LDAP: {Config.LDAP_SERVER_URL}")
            
            ldap_result = make_secure_request(
                url=Config.LDAP_SERVER_URL,
                method='POST',
                data={'username': username, 'password': password}
            )
            
            if ldap_result['success']:
                # Успешная аутентификация через LDAP
                result = ldap_result['data']
                result.update({
                    'api_server': 'dostupnost_api_render',
                    'auth_flow': 'ldap_direct',
                    'response_time_ms': int((datetime.now() - start_time).total_seconds() * 1000),
                    'ldap_server_url': Config.LDAP_SERVER_URL,
                    'client_ip': client_ip,
                    'timestamp': datetime.now().isoformat()
                })
                
                logger.info(f"✅ Успешная LDAP аутентификация: {username}")
                return jsonify(result), 200
            else:
                # Ошибка подключения к LDAP
                logger.warning(f"⚠️ Ошибка LDAP: {ldap_result.get('error')}")
                
                # 🔧 ШАГ 2: Пробуем фолбэк режим если включен
                if Config.FALLBACK_MODE:
                    logger.info("🔄 Пробую фолбэк режим...")
                    fallback_result = check_fallback_credentials(username, password)
                    
                    if fallback_result['success']:
                        fallback_result.update({
                            'api_server': 'dostupnost_api_render',
                            'auth_flow': 'fallback_mode',
                            'warning': 'Используется фолбэк аутентификация. LDAP сервер недоступен.',
                            'ldap_error': ldap_result.get('error'),
                            'response_time_ms': int((datetime.now() - start_time).total_seconds() * 1000),
                            'timestamp': datetime.now().isoformat()
                        })
                        
                        logger.info(f"✅ Успешная фолбэк аутентификация: {username}")
                        return jsonify(fallback_result), 200
                
                # Возвращаем ошибку LDAP
                return jsonify({
                    'success': False,
                    'error': ldap_result.get('error', 'Ошибка авторизации'),
                    'details': ldap_result.get('details', ''),
                    'error_code': 'LDAP_CONNECTION_ERROR',
                    'timestamp': datetime.now().isoformat(),
                    'suggestions': [
                        'Проверьте доступность LDAP сервера',
                        'Убедитесь что порт 8443 открыт на роутере',
                        'Проверьте правильность LDAP_SERVER_URL'
                    ]
                }), 503  # 503 Service Unavailable
        else:
            # LDAP_SERVER_URL не настроен
            logger.error("❌ LDAP_SERVER_URL не настроен в Render.com")
            
            # 🔧 ШАГ 3: Только фолбэк режим
            if Config.FALLBACK_MODE:
                fallback_result = check_fallback_credentials(username, password)
                
                if fallback_result['success']:
                    fallback_result.update({
                        'api_server': 'dostupnost_api_render',
                        'auth_flow': 'fallback_only',
                        'warning': 'LDAP сервер не настроен. Используется только фолбэк режим.',
                        'response_time_ms': int((datetime.now() - start_time).total_seconds() * 1000),
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    logger.info(f"✅ Фолбэк аутентификация (без LDAP): {username}")
                    return jsonify(fallback_result), 200
            
            return jsonify({
                'success': False,
                'error': 'Сервер авторизации не настроен',
                'error_code': 'LDAP_NOT_CONFIGURED',
                'instructions': 'Настройте переменную LDAP_SERVER_URL в Render.com Dashboard',
                'example': 'LDAP_SERVER_URL = https://ваш_внешний_ip:8443/api/ldap/auth',
                'timestamp': datetime.now().isoformat()
            }), 503
            
    except Exception as e:
        logger.error(f"💥 Критическая ошибка в auth_login: {e}")
        return jsonify({
            'success': False,
            'error': 'Внутренняя ошибка сервера',
            'error_code': 'SERVER_ERROR',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/region/<region_code>', methods=['GET'])
def get_region_data(region_code):
    """
    🗺️ Получение данных региона
    Подключается к локальному Data API если настроено
    """
    try:
        region_code = region_code.upper()
        logger.info(f"🗺️ Запрос региона: {region_code}")
        
        # 🔧 Пробуем локальный Data API
        if Config.DATA_API_URL:
            data_url = f"{Config.DATA_API_URL}/api/region/{region_code}"
            result = make_secure_request(data_url, method='GET')
            
            if result['success']:
                data = result['data']
                data.update({
                    'source': 'external_data_api',
                    'api_timestamp': datetime.now().isoformat(),
                    'data_server': Config.DATA_API_URL
                })
                logger.info(f"✅ Данные получены из Data API")
                return jsonify(data)
        
        # 📌 Фолбэк данные
        if region_code in Config.FALLBACK_REGIONS:
            data = Config.FALLBACK_REGIONS[region_code].copy()
            data.update({
                'success': True,
                'region_code': region_code,
                'is_fallback': True,
                'source': 'fallback_data',
                'api_timestamp': datetime.now().isoformat(),
                'warning': 'Используются тестовые данные' if not Config.DATA_API_URL else 'Data API недоступен'
            })
            logger.info(f"📋 Используются фолбэк данные для {region_code}")
            return jsonify(data)
        
        # ❌ Регион не найден
        return jsonify({
            'success': False,
            'error': f'Регион {region_code} не найден',
            'available_regions': list(Config.FALLBACK_REGIONS.keys()),
            'timestamp': datetime.now().isoformat()
        }), 404
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения региона {region_code}: {e}")
        return jsonify({
            'success': False,
            'error': 'Ошибка получения данных',
            'region_code': region_code,
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/test/ldap', methods=['GET'])
def test_ldap_connection():
    """
    🧪 Тестирование подключения к LDAP серверу
    """
    test_results = {
        'test': 'ldap_connection_test',
        'timestamp': datetime.now().isoformat(),
        'config': {
            'ldap_server_url': Config.LDAP_SERVER_URL,
            'request_timeout': Config.REQUEST_TIMEOUT,
            'verify_ssl': Config.VERIFY_SSL,
            'fallback_mode': Config.FALLBACK_MODE
        },
        'tests': {}
    }
    
    # Тест 1: Проверка конфигурации
    test_results['tests']['config_check'] = {
        'passed': bool(Config.LDAP_SERVER_URL),
        'message': 'LDAP_SERVER_URL настроен' if Config.LDAP_SERVER_URL else 'LDAP_SERVER_URL не настроен',
        'url': Config.LDAP_SERVER_URL or 'не указан'
    }
    
    # Тест 2: Пинг LDAP сервера (если настроен)
    if Config.LDAP_SERVER_URL:
        try:
            # Пробуем получить health status от LDAP сервера
            health_url = Config.LDAP_SERVER_URL.replace('/api/ldap/auth', '/api/ldap/health')
            
            result = make_secure_request(health_url, method='GET')
            
            test_results['tests']['ldap_health'] = {
                'passed': result['success'],
                'message': result.get('error', 'Успешно') if not result['success'] else 'LDAP сервер доступен',
                'response_time': result.get('response_time'),
                'status_code': result.get('status_code')
            }
        except Exception as e:
            test_results['tests']['ldap_health'] = {
                'passed': False,
                'message': f'Ошибка теста: {str(e)}'
            }
    
    # Тест 3: Тестовая аутентификация
    test_results['tests']['test_auth'] = {
        'available': True,
        'test_users': list(Config.FALLBACK_USERS.keys()) if Config.FALLBACK_MODE else [],
        'message': 'Фолбэк режим включен' if Config.FALLBACK_MODE else 'Только LDAP'
    }
    
    # Общая оценка
    passed_tests = [t for t in test_results['tests'].values() if t.get('passed', False)]
    if len(passed_tests) == len(test_results['tests']):
        test_results['overall'] = 'PASSED'
    elif len(passed_tests) > 0:
        test_results['overall'] = 'PARTIAL'
    else:
        test_results['overall'] = 'FAILED'
    
    return jsonify(test_results)

@app.route('/api/test', methods=['GET'])
def test_api():
    """🧪 Полный тест API сервера"""
    return jsonify({
        'service': 'dostupnost_api',
        'status': 'running',
        'timestamp': datetime.now().isoformat(),
        'version': '2.0.0',
        'config_summary': {
            'ldap_configured': bool(Config.LDAP_SERVER_URL),
            'data_api_configured': bool(Config.DATA_API_URL),
            'fallback_mode': Config.FALLBACK_MODE,
            'request_timeout': Config.REQUEST_TIMEOUT
        },
        'endpoints': [
            {'method': 'POST', 'path': '/api/auth/login', 'desc': 'Аутентификация'},
            {'method': 'GET', 'path': '/api/region/{code}', 'desc': 'Данные региона'},
            {'method': 'GET', 'path': '/api/test/ldap', 'desc': 'Тест LDAP'},
            {'method': 'GET', 'path': '/api/test', 'desc': 'Тест API'},
            {'method': 'GET', 'path': '/api/health', 'desc': 'Здоровье'}
        ],
        'available_regions': list(Config.FALLBACK_REGIONS.keys()),
        'instructions': {
            'setup_ldap': 'Настройте LDAP_SERVER_URL = https://ваш_ip:8443/api/ldap/auth',
            'test_auth': 'Используйте test@t2.ru / Test123! для теста'
        }
    })

@app.route('/api/health', methods=['GET'])
def health_check():
    """Проверка здоровья API"""
    return jsonify({
        'status': 'healthy',
        'service': 'dostupnost_api',
        'environment': 'production',
        'timestamp': datetime.now().isoformat(),
        'checks': {
            'api_server': 'running',
            'ldap_configured': bool(Config.LDAP_SERVER_URL),
            'fallback_available': Config.FALLBACK_MODE
        }
    })

@app.route('/')
def home():
    """Домашняя страница"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🌐 Dostupnost API</title>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
            .card {{ background: #f5f5f5; padding: 20px; margin: 20px 0; border-radius: 8px; }}
            .success {{ color: #4CAF50; font-weight: bold; }}
            .warning {{ color: #FF9800; font-weight: bold; }}
            .error {{ color: #f44336; font-weight: bold; }}
            code {{ background: #eee; padding: 2px 6px; border-radius: 3px; }}
            pre {{ background: #f8f8f8; padding: 10px; border-radius: 5px; overflow-x: auto; }}
        </style>
    </head>
    <body>
        <h1>🌐 Dostupnost API Server</h1>
        <p>API сервер для Android приложения мониторинга доступности</p>
        
        <div class="card">
            <h2>⚙️ Конфигурация</h2>
            <p>LDAP сервер: <span class="{'success' if Config.LDAP_SERVER_URL else 'error'}">
                {Config.LDAP_SERVER_URL or '❌ НЕ НАСТРОЕН'}
            </span></p>
            <p>Data API: <span class="{'success' if Config.DATA_API_URL else 'warning'}">
                {Config.DATA_API_URL or '⚠️ ОПЦИОНАЛЬНО'}
            </span></p>
            <p>Фолбэк режим: <span class="{'success' if Config.FALLBACK_MODE else 'warning'}">
                {'✅ ВКЛЮЧЕН' if Config.FALLBACK_MODE else '⚠️ ВЫКЛЮЧЕН'}
            </span></p>
        </div>
        
        <div class="card">
            <h2>🔗 Основные Endpoints</h2>
            <ul>
                <li><code>POST /api/auth/login</code> - Аутентификация через LDAP</li>
                <li><code>GET /api/region/{code}</code> - Данные региона (BRT, OMS, TEST)</li>
                <li><code>GET /api/test/ldap</code> - Тест подключения к LDAP</li>
                <li><code>GET /api/test</code> - Полный тест системы</li>
                <li><code>GET /api/health</code> - Проверка здоровья</li>
            </ul>
        </div>
        
        <div class="card">
            <h2>🔧 Настройка LDAP сервера</h2>
            <p>1. Убедитесь что LDAP сервер запущен на вашем компьютере</p>
            <p>2. Откройте порт 8443 на роутере:</p>
            <pre>Внешний порт: 8443 → Внутренний IP: [ваш IP]:8443</pre>
            <p>3. Узнайте ваш внешний IP:</p>
            <pre>curl ifconfig.me</pre>
            <p>4. В Render.com Dashboard добавьте переменную:</p>
            <pre>LDAP_SERVER_URL = https://[ВАШ_ВНЕШНИЙ_IP]:8443/api/ldap/auth</pre>
        </div>
        
        <div class="card">
            <h2>🧪 Тестирование</h2>
            <p><a href="/api/test">Полный тест системы</a></p>
            <p><a href="/api/test/ldap">Тест LDAP подключения</a></p>
            <p><a href="/api/health">Проверка здоровья</a></p>
        </div>
        
        <div class="card">
            <h2>📱 Тестовые пользователи (фолбэк)</h2>
            <ul>
                <li><code>admin</code> / <code>admin123</code></li>
                <li><code>test@t2.ru</code> / <code>Test123!</code></li>
                <li><code>danil.vasilchenko@t2.ru</code> / <code>Daniil2024!</code></li>
            </ul>
        </div>
    </body>
    </html>
    """

# ================== ЗАПУСК СЕРВЕРА ==================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    
    print("=" * 70)
    print("🌐 DOSTUPNOST API СЕРВЕР НА RENDER.COM")
    print("Подключение к локальному LDAP серверу")
    print("=" * 70)
    
    print(f"\n⚙️  ТЕКУЩАЯ КОНФИГУРАЦИЯ:")
    print(f"   • LDAP сервер:    {Config.LDAP_SERVER_URL or '❌ НЕ НАСТРОЕН'}")
    print(f"   • Data API:       {Config.DATA_API_URL or '⚠️  ОПЦИОНАЛЬНО'}")
    print(f"   • Таймаут:        {Config.REQUEST_TIMEOUT} секунд")
    print(f"   • Фолбэк режим:   {'✅ ВКЛЮЧЕН' if Config.FALLBACK_MODE else '⚠️ ВЫКЛЮЧЕН'}")
    print(f"   • Проверка SSL:   {'✅ ВКЛЮЧЕНА' if Config.VERIFY_SSL else '⚠️ ОТКЛЮЧЕНА (самоподписанные)'}")
    
    print(f"\n📋 ДОСТУПНЫЕ ENDPOINTS:")
    print(f"   • POST /api/auth/login    - Аутентификация")
    print(f"   • GET  /api/region/BRT    - Данные Бурятии")
    print(f"   • GET  /api/test/ldap     - Тест LDAP")
    print(f"   • GET  /api/test          - Тест системы")
    print(f"   • GET  /api/health        - Проверка здоровья")
    
    print(f"\n🔧 ИНСТРУКЦИЯ ДЛЯ НАСТРОЙКИ:")
    print(f"   1. Запустите LDAP сервер на вашем компьютере")
    print(f"   2. Откройте порт 8443 на роутере:")
    print(f"      Внешний порт 8443 → Внутренний IP:8443")
    print(f"   3. Узнайте ваш внешний IP:")
    print(f"      На компьютере выполните: curl ifconfig.me")
    print(f"   4. В Render.com Dashboard добавьте:")
    print(f"      LDAP_SERVER_URL = https://[ВАШ_IP]:8443/api/ldap/auth")
    
    print(f"\n📱 ДЛЯ ANDROID ПРИЛОЖЕНИЯ:")
    print(f"   В файле ApiClient.kt укажите:")
    print(f'   private const val BASE_URL = "https://ваш-сервис.onrender.com/"')
    
    print(f"\n⚠️  ВАЖНЫЕ ЗАМЕЧАНИЯ:")
    print(f"   • LDAP сервер использует самоподписанный SSL сертификат")
    print(f"   • Для запросов установлен verify=False")
    print(f"   • При недоступности LDAP работает фолбэк режим")
    print("=" * 70)
    
    print(f"\n🚀 Запуск API сервера на порту {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
