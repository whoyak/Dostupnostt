# api_server.py
import os
import requests
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS
from storage import get_storage

app = Flask(__name__)
CORS(app)

# Конфигурация
CONFIG = {
    'ldap_server_url': os.environ.get('LDAP_SERVER_URL', 'http://localhost:8080'),
    'api_port': int(os.environ.get('API_PORT', 5000)),
    'enable_backup': os.environ.get('ENABLE_BACKUP', 'True').lower() == 'true',
    'max_history_days': 30
}

storage = get_storage()


@app.route('/api/test', methods=['GET'])
def test_connection():
    """Тестовый endpoint"""
    return jsonify({
        'success': True,
        'message': 'API Dostupnost работает нормально',
        'timestamp': datetime.now().isoformat(),
        'storage_type': 'filesystem',
        'regions_count': len(storage.get_all_regions()),
        'version': '1.0.0'
    })


@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    """Аутентификация пользователя"""
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        if not username or not password:
            return jsonify({'success': False, 'error': 'Missing credentials'}), 400

        # Тестовая учетка
        if username == 'admin' and password == 'admin':
            return jsonify({
                'success': True,
                'username': 'admin',
                'display_name': 'Администратор',
                'auth_source': 'local',
                'timestamp': datetime.now().isoformat()
            })

        # Проверяем через LDAP сервер
        try:
            ldap_response = requests.post(
                f"{CONFIG['ldap_server_url']}/api/ldap/auth",
                json={'username': username, 'password': password},
                timeout=10
            )

            if ldap_response.status_code == 200:
                result = ldap_response.json()
                if result.get('success'):
                    return jsonify(result)
                else:
                    return jsonify(result), 401

        except requests.exceptions.RequestException as e:
            print(f"⚠️ LDAP сервер недоступен: {e}")

            # Фолбэк на локальную проверку
            from ldap_server import ADAuthenticator
            authenticator = ADAuthenticator()
            result = authenticator.authenticate(username, password)

            if result['success']:
                return jsonify(result)
            else:
                return jsonify({
                    'success': False,
                    'error': 'Сервер авторизации недоступен',
                    'details': str(e)
                }), 503

        return jsonify({
            'success': False,
            'error': 'Неверный логин или пароль'
        }), 401

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Ошибка аутентификации: {str(e)}'
        }), 500


@app.route('/api/region/<region_code>', methods=['GET'])
def get_region_data(region_code):
    """Получение текущих данных региона"""
    try:
        region_code = region_code.upper()
        data = storage.get_region_data(region_code)

        if data:
            # Добавляем текущее время
            data['api_timestamp'] = datetime.now().isoformat()
            data['success'] = True
            return jsonify(data)

        # Если данных нет
        return jsonify({
            'success': False,
            'error': f'Регион {region_code} не найден',
            'region_code': region_code,
            'timestamp': datetime.now().isoformat()
        }), 404

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'region_code': region_code
        }), 500


@app.route('/api/region/<region_code>/history', methods=['GET'])
def get_region_history(region_code):
    """Получение истории региона"""
    try:
        region_code = region_code.upper()
        hours = int(request.args.get('hours', 24))

        history = storage.get_history(region_code, hours)

        # Форматируем ответ
        formatted_history = []
        for item in history:
            formatted_item = {
                'region_code': item.get('region_code', region_code),
                'region_name': item.get('region_name', f'Регион {region_code}'),
                'timestamp': item.get('_history', {}).get('timestamp', ''),
                'stats': item.get('stats', {}),
                'base_layer_preview': item.get('base_layer', '')[:500] + '...' if len(
                    item.get('base_layer', '')) > 500 else item.get('base_layer', '')
            }
            formatted_history.append(formatted_item)

        return jsonify({
            'success': True,
            'region_code': region_code,
            'history': formatted_history,
            'count': len(formatted_history),
            'hours': hours,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'region_code': region_code
        }), 500


@app.route('/api/region/<region_code>/history/<timestamp>', methods=['GET'])
def get_historical_data(region_code, timestamp):
    """Получение данных на конкретный момент времени"""
    try:
        region_code = region_code.upper()

        # Пытаемся распарсить timestamp
        try:
            # Форматируем timestamp (может быть в разных форматах)
            if 'T' in timestamp:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            else:
                # Пробуем разные форматы
                formats = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y%m%d_%H%M%S']
                dt = None
                for fmt in formats:
                    try:
                        dt = datetime.strptime(timestamp, fmt)
                        break
                    except:
                        continue

                if not dt:
                    return jsonify({
                        'success': False,
                        'error': 'Неверный формат времени'
                    }), 400

            iso_timestamp = dt.isoformat()

        except:
            return jsonify({
                'success': False,
                'error': 'Неверный формат времени'
            }), 400

        # Получаем исторические данные
        data = storage.get_historical_data(region_code, iso_timestamp)

        if data:
            data['success'] = True
            data['is_historical'] = True
            data['historical_timestamp'] = iso_timestamp
            data['api_timestamp'] = datetime.now().isoformat()
            return jsonify(data)

        return jsonify({
            'success': False,
            'error': f'Исторические данные для {region_code} на время {iso_timestamp} не найдены',
            'region_code': region_code,
            'timestamp': iso_timestamp
        }), 404

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'region_code': region_code,
            'timestamp': timestamp
        }), 500


@app.route('/api/region/<region_code>/refresh', methods=['POST'])
def refresh_region_data(region_code):
    """Принудительное обновление данных региона"""
    try:
        # Здесь можно добавить логику обновления из парсера
        # Пока просто возвращаем текущие данные с пометкой об обновлении

        data = storage.get_region_data(region_code)

        if data:
            data['forced_refresh'] = True
            data['refresh_timestamp'] = datetime.now().isoformat()
            data['success'] = True

            # Сохраняем обновленные данные
            storage.save_region_data(region_code, data)

            return jsonify(data)

        return jsonify({
            'success': False,
            'error': f'Регион {region_code} не найден'
        }), 404

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'region_code': region_code
        }), 500


@app.route('/api/regions', methods=['GET'])
def get_all_regions():
    """Получение списка всех регионов с краткой статистикой"""
    try:
        regions = storage.get_all_regions()

        regions_list = []
        for region_code in regions:
            data = storage.get_region_data(region_code)
            if data:
                regions_list.append({
                    'code': region_code,
                    'name': data.get('region_name', region_code),
                    'last_updated': data.get('_meta', {}).get('updated_at', ''),
                    'stats': data.get('stats', {}),
                    'has_history': len(storage.get_history(region_code, hours=1)) > 0
                })

        return jsonify({
            'success': True,
            'regions': regions_list,
            'count': len(regions_list),
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/storage/stats', methods=['GET'])
def get_storage_stats():
    """Получение статистики хранилища"""
    try:
        stats_file = os.path.join(storage.data_dir, 'meta', 'stats.json')

        if os.path.exists(stats_file):
            with open(stats_file, 'r') as f:
                stats = json.load(f)
        else:
            stats = {
                'total_regions': 0,
                'last_updated': datetime.now().isoformat(),
                'storage_size_mb': 0,
                'history_entries': 0
            }

        stats['success'] = True
        stats['storage_path'] = storage.data_dir
        stats['timestamp'] = datetime.now().isoformat()

        return jsonify(stats)

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/auth/health', methods=['GET'])
def auth_health():
    """Проверка доступности авторизации"""
    try:
        # Проверяем LDAP сервер
        ldap_response = requests.get(
            f"{CONFIG['ldap_server_url']}/api/ldap/health",
            timeout=5
        )

        ldap_status = 'available' if ldap_response.status_code == 200 else 'unavailable'

        return jsonify({
            'success': True,
            'ldap_server': ldap_status,
            'storage': 'available',
            'timestamp': datetime.now().isoformat()
        })

    except:
        return jsonify({
            'success': False,
            'error': 'LDAP сервер недоступен'
        }), 503


@app.route('/api/health', methods=['GET'])
def health_check():
    """Полная проверка здоровья системы"""
    try:
        # Проверяем хранилище
        regions_count = len(storage.get_all_regions())

        # Проверяем LDAP
        ldap_ok = False
        try:
            ldap_response = requests.get(f"{CONFIG['ldap_server_url']}/api/ldap/health", timeout=3)
            ldap_ok = ldap_response.status_code == 200
        except:
            pass

        return jsonify({
            'status': 'healthy',
            'storage': {
                'regions_count': regions_count,
                'path': storage.data_dir,
                'status': 'ok'
            },
            'ldap': {
                'status': 'ok' if ldap_ok else 'unavailable',
                'url': CONFIG['ldap_server_url']
            },
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0'
        })

    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


if __name__ == '__main__':
    print(f"🚀 API сервер запущен на порту {CONFIG['api_port']}")
    print(f"📁 Хранилище: {storage.data_dir}")
    print(f"🔐 LDAP сервер: {CONFIG['ldap_server_url']}")
    print(f"🌐 Доступные endpoint'ы:")
    print(f"  • /api/test - тест подключения")
    print(f"  • /api/region/<code> - данные региона")
    print(f"  • /api/region/<code>/history - история")
    print(f"  • /api/regions - все регионы")
    print(f"  • /api/health - проверка системы")

    app.run(host='0.0.0.0', port=CONFIG['api_port'], debug=False)
