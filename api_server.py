"""
API СЕРВЕР ДЛЯ ДОСТУПНОСТИ РЕГИОНОВ С ИСТОРИЧЕСКИМИ ДАННЫМИ
Запускается на Render.com
"""
import time
from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import requests
from datetime import datetime, timedelta
import os
import base64
import uuid

app = Flask(__name__)
CORS(app)  # Разрешаем CORS для всех доменов

# === LDAP GATEWAY КОНФИГУРАЦИЯ ===
# Эти настройки нужны для доменной авторизации
LDAP_GATEWAY_ENABLED = True

# 🔗 GitHub репозиторий с данными
GITHUB_REPO = os.environ.get('GITHUB_REPO', 'whoyak/region-data-cache')
GITHUB_BRANCH = os.environ.get('GITHUB_BRANCH', 'main')
    
# 🔑 GitHub токен (берется из переменных окружения Render.com)
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')

# === LDAP НАСТРОЙКИ ===
# URL вашего локального LDAP сервера (будет настроен позже)
# Формат: https://ВАШ_ВНЕШНИЙ_IP:8443/api/ldap/auth
LDAP_SERVER_URL = os.environ.get('LDAP_SERVER_URL', '')
LDAP_REQUEST_TIMEOUT = int(os.environ.get('LDAP_REQUEST_TIMEOUT', 10))

# Режимы работы авторизации
AUTH_MODE = os.environ.get('AUTH_MODE', 'mixed')  # 'mixed', 'ldap_only', 'fallback_only'

# Фолбэк пользователи (если LDAP недоступен)
FALLBACK_USERS = {
    "operator": "operator123",
    "viewer": "viewonly",
    "test": "test123",
    "admin": "admin",
    "danil.vasilchenko": "ваш_пароль",  # Замените на реальный пароль
    "danil": "ваш_пароль"
}

# Конфигурация
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/whoyak/region-data-cache/main/"
CACHE_TIMEOUT = 60  # Кэшируем на 60 секунд

# Кэш в памяти
cache = {
    'data': {},
    'timestamp': datetime.min
}

def make_ldap_request(username, password):
    """Отправляет запрос на локальный LDAP сервер"""
    try:
        if not LDAP_SERVER_URL:
            return {
                'success': False,
                'error': 'LDAP сервер не настроен',
                'error_code': 'LDAP_NOT_CONFIGURED'
            }
        
        # Подготавливаем данные для LDAP
        ldap_data = {
            'username': username,
            'password': password,
            'timestamp': datetime.now().isoformat(),
            'source_ip': request.remote_addr
        }
        
        # Отправляем запрос к локальному LDAP серверу
        response = requests.post(
            LDAP_SERVER_URL,
            json=ldap_data,
            timeout=LDAP_REQUEST_TIMEOUT,
            verify=False  # Для самоподписанных сертификатов
        )
        
        if response.status_code == 200:
            return {
                'success': True,
                'data': response.json(),
                'auth_source': 'ldap_direct',
                'response_time': response.elapsed.total_seconds()
            }
        else:
            return {
                'success': False,
                'error': f'LDAP сервер вернул {response.status_code}',
                'error_code': f'LDAP_{response.status_code}',
                'response_text': response.text[:200]
            }
            
    except requests.exceptions.Timeout:
        return {
            'success': False,
            'error': f'Таймаут подключения к LDAP серверу ({LDAP_REQUEST_TIMEOUT}с)',
            'error_code': 'LDAP_TIMEOUT',
            'details': 'LDAP сервер не ответил. Проверьте доступность и порты.'
        }
    except requests.exceptions.ConnectionError:
        return {
            'success': False,
            'error': 'Не удалось подключиться к LDAP серверу',
            'error_code': 'LDAP_CONNECTION_ERROR',
            'details': 'Проверьте URL и доступность LDAP сервера.'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Ошибка LDAP запроса: {str(e)}',
            'error_code': 'LDAP_REQUEST_ERROR'
        }

def check_fallback_auth(username, password):
    """Проверка учетных данных в фолбэк режиме"""
    if username in FALLBACK_USERS:
        if FALLBACK_USERS[username] == password:
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

def fetch_from_github(filename):
    """Загружает данные из GitHub"""
    try:
        url = f"{GITHUB_RAW_BASE}{filename}"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"⚠️ Файл {filename} не найден: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Ошибка загрузки {filename}: {e}")
        return None

def get_cached_data():
    """Получает данные с кэшированием"""
    global cache

    now = datetime.now()
    if (now - cache['timestamp']).seconds < CACHE_TIMEOUT and 'data' in cache:
        return cache['data']

    # Загружаем данные
    data = fetch_from_github("cached_data.json")
    if data:
        cache['data'] = data
        cache['timestamp'] = now

    return data

@app.route('/api/test', methods=['GET'])
def test_connection():
    """Тестовый endpoint"""
    return jsonify({
        'success': True,
        'message': 'API Dostupnost работает нормально',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0',
        'features': ['current_data', 'full_history', 'historical_view', 'ldap_auth'],
        'auth_modes': ['ldap', 'fallback', 'mixed'],
        'current_auth_mode': AUTH_MODE,
        'ldap_configured': bool(LDAP_SERVER_URL)
    })

@app.route('/api/region/<region_code>', methods=['GET'])
def get_region_data(region_code):
    """Получение текущих данных региона"""
    try:
        # Пробуем загрузить конкретный файл региона
        filename = f"region_{region_code}.json"
        data = fetch_from_github(filename)

        if data:
            return jsonify(data)

        # Если нет отдельного файла, ищем в общем кэше
        cached_data = get_cached_data()
        if cached_data and region_code in cached_data:
            return jsonify(cached_data[region_code]['current'])

        # Если данных нет, возвращаем mock
        return jsonify({
            'success': True,
            'region_code': region_code,
            'region_name': f"Регион {region_code}",
            'base_layer': f"{region_code} Базовый слой (тестовые данные)\n\nВсего BS: 100\nБазовый слой: 95/100",
            'non_priority': f"{region_code} Технологии (тестовые данные)\n\nНедоступно LTE1800:\n1) BS1001",
            'timestamp': datetime.now().strftime("%H:%M:%S"),
            'is_mock': True,
            'forced_refresh': False,
            'stats': {
                'total_bs': 100,
                'base_layer_count': 95,
                'power_problems': 3,
                'non_priority_percentage': 5
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'region_code': region_code
        }), 500

@app.route('/api/region/<region_code>/history', methods=['GET'])
def get_region_history(region_code):
    """Получение истории региона (список записей)"""
    try:
        # Получаем параметр hours
        hours = int(request.args.get('hours', 24))

        # Пробуем загрузить файл истории
        filename = f"history_{region_code}.json"
        data = fetch_from_github(filename)

        if data:
            # Фильтруем по времени если нужно
            if hours < 24:
                cutoff_time = datetime.now() - timedelta(hours=hours)
                filtered_history = []
                for item in data.get('history', []):
                    try:
                        item_time = datetime.fromisoformat(item.get('full_timestamp', '2000-01-01').replace('Z', '+00:00'))
                        if item_time > cutoff_time:
                            filtered_history.append(item)
                    except:
                        filtered_history.append(item)

                data['history'] = filtered_history
                data['count'] = len(filtered_history)

            return jsonify(data)

        # Если файла истории нет, ищем в кэше
        cached_data = get_cached_data()
        if cached_data and region_code in cached_data:
            history = cached_data[region_code].get('history', [])

            # Фильтруем по времени если нужно
            if hours < 24:
                cutoff_time = datetime.now() - timedelta(hours=hours)
                filtered_history = []
                for item in history:
                    try:
                        item_time = datetime.fromisoformat(item.get('full_timestamp', '2000-01-01').replace('Z', '+00:00'))
                        if item_time > cutoff_time:
                            filtered_history.append(item)
                    except:
                        filtered_history.append(item)

                history = filtered_history

            return jsonify({
                'success': True,
                'region_code': region_code,
                'history': history,
                'count': len(history),
                'timestamp': datetime.now().isoformat(),
                'message': 'Полная история с данными'
            })

        # Если истории нет, возвращаем пустую
        return jsonify({
            'success': True,
            'region_code': region_code,
            'history': [],
            'count': 0,
            'timestamp': datetime.now().isoformat(),
            'message': 'История пока пуста'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'region_code': region_code
        }), 500

@app.route('/api/region/<region_code>/history/<timestamp>', methods=['GET'])
def get_historical_data(region_code, timestamp):
    """Получение данных региона на конкретный момент времени"""
    try:
        # Преобразуем timestamp из URL в нормальный формат
        timestamp = timestamp.replace('-', ':').replace('T', ' ')

        # Сначала пробуем загрузить конкретный файл исторических данных
        filename = f"history_{region_code}_{timestamp}.json"
        data = fetch_from_github(filename)

        if data and data.get('historical_data'):
            return jsonify({
                'success': True,
                'is_historical': True,
                'historical_timestamp': timestamp,
                'data': data['historical_data']
            })

        # Если нет отдельного файла, ищем в общей истории
        history_response = fetch_from_github(f"history_{region_code}.json")
        if history_response and history_response.get('history'):
            # Ищем запись с ближайшим timestamp
            target_time = None
            try:
                target_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                pass

            closest_item = None
            closest_item_time = None
            if target_time:
                for item in history_response['history']:
                    item_time = datetime.fromisoformat(item.get('full_timestamp', '2000-01-01').replace('Z', '+00:00'))
                    if not closest_item or abs((item_time - target_time).total_seconds()) < abs((closest_item_time - target_time).total_seconds()):
                        closest_item = item
                        closest_item_time = item_time

            if closest_item:
                return jsonify({
                    'success': True,
                    'is_historical': True,
                    'historical_timestamp': timestamp,
                    'data': closest_item
                })

        # Ищем в кэше
        cached_data = get_cached_data()
        if cached_data and region_code in cached_data:
            history = cached_data[region_code].get('history', [])

            # Ищем по timestamp
            for item in history:
                if item.get('full_timestamp', '').startswith(timestamp) or item.get('timestamp', '') == timestamp:
                    return jsonify({
                        'success': True,
                        'is_historical': True,
                        'historical_timestamp': timestamp,
                        'data': item
                    })

        return jsonify({
            'success': False,
            'error': f'Исторические данные для {region_code} на время {timestamp} не найдены',
            'region_code': region_code,
            'timestamp': timestamp
        }), 404

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'region_code': region_code,
            'timestamp': timestamp
        }), 500

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    """Аутентификация через LDAP или фолбэк"""
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        if not username or not password:
            return jsonify({
                'success': False,
                'error': 'Требуется имя пользователя и пароль',
                'error_code': 'MISSING_CREDENTIALS'
            }), 400

        print(f"🔐 Auth request for: {username} (mode: {AUTH_MODE})")

        # 📌 Режим работы в зависимости от AUTH_MODE
        if AUTH_MODE == 'ldap_only' or AUTH_MODE == 'mixed':
            # Пробуем LDAP аутентификацию
            ldap_result = make_ldap_request(username, password)
            
            if ldap_result['success']:
                print(f"✅ LDAP auth successful: {username}")
                response_data = ldap_result['data']
                response_data.update({
                    'api_server': 'dostupnost_api_render',
                    'auth_flow': 'ldap_direct',
                    'timestamp': datetime.now().isoformat()
                })
                return jsonify(response_data)
            
            # Если LDAP не сработал, но режим mixed - пробуем фолбэк
            if AUTH_MODE == 'mixed':
                print(f"⚠️ LDAP failed, trying fallback: {ldap_result.get('error')}")
                fallback_result = check_fallback_auth(username, password)
                
                if fallback_result['success']:
                    fallback_result.update({
                        'api_server': 'dostupnost_api_render',
                        'auth_flow': 'fallback_after_ldap',
                        'warning': 'Используется фолбэк аутентификация. LDAP сервер недоступен.',
                        'ldap_error': ldap_result.get('error'),
                        'timestamp': datetime.now().isoformat()
                    })
                    print(f"✅ Fallback auth successful: {username}")
                    return jsonify(fallback_result)
                
                # Если фолбэк тоже не сработал
                return jsonify({
                    'success': False,
                    'error': 'Неверные учетные данные',
                    'error_code': 'INVALID_CREDENTIALS',
                    'timestamp': datetime.now().isoformat()
                }), 401
            else:
                # Режим ldap_only - возвращаем ошибку LDAP
                return jsonify({
                    'success': False,
                    'error': ldap_result.get('error', 'Ошибка LDAP аутентификации'),
                    'error_code': ldap_result.get('error_code', 'LDAP_ERROR'),
                    'details': ldap_result.get('details', ''),
                    'timestamp': datetime.now().isoformat()
                }), 401
        
        # 📌 Режим fallback_only
        elif AUTH_MODE == 'fallback_only':
            fallback_result = check_fallback_auth(username, password)
            
            if fallback_result['success']:
                fallback_result.update({
                    'api_server': 'dostupnost_api_render',
                    'auth_flow': 'fallback_only',
                    'timestamp': datetime.now().isoformat()
                })
                print(f"✅ Fallback-only auth successful: {username}")
                return jsonify(fallback_result)
            
            return jsonify({
                'success': False,
                'error': 'Неверные учетные данные',
                'error_code': 'INVALID_CREDENTIALS',
                'timestamp': datetime.now().isoformat()
            }), 401

    except Exception as e:
        print(f"❌ Auth endpoint error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Authentication error: {str(e)}',
            'error_code': 'SERVER_ERROR',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/auth/ldap/test', methods=['GET'])
def test_ldap_connection():
    """Тест подключения к LDAP серверу"""
    test_results = {
        'test': 'ldap_connection_test',
        'timestamp': datetime.now().isoformat(),
        'config': {
            'ldap_server_url': LDAP_SERVER_URL,
            'auth_mode': AUTH_MODE,
            'request_timeout': LDAP_REQUEST_TIMEOUT,
            'fallback_users_count': len(FALLBACK_USERS)
        },
        'tests': {}
    }
    
    # Тест 1: Проверка конфигурации
    test_results['tests']['config_check'] = {
        'passed': bool(LDAP_SERVER_URL),
        'message': 'LDAP сервер настроен' if LDAP_SERVER_URL else 'LDAP сервер не настроен',
        'url': LDAP_SERVER_URL or 'не указан'
    }
    
    # Тест 2: Пинг LDAP сервера (если настроен)
    if LDAP_SERVER_URL:
        try:
            # Пробуем получить health status от LDAP сервера
            health_url = LDAP_SERVER_URL.replace('/api/ldap/auth', '/health')
            
            response = requests.get(health_url, timeout=5, verify=False)
            
            test_results['tests']['ldap_health'] = {
                'passed': response.status_code == 200,
                'message': 'LDAP сервер доступен' if response.status_code == 200 else f'LDAP сервер недоступен: {response.status_code}',
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds() if hasattr(response, 'elapsed') else None
            }
        except Exception as e:
            test_results['tests']['ldap_health'] = {
                'passed': False,
                'message': f'Ошибка подключения: {str(e)}'
            }
    
    # Тест 3: Проверка фолбэк пользователей
    test_results['tests']['fallback_users'] = {
        'passed': len(FALLBACK_USERS) > 0,
        'message': f'{len(FALLBACK_USERS)} фолбэк пользователей настроено',
        'users': list(FALLBACK_USERS.keys())
    }
    
    # Общая оценка
    passed_tests = [t for t in test_results['tests'].values() if t.get('passed', False)]
    if AUTH_MODE == 'fallback_only' and test_results['tests']['fallback_users']['passed']:
        test_results['overall'] = 'PASSED'
    elif AUTH_MODE == 'ldap_only' and test_results['tests']['ldap_health']['passed']:
        test_results['overall'] = 'PASSED'
    elif AUTH_MODE == 'mixed' and (test_results['tests']['ldap_health']['passed'] or test_results['tests']['fallback_users']['passed']):
        test_results['overall'] = 'PASSED'
    else:
        test_results['overall'] = 'FAILED'
    
    return jsonify(test_results)

@app.route('/api/auth/health', methods=['GET'])
def auth_health():
    """Проверка доступности авторизации"""
    ldap_status = 'unknown'
    
    if LDAP_SERVER_URL:
        try:
            response = requests.get(
                LDAP_SERVER_URL.replace('/api/ldap/auth', '/health'),
                timeout=3,
                verify=False
            )
            if response.status_code == 200:
                ldap_status = 'available'
            else:
                ldap_status = 'unavailable'
        except:
            ldap_status = 'unavailable'

    return jsonify({
        'success': True,
        'auth': {
            'mode': AUTH_MODE,
            'ldap_configured': bool(LDAP_SERVER_URL),
            'ldap_status': ldap_status,
            'fallback_users': len(FALLBACK_USERS),
            'fallback_available': AUTH_MODE in ['mixed', 'fallback_only']
        },
        'timestamp': datetime.now().isoformat(),
        'instructions': {
            'setup_ldap': 'Установите LDAP_SERVER_URL = https://ваш_внешний_ip:8443/api/ldap/auth',
            'test_users': 'Используйте admin/admin для теста'
        }
    })

@app.route('/api/region/<region_code>/refresh', methods=['POST'])
def refresh_region_data(region_code):
    """Принудительное обновление данных региона"""
    try:
        data = fetch_from_github(f"region_{region_code}.json")
        if data:
            data['forced_refresh'] = True
            data['refresh_timestamp'] = datetime.now().isoformat()
            return jsonify(data)

        return jsonify({
            'success': True,
            'region_code': region_code,
            'region_name': f"Регион {region_code} (обновлено)",
            'base_layer': f"{region_code} Базовый слой (обновлено)\n\nВсего BS: 100\nБазовый слой: 95/100",
            'non_priority': f"{region_code} Технологии (обновлено)\n\nНедоступно LTE1800:\n1) BS1001",
            'timestamp': datetime.now().strftime("%H:%M:%S"),
            'forced_refresh': True,
            'refresh_timestamp': datetime.now().isoformat(),
            'stats': {
                'total_bs': 100,
                'base_layer_count': 95,
                'power_problems': 3,
                'non_priority_percentage': 5
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'region_code': region_code
        }), 500

@app.route('/api/regions', methods=['GET'])
def get_all_regions():
    """Получение списка всех регионов"""
    try:
        cached_data = get_cached_data()
        if cached_data and '_meta' in cached_data:
            regions_list = []
            for region_code, data in cached_data.items():
                if region_code != '_meta':
                    current = data.get('current', {})
                    stats = current.get('stats', {})
                    regions_list.append({
                        'code': region_code,
                        'name': current.get('region_name', region_code),
                        'total_bs': stats.get('total_bs', 0),
                        'base_layer_percentage': stats.get('base_layer_percentage', 0),
                        'power_problems': stats.get('power_problems', 0),
                        'last_updated': current.get('timestamp', '00:00:00'),
                        'has_history': len(data.get('history', [])) > 0
                    })

            return jsonify({
                'success': True,
                'regions': regions_list,
                'count': len(regions_list),
                'timestamp': datetime.now().isoformat()
            })

        return jsonify({
            'success': True,
            'regions': [],
            'count': 0,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check для мониторинга"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'dostupnost-api',
        'features': ['current_data', 'historical_data', 'full_history', 'ldap_auth'],
        'auth': {
            'mode': AUTH_MODE,
            'ldap_configured': bool(LDAP_SERVER_URL),
            'fallback_available': True
        }
    })

@app.route('/')
def home():
    """Домашняя страница API"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>🌐 Dostupnost API Server</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
            .card { background: #f5f5f5; padding: 20px; margin: 20px 0; border-radius: 8px; }
            .success { color: #4CAF50; font-weight: bold; }
            .warning { color: #FF9800; font-weight: bold; }
            .error { color: #f44336; font-weight: bold; }
            code { background: #eee; padding: 2px 6px; border-radius: 3px; }
        </style>
    </head>
    <body>
        <h1>🌐 Dostupnost API Server</h1>
        <p>API для Android приложения мониторинга доступности базовых станций</p>
        
        <div class="card">
            <h2>📊 Статус системы</h2>
            <p>Режим авторизации: <span class="success">{}</span></p>
            <p>LDAP сервер: <span class="{}">{}</span></p>
            <p>Фолбэк пользователей: <span class="success">{}</span></p>
            <p>GitHub репозиторий: <code>{}</code></p>
        </div>
        
        <div class="card">
            <h2>🔗 Основные Endpoints</h2>
            <ul>
                <li><code>POST /api/auth/login</code> - Авторизация (LDAP/фолбэк)</li>
                <li><code>GET /api/region/{code}</code> - Данные региона</li>
                <li><code>GET /api/region/{code}/history</code> - История региона</li>
                <li><code>GET /api/regions</code> - Список регионов</li>
                <li><code>GET /api/auth/ldap/test</code> - Тест LDAP</li>
                <li><code>GET /api/health</code> - Проверка здоровья</li>
            </ul>
        </div>
        
        <div class="card">
            <h2>⚙️ Настройка LDAP</h2>
            <p>1. Запустите LDAP сервер на вашем компьютере</p>
            <p>2. Откройте порт 8443 на роутере:</p>
            <pre>Внешний порт 8443 → Внутренний IP:8443</pre>
            <p>3. Узнайте внешний IP: <code>curl ifconfig.me</code></p>
            <p>4. В Render.com добавьте переменную:</p>
            <pre>LDAP_SERVER_URL = https://[ВАШ_IP]:8443/api/ldap/auth</pre>
        </div>
    </body>
    </html>
    """.format(
        AUTH_MODE,
        'success' if LDAP_SERVER_URL else 'warning',
        LDAP_SERVER_URL or 'Не настроен',
        len(FALLBACK_USERS),
        GITHUB_REPO
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 60)
    print("🚀 ЗАПУСК DOSTUPNOST API СЕРВЕРА")
    print("=" * 60)
    print(f"\n⚙️  КОНФИГУРАЦИЯ:")
    print(f"   • Режим авторизации: {AUTH_MODE}")
    print(f"   • LDAP сервер: {LDAP_SERVER_URL or 'Не настроен'}")
    print(f"   • GitHub репозиторий: {GITHUB_REPO}")
    print(f"   • Фолбэк пользователей: {len(FALLBACK_USERS)}")
    
    print(f"\n📋 ДОСТУПНЫЕ ENDPOINTS:")
    print(f"   • POST /api/auth/login")
    print(f"   • GET  /api/region/{{code}}")
    print(f"   • GET  /api/region/{{code}}/history")
    print(f"   • GET  /api/regions")
    print(f"   • GET  /api/auth/health")
    
    print(f"\n🔧 НАСТРОЙКА LDAP:")
    print(f"   1. Установите LDAP_SERVER_URL в Render.com")
    print(f"   2. Формат: https://ваш_ip:8443/api/ldap/auth")
    print(f"   3. Для теста используйте: admin/admin")
    
    app.run(host='0.0.0.0', port=port, debug=False)
