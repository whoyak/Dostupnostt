"""
API СЕРВЕР ДЛЯ ДОСТУПНОСТИ РЕГИОНОВ С ИСТОРИЧЕСКИМИ ДАННЫМИ
Запускается на Render.com
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import requests
from datetime import datetime, timedelta
import os

app = Flask(__name__)
CORS(app)  # Разрешаем CORS для всех доменов
# ===== LDAP GATEWAY CONFIG =====
LDAP_GATEWAY_URL = "https://ваш-ldap-gateway.corp.tele2.ru"  # ВНУТРЕННИЙ адрес
LDAP_GATEWAY_KEY = "render-server-key"  # Должен совпадать с ключом в шлюзе
# ===============================

# Конфигурация
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/whoyak/region-data-cache/main/"
CACHE_TIMEOUT = 60  # Кэшируем на 60 секунд

# Кэш в памяти
cache = {
    'data': {},
    'timestamp': datetime.min
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
        'features': ['current_data', 'full_history', 'historical_view']
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

@app.route('/api/auth/health', methods=['GET'])
def auth_health():
    """Проверка доступности доменной авторизации"""
    try:
        response = requests.get(
            f"{LDAP_GATEWAY_URL}/api/ldap/health",
            headers={'X-API-Key': LDAP_GATEWAY_KEY},
            timeout=5
        )
        return jsonify(response.json())
    except Exception as e:
        return jsonify({
            'success': False,
            'ldap_available': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 503

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
    """Прокси для аутентификации через LDAP Gateway"""
    try:
        # 1. Получаем учетные данные из запроса
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Missing credentials'}), 400
        
        # 2. Отправляем запрос во внутренний LDAP Gateway
        ldap_response = requests.post(
            f"{LDAP_GATEWAY_URL}/api/ldap/authenticate",
            json={'username': username, 'password': password},
            headers={'X-API-Key': LDAP_GATEWAY_KEY},
            timeout=10
        )
        
        # 3. Возвращаем ответ от LDAP (или кэшируем сессию)
        if ldap_response.status_code == 200:
            ldap_data = ldap_response.json()
            
            # Здесь можно создать сессию/JWT токен для пользователя
            # Пока просто возвращаем ответ от LDAP
            
            return jsonify(ldap_data)
        else:
            # Проксируем ошибку от LDAP Gateway
            return jsonify({
                'success': False,
                'error': 'Authentication failed',
                'details': ldap_response.json() if ldap_response.content else 'LDAP gateway error'
            }), ldap_response.status_code
            
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'error': 'LDAP service timeout',
            'fallback': 'using_local_auth'  # Можно переключиться на локальную
        }), 504
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Auth service error: {str(e)}'
        }), 500

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
        'features': ['current_data', 'historical_data', 'full_history']
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)



