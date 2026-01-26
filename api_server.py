"""
🌐 API СЕРВЕР ДЛЯ ANDROID ПРИЛОЖЕНИЯ С HTTPS
Запускается на Render.com, связывается с локальными HTTPS серверами
"""

import os
import requests
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import logging
import urllib3
from typing import Dict, Optional

# Отключаем предупреждения о самоподписанных сертификатах
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ================== НАСТРОЙКА ЛОГГИНГА ==================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# ================== КОНФИГУРАЦИЯ ==================

class Config:
    """Конфигурация API сервера"""
    
    # ⚠️ ЭТИ ПЕРЕМЕННЫЕ НАСТРАИВАЮТСЯ В RENDER.COM DASHBOARD!
    # Settings → Environment → Add Environment Variable
    
    # URL твоего локального LDAP сервера (HTTPS!)
    LDAP_SERVER_URL = os.environ.get('LDAP_SERVER_URL', '')
    # Пример: https://95.165.123.456:8443
    
    # URL твоего локального Data API (HTTPS!)
    DATA_API_URL = os.environ.get('DATA_API_URL', '')
    # Пример: https://95.165.123.456:8444
    
    # Настройки запросов
    REQUEST_TIMEOUT = 10  # секунд
    VERIFY_SSL = False    # Не проверять SSL для самоподписанных сертификатов
    
    # Фолбэк данные
    FALLBACK_DATA = {
        'BRT': {
            'region_name': 'Бурятия (фолбэк данные)',
            'base_layer': '📡 Данные временно недоступны\n\nСервер данных обновляется...',
            'non_priority': '📶 Технологии: обновление данных...',
            'stats': {
                'total_bs': 150,
                'base_layer_count': 142,
                'power_problems': 3,
                'non_priority_percentage': 5
            }
        }
    }

# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================

def make_secure_request(url: str, method: str = 'GET', data: dict = None) -> dict:
    """
    Безопасный HTTP запрос с поддержкой HTTPS и самоподписанных сертификатов
    """
    try:
        logger.info(f"📡 Запрос {method} к: {url}")
        
        # Настраиваем параметры запроса
        request_kwargs = {
            'timeout': Config.REQUEST_TIMEOUT,
            'verify': Config.VERIFY_SSL,  # Важно: не проверяем SSL для самоподписанных
            'headers': {'Content-Type': 'application/json'}
        }
        
        # Добавляем данные для POST запроса
        if method.upper() == 'POST' and data:
            request_kwargs['json'] = data
        
        # Выполняем запрос
        if method.upper() == 'POST':
            response = requests.post(url, **request_kwargs)
        else:
            response = requests.get(url, **request_kwargs)
        
        logger.info(f"📨 Ответ {response.status_code} от {url}")
        
        if response.status_code == 200:
            return {
                'success': True,
                'data': response.json(),
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds()
            }
        else:
            error_text = response.text[:200] if response.text else 'No response body'
            return {
                'success': False,
                'error': f'HTTP {response.status_code}',
                'status_code': response.status_code,
                'details': error_text,
                'url': url
            }
            
    except requests.exceptions.SSLError as e:
        logger.error(f"🔒 Ошибка SSL при подключении к {url}: {e}")
        return {
            'success': False,
            'error': 'SSL ошибка',
            'details': 'Сертификат не доверен. Для самоподписанных сертификатов нужна настройка verify=False',
            'url': url
        }
    except requests.exceptions.Timeout:
        logger.error(f"⏰ Таймаут при запросе к {url}")
        return {
            'success': False,
            'error': 'Таймаут подключения',
            'details': f'Сервер {url} не ответил за {Config.REQUEST_TIMEOUT} секунд'
        }
    except requests.exceptions.ConnectionError:
        logger.error(f"🔌 Ошибка подключения к {url}")
        return {
            'success': False,
            'error': 'Ошибка подключения',
            'details': f'Не удалось подключиться к {url}. Проверьте доступность сервера и порты.'
        }
    except Exception as e:
        logger.error(f"❌ Ошибка при запросе к {url}: {e}")
        return {
            'success': False,
            'error': 'Внутренняя ошибка',
            'details': str(e)[:100]
        }

# ================== API ENDPOINTS ==================

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    """
    🔐 Аутентификация пользователя
    Работает через локальный HTTPS LDAP сервер
    """
    start_time = datetime.now()
    
    try:
        # Получаем данные от клиента
        data = request.json
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
        
        logger.info(f"🔐 Запрос авторизации для пользователя: {username}")
        
        # Проверяем настройки LDAP сервера
        if not Config.LDAP_SERVER_URL:
            logger.error("❌ LDAP_SERVER_URL не настроен в Render.com")
            return jsonify({
                'success': False,
                'error': 'Сервер авторизации не настроен',
                'instructions': 'Настройте переменную LDAP_SERVER_URL в Render.com Dashboard',
                'example': 'LDAP_SERVER_URL = https://ваш_ip:8443'
            }), 503
        
        # 📌 ФОЛБЭК: Тестовый пользователь (если LDAP не настроен или для теста)
        if username == 'admin' and password == 'admin':
            logger.info("👨‍💻 Используется тестовая учетка admin")
            return jsonify({
                'success': True,
                'username': 'admin',
                'display_name': 'Администратор (тест)',
                'auth_source': 'test',
                'timestamp': datetime.now().isoformat(),
                'warning': 'Используется тестовая авторизация',
                'ldap_server': Config.LDAP_SERVER_URL
            }), 200
        
        # Отправляем запрос на локальный LDAP сервер
        ldap_url = f"{Config.LDAP_SERVER_URL}/api/ldap/auth"
        logger.info(f"📡 Перенаправляю запрос на LDAP: {ldap_url}")
        
        ldap_result = make_secure_request(
            url=ldap_url,
            method='POST',
            data={'username': username, 'password': password}
        )
        
        # Обрабатываем результат
        if ldap_result['success']:
            result = ldap_result['data']
            result.update({
                'api_timestamp': datetime.now().isoformat(),
                'response_time_ms': int((datetime.now() - start_time).total_seconds() * 1000),
                'auth_flow': 'ldap_https_remote',
                'api_server': 'render.com'
            })
            logger.info(f"✅ Успешная авторизация через LDAP: {username}")
            return jsonify(result), 200
        else:
            # Ошибка LDAP сервера
            logger.warning(f"⚠️ Ошибка LDAP для {username}: {ldap_result.get('error')}")
            
            # Детальная информация об ошибке
            error_response = {
                'success': False,
                'error': ldap_result.get('error', 'Ошибка авторизации'),
                'details': ldap_result.get('details', ''),
                'timestamp': datetime.now().isoformat(),
                'ldap_server': Config.LDAP_SERVER_URL,
                'suggestion': 'Проверьте доступность LDAP сервера и правильность URL'
            }
            
            # Определяем код ответа
            if 'пароль' in str(ldap_result.get('error', '')).lower() or 'credential' in str(ldap_result.get('error', '')).lower():
                status_code = 401  # Неверные учетные данные
            elif 'timeout' in str(ldap_result.get('error', '')).lower() or 'connection' in str(ldap_result.get('error', '')).lower():
                status_code = 503  # Сервер недоступен
            else:
                status_code = 500  # Внутренняя ошибка
            
            return jsonify(error_response), status_code
            
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в /api/auth/login: {e}")
        return jsonify({
            'success': False,
            'error': 'Внутренняя ошибка сервера',
            'timestamp': datetime.now().isoformat(),
            'error_details': str(e)[:200]
        }), 500

@app.route('/api/region/<region_code>', methods=['GET'])
def get_region_data(region_code):
    """
    🗺️ Получение данных региона
    """
    try:
        region_code = region_code.upper()
        logger.info(f"🗺️ Запрос данных региона: {region_code}")
        
        sources_tried = []
        
        # 🔧 ШАГ 1: Пробуем локальный Data API (HTTPS)
        if Config.DATA_API_URL:
            sources_tried.append('local_data_api_https')
            data_url = f"{Config.DATA_API_URL}/api/region/{region_code}"
            
            result = make_secure_request(data_url)
            
            if result['success']:
                data = result['data']
                data.update({
                    'source': 'local_data_api_https',
                    'api_timestamp': datetime.now().isoformat(),
                    'sources_tried': sources_tried,
                    'data_server': Config.DATA_API_URL
                })
                logger.info(f"✅ Данные получены из локального HTTPS API для {region_code}")
                return jsonify(data)
        
        # 🔧 ШАГ 2: Фолбэк данные
        sources_tried.append('fallback')
        if region_code in Config.FALLBACK_DATA:
            data = Config.FALLBACK_DATA[region_code].copy()
            data.update({
                'success': True,
                'region_code': region_code,
                'timestamp': datetime.now().strftime("%H:%M:%S"),
                'non_priority': '📶 Технологии: данные временно недоступны',
                'is_mock': True,
                'source': 'fallback',
                'sources_tried': sources_tried,
                'api_timestamp': datetime.now().isoformat(),
                'warning': 'Используются тестовые данные. Настройте DATA_API_URL.'
            })
            logger.warning(f"⚠️ Используются фолбэк данные для {region_code}")
            return jsonify(data)
        
        # 🔧 ШАГ 3: Регион не найден
        logger.error(f"❌ Регион не найден: {region_code}")
        return jsonify({
            'success': False,
            'error': f'Регион {region_code} не найден',
            'sources_tried': sources_tried,
            'timestamp': datetime.now().isoformat(),
            'suggestion': 'Настройте DATA_API_URL или добавьте регион в фолбэк данные'
        }), 404
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения данных региона {region_code}: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'region_code': region_code,
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/test', methods=['GET'])
def test_connection():
    """
    🧪 Тестовый endpoint
    Проверяет работу API и подключение ко всем сервисам
    """
    test_results = {
        'api_status': 'running',
        'timestamp': datetime.now().isoformat(),
        'server': 'dostupnost_api_render',
        'protocol': 'https',
        'config': {
            'ldap_server_url': Config.LDAP_SERVER_URL,
            'data_api_url': Config.DATA_API_URL,
            'has_ldap_config': bool(Config.LDAP_SERVER_URL),
            'has_data_api_config': bool(Config.DATA_API_URL),
            'ssl_verification': Config.VERIFY_SSL
        },
        'services': {},
        'endpoints': [
            {'method': 'POST', 'path': '/api/auth/login', 'description': 'Аутентификация'},
            {'method': 'GET', 'path': '/api/region/{code}', 'description': 'Данные региона'},
            {'method': 'GET', 'path': '/api/test', 'description': 'Тест системы'},
            {'method': 'GET', 'path': '/api/health', 'description': 'Проверка здоровья'}
        ]
    }
    
    # Проверяем LDAP сервер
    if Config.LDAP_SERVER_URL:
        ldap_health_url = f"{Config.LDAP_SERVER_URL}/api/ldap/health"
        ldap_check = make_secure_request(ldap_health_url)
        test_results['services']['ldap'] = {
            'url': Config.LDAP_SERVER_URL,
            'status': 'up' if ldap_check['success'] else 'down',
            'response': ldap_check
        }
    else:
        test_results['services']['ldap'] = {
            'status': 'not_configured',
            'error': 'LDAP_SERVER_URL не настроен'
        }
    
    # Проверяем Data API
    if Config.DATA_API_URL:
        data_test_url = f"{Config.DATA_API_URL}/api/test"
        data_check = make_secure_request(data_test_url)
        test_results['services']['data_api'] = {
            'url': Config.DATA_API_URL,
            'status': 'up' if data_check['success'] else 'down',
            'response': data_check
        }
    else:
        test_results['services']['data_api'] = {
            'status': 'not_configured',
            'error': 'DATA_API_URL не настроен'
        }
    
    # Определяем общий статус
    configured_services = [s for s in test_results['services'].values() 
                          if s.get('status') != 'not_configured']
    
    if not configured_services:
        overall_status = 'not_configured'
    elif all(s.get('status') == 'up' for s in configured_services):
        overall_status = 'healthy'
    elif any(s.get('status') == 'up' for s in configured_services):
        overall_status = 'degraded'
    else:
        overall_status = 'down'
    
    test_results['overall_status'] = overall_status
    
    return jsonify(test_results)

@app.route('/api/health', methods=['GET'])
def health_check():
    """Проверка здоровья API"""
    return jsonify({
        'status': 'healthy',
        'service': 'dostupnost_api',
        'version': '2.0.0',
        'timestamp': datetime.now().isoformat(),
        'environment': 'production',
        'features': ['https', 'ldap_auth', 'region_data']
    })

@app.route('/')
def home():
    """Домашняя страница"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🌐 Dostupnost API (HTTPS)</title>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
            .card {{ background: #f5f5f5; padding: 20px; margin: 20px 0; border-radius: 8px; }}
            .success {{ color: #4CAF50; }}
            .warning {{ color: #FF9800; }}
            .error {{ color: #f44336; }}
            code {{ background: #eee; padding: 2px 6px; border-radius: 3px; }}
            pre {{ background: #f8f8f8; padding: 10px; border-radius: 5px; overflow-x: auto; }}
        </style>
    </head>
    <body>
        <h1>🌐 Dostupnost API Server</h1>
        <p>HTTPS API сервер для Android приложения мониторинга доступности регионов</p>
        
        <div class="card">
            <h2>📱 Для Android приложения</h2>
            <p>В файле <code>ApiClient.kt</code> укажите HTTPS URL:</p>
            <pre>private const val BASE_URL = "https://dostupnost.onrender.com/"</pre>
        </div>
        
        <div class="card">
            <h2>⚙️ Конфигурация Render.com</h2>
            <p>В Dashboard Render.com настройте переменные окружения:</p>
            <ul>
                <li><code>LDAP_SERVER_URL = https://ваш_ip:8443</code> <span class="{'success' if Config.LDAP_SERVER_URL else 'error'}">({'Настроено' if Config.LDAP_SERVER_URL else 'Не настроено'})</span></li>
                <li><code>DATA_API_URL = https://ваш_ip:8444</code> <span class="{'success' if Config.DATA_API_URL else 'warning'}">({'Настроено' if Config.DATA_API_URL else 'Опционально'})</span></li>
            </ul>
            <p><em>Используйте реальный внешний IP адрес вашего компьютера</em></p>
        </div>
        
        <div class="card">
            <h2>🔗 Основные endpoints</h2>
            <ul>
                <li><code>POST /api/auth/login</code> - Авторизация через LDAP</li>
                <li><code>GET /api/region/&lt;code&gt;</code> - Данные региона</li>
                <li><code>GET /api/test</code> - Тест системы</li>
                <li><code>GET /api/health</code> - Проверка здоровья</li>
            </ul>
        </div>
        
        <div class="card">
            <h2>🔧 Проверка работы</h2>
            <p><a href="/api/test">/api/test</a> - Полный тест всех сервисов</p>
            <p><a href="/api/health">/api/health</a> - Проверка здоровья API</p>
        </div>
        
        <div class="card">
            <h2>⚠️ Важная информация</h2>
            <p>1. LDAP сервер использует самоподписанный SSL сертификат</p>
            <p>2. Для работы требуется открыть порты 8443 и 8444 на роутере</p>
            <p>3. Android может требовать доверия к самоподписанному сертификату</p>
        </div>
    </body>
    </html>
    """

# ================== ЗАПУСК СЕРВЕРА ==================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    
    print("=" * 70)
    print("🌐 DOSTUPNOST API СЕРВЕР НА RENDER.COM (HTTPS)")
    print("=" * 70)
    
    print("\n⚙️  КОНФИГУРАЦИЯ:")
    print(f"   • LDAP сервер:  {Config.LDAP_SERVER_URL or '❌ НЕ НАСТРОЕНО'}")
    print(f"   • Data API:     {Config.DATA_API_URL or '⚠️  ОПЦИОНАЛЬНО'}")
    print(f"   • SSL verify:   {'Да' if Config.VERIFY_SSL else 'Нет (самоподписанные)'}")
    
    print("\n📋 ОСНОВНЫЕ ENDPOINTS:")
    print("   • POST /api/auth/login            - Авторизация")
    print("   • GET  /api/region/{code}        - Данные региона")
    print("   • GET  /api/test                 - Тест системы")
    print("   • GET  /api/health               - Проверка здоровья")
    
    print("\n🔧 ДЛЯ НАСТРОЙКИ:")
    print("   1. Сгенерируйте SSL сертификаты: python generate_certs.py")
    print("   2. Запустите ldap_server.py на своем компьютере")
    print("   3. Откройте порты 8443 и 8444 на роутере")
    print("   4. В Render.com Dashboard добавьте переменные:")
    print("      - LDAP_SERVER_URL = https://[ВАШ_IP]:8443")
    print("      - DATA_API_URL = https://[ВАШ_IP]:8444")
    
    print("\n📱 ДЛЯ ANDROID:")
    print("   Убедитесь что BASE_URL в ApiClient.kt:")
    print('   private const val BASE_URL = "https://dostupnost.onrender.com/"')
    
    print("\n🔐 SSL ВАЖНО:")
    print("   • Самоподписанные сертификаты требуют verify=False")
    print("   • Для продакшена используйте Let's Encrypt")
    print("=" * 70)
    
    print(f"🚀 Запуск API сервера на порту {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
