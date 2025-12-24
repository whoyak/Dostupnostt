"""
УПРОЩЕННЫЙ API СЕРВЕР ДЛЯ RENDER
Читает данные напрямую из GitHub Raw URL
"""
from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime
import json

app = Flask(__name__)
CORS(app)

# Ссылка на ваш файл данных в GitHub
GITHUB_DATA_URL = "https://raw.githubusercontent.com/ВАШ_ЛОГИН/region-data-cache/main/cached_data.json"

# Локальный кэш данных
data_cache = {
    'last_update': None,
    'data': None,
    'error': None
}

def fetch_data_from_github():
    """Загрузить данные из GitHub"""
    try:
        print(f"📥 Загружаю данные из GitHub...")
        response = requests.get(GITHUB_DATA_URL, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            data_cache['data'] = data
            data_cache['last_update'] = datetime.now().isoformat()
            data_cache['error'] = None
            
            regions_count = len([k for k in data.keys() if not k.startswith('_')])
            print(f"✅ Данные загружены: {regions_count} регионов")
            return True
        else:
            data_cache['error'] = f"GitHub вернул статус {response.status_code}"
            print(f"❌ Ошибка загрузки: {response.status_code}")
            return False
            
    except Exception as e:
        data_cache['error'] = str(e)
        print(f"❌ Ошибка сети: {e}")
        return False

# Загружаем данные при старте сервера
fetch_data_from_github()

@app.route('/api/test', methods=['GET'])
def test():
    return jsonify({
        'success': True,
        'message': 'API работает с GitHub как источником данных',
        'timestamp': datetime.now().strftime("%H:%M:%S"),
        'data_source': GITHUB_DATA_URL
    })

@app.route('/api/region/<region_code>', methods=['GET'])
def get_region_data(region_code):
    """Получить данные региона из кэша"""
    print(f"📥 Запрос данных для региона: {region_code}")
    
    # Проверяем актуальность данных (каждые 5 минут)
    if (not data_cache['last_update'] or 
        (datetime.now() - datetime.fromisoformat(data_cache['last_update'])).seconds > 300):
        print("🔄 Обновляю кэш данных...")
        fetch_data_from_github()
    
    if data_cache['data'] and region_code in data_cache['data']:
        data = data_cache['data'][region_code].copy()
        data['from_github_cache'] = True
        data['cache_updated'] = data_cache['last_update']
        return jsonify(data)
    
    # Если данных нет в кэше
    return jsonify({
        'success': False,
        'error': f'Регион {region_code} не найден',
        'region_code': region_code,
        'timestamp': datetime.now().strftime("%H:%M:%S"),
        'cache_status': {
            'last_update': data_cache['last_update'],
            'error': data_cache['error']
        }
    })

@app.route('/api/regions', methods=['GET'])
def get_regions_list():
    """Получить список всех регионов"""
    if data_cache['data']:
        regions = []
        for code, data in data_cache['data'].items():
            if not code.startswith('_'):
                regions.append({
                    'code': code,
                    'name': data.get('region_name', code),
                    'has_data': True
                })
        
        return jsonify({
            'success': True,
            'regions': regions,
            'count': len(regions),
            'from_github': True,
            'last_updated': data_cache['last_update'],
            'timestamp': datetime.now().strftime("%H:%M:%S")
        })
    
    return jsonify({
        'success': False,
        'error': 'Данные не загружены',
        'timestamp': datetime.now().strftime("%H:%M:%S")
    })

@app.route('/api/cache/status', methods=['GET'])
def cache_status():
    """Проверить статус кэша"""
    return jsonify({
        'success': True,
        'last_update': data_cache['last_update'],
        'data_source': GITHUB_DATA_URL,
        'has_data': data_cache['data'] is not None,
        'error': data_cache['error'],
        'regions_count': len([k for k in data_cache['data'].keys() if not k.startswith('_')]) if data_cache['data'] else 0,
        'timestamp': datetime.now().strftime("%H:%M:%S")
    })

@app.route('/api/cache/refresh', methods=['POST'])
def refresh_cache():
    """Принудительно обновить кэш"""
    success = fetch_data_from_github()
    return jsonify({
        'success': success,
        'message': 'Кэш обновлен' if success else 'Ошибка обновления',
        'last_update': data_cache['last_update'],
        'timestamp': datetime.now().strftime("%H:%M:%S")
    })

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 API СЕРВЕР ЗАПУЩЕН")
    print(f"📁 Источник данных: {GITHUB_DATA_URL}")
    print(f"🕐 Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if data_cache['data']:
        regions = [k for k in data_cache['data'].keys() if not k.startswith('_')]
        print(f"📊 Загружено регионов: {len(regions)}")
        print(f"⏰ Последнее обновление: {data_cache['last_update']}")
    else:
        print("⚠️ Данные не загружены!")
        print(f"❌ Ошибка: {data_cache['error']}")
    
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=5000, debug=False)
