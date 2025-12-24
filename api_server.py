"""
УПРОЩЕННЫЙ API СЕРВЕР ДЛЯ RENDER
Читает данные напрямую из GitHub Raw URL
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from datetime import datetime
import json
import time

app = Flask(__name__)
CORS(app)

# Ссылка на ваш файл данных в GitHub
GITHUB_DATA_URL = "https://raw.githubusercontent.com/whoyak/region-data-cache/main/cached_data.json"

# Локальный кэш данных
data_cache = {
    'last_update': None,
    'data': None,
    'error': None,
    'cache_hits': 0,
    'github_hits': 0
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
            data_cache['github_hits'] += 1
            
            # Подсчитываем регионы (исключая мета-данные)
            regions = [k for k in data.keys() if not k.startswith('_')]
            regions_count = len(regions)
            
            print(f"✅ Данные загружены: {regions_count} регионов")
            
            # Логируем первый регион для проверки
            if regions:
                first_region = regions[0]
                if first_region in data:
                    print(f"   Пример: {first_region} - {data[first_region].get('region_name', 'N/A')}")
            
            return True
        elif response.status_code == 404:
            data_cache['error'] = f"Файл не найден на GitHub (404): {GITHUB_DATA_URL}"
            print(f"❌ Файл данных не найден на GitHub!")
            print(f"   Проверьте URL: {GITHUB_DATA_URL}")
            print(f"   Убедитесь, что файл cached_data.json существует в репозитории")
            return False
        else:
            data_cache['error'] = f"GitHub вернул статус {response.status_code}"
            print(f"❌ Ошибка загрузки: {response.status_code}")
            return False
            
    except Exception as e:
        data_cache['error'] = str(e)
        print(f"❌ Ошибка сети: {e}")
        return False

# Загружаем данные при старте сервера
print("🚀 API сервер запущен в режиме чтения кэша")
print(f"📁 Источник данных: {GITHUB_DATA_URL}")
fetch_data_from_github()

@app.route('/api/test', methods=['GET'])
def test():
    return jsonify({
        'success': True,
        'message': 'API работает с GitHub как источником данных',
        'timestamp': datetime.now().strftime("%H:%M:%S"),
        'data_source': GITHUB_DATA_URL,
        'cache_status': {
            'last_update': data_cache['last_update'],
            'has_data': data_cache['data'] is not None,
            'error': data_cache['error']
        }
    })

@app.route('/api/region/<region_code>', methods=['GET'])
def get_region_data(region_code):
    """Получить данные региона из кэша"""
    print(f"📥 Запрос данных для региона: {region_code}")
    
    # Всегда проверяем кэш, не обновляем автоматически
    if data_cache['data'] is None:
        print("⚠️ Кэш пуст, пытаюсь загрузить...")
        fetch_data_from_github()
    
    if data_cache['data'] and region_code in data_cache['data']:
        data = data_cache['data'][region_code].copy()
        data['from_github_cache'] = True
        data['cache_updated'] = data_cache['last_update']
        data['cache_hit'] = data_cache['cache_hits']
        data_cache['cache_hits'] += 1
        
        # Добавляем статистику, если её нет
        if 'stats' not in data:
            data['stats'] = {
                'total_bs': 0,
                'base_layer_count': 0,
                'power_problems': 0,
                'non_priority_percentage': 0
            }
        
        return jsonify(data)
    
    # Если данных нет в кэше, возвращаем тестовые данные
    print(f"⚠️ Регион {region_code} не найден в кэше, возвращаю тестовые данные")
    
    return jsonify({
        'success': True,
        'region_code': region_code,
        'region_name': region_code,
        'base_layer': f'{region_code} Базовый слой (тестовые данные)\n\nДанные временно недоступны\nФайл cached_data.json не найден на GitHub',
        'non_priority': f'{region_code} Технологии (тестовые данные)\n\nОжидание обновления данных',
        'timestamp': datetime.now().strftime("%H:%M:%S"),
        'is_mock': True,
        'is_fallback': True,
        'stats': {
            'total_bs': 50,
            'base_layer_count': 45,
            'power_problems': 2,
            'non_priority_percentage': 10
        },
        'cache_status': {
            'last_update': data_cache['last_update'],
            'error': data_cache['error'],
            'suggestion': 'Запустите auto_collector.py на локальном ПК для обновления данных'
        }
    })

@app.route('/api/region/<region_code>/refresh', methods=['POST'])
def refresh_region_data(region_code):
    """Принудительно обновить данные региона (загрузить из GitHub)"""
    print(f"🔄 Принудительное обновление кэша для региона: {region_code}")
    
    success = fetch_data_from_github()
    
    if success:
        if data_cache['data'] and region_code in data_cache['data']:
            data = data_cache['data'][region_code].copy()
            data['forced_refresh'] = True
            data['refresh_timestamp'] = datetime.now().strftime("%H:%M:%S")
            data['from_github_cache'] = True
            return jsonify(data)
    
    # Если обновление не удалось или региона нет
    return jsonify({
        'success': success,
        'region_code': region_code,
        'message': 'Кэш обновлен' if success else 'Ошибка обновления кэша',
        'timestamp': datetime.now().strftime("%H:%M:%S"),
        'error': data_cache['error'] if not success else None
    })

@app.route('/api/regions', methods=['GET'])
def get_regions_list():
    """Получить список всех регионов"""
    if data_cache['data']:
        regions = []
        for code, data in data_cache['data'].items():
            if not code.startswith('_'):
                region_data = {
                    'code': code,
                    'name': data.get('region_name', code),
                    'has_data': True,
                    'macroregion': data.get('macroregion', 'Неизвестно')
                }
                regions.append(region_data)
        
        return jsonify({
            'success': True,
            'regions': regions,
            'count': len(regions),
            'from_github': True,
            'last_updated': data_cache['last_update'],
            'timestamp': datetime.now().strftime("%H:%M:%S")
        })
    
    # Если кэш пуст, возвращаем список из REGION_INFO
    print("⚠️ Кэш пуст, возвращаю статический список регионов")
    
    # Статический список регионов (можно вынести в отдельный файл)
    static_regions = [
        {'code': 'BRT', 'name': 'Бурятия', 'has_data': False},
        {'code': 'IRK', 'name': 'Иркутская область', 'has_data': False},
        {'code': 'KAM', 'name': 'Камчатский край', 'has_data': False},
        {'code': 'KHB', 'name': 'Хабаровский край', 'has_data': False},
        {'code': 'SAH', 'name': 'Сахалинская область', 'has_data': False},
        {'code': 'VLD', 'name': 'Владивосток', 'has_data': False},
        {'code': 'ROS', 'name': 'Ростовская область', 'has_data': False},
        {'code': 'KRA', 'name': 'Краснодарский край', 'has_data': False},
        {'code': 'CNT', 'name': 'Центральный округ Москвы', 'has_data': False},
        {'code': 'SPE', 'name': 'Санкт-Петербург Восток', 'has_data': False},
    ]
    
    return jsonify({
        'success': True,
        'regions': static_regions,
        'count': len(static_regions),
        'is_static_list': True,
        'cache_status': data_cache['error'],
        'timestamp': datetime.now().strftime("%H:%M:%S")
    })

@app.route('/api/cache/status', methods=['GET'])
def cache_status():
    """Проверить статус кэша"""
    regions_count = 0
    if data_cache['data']:
        regions_count = len([k for k in data_cache['data'].keys() if not k.startswith('_')])
    
    return jsonify({
        'success': True,
        'last_update': data_cache['last_update'],
        'data_source': GITHUB_DATA_URL,
        'has_data': data_cache['data'] is not None,
        'regions_count': regions_count,
        'cache_hits': data_cache['cache_hits'],
        'github_hits': data_cache['github_hits'],
        'error': data_cache['error'],
        'timestamp': datetime.now().strftime("%H:%M:%S"),
        'server_time': datetime.now().isoformat()
    })

@app.route('/api/cache/refresh', methods=['POST'])
def refresh_cache():
    """Принудительно обновить кэш"""
    success = fetch_data_from_github()
    return jsonify({
        'success': success,
        'message': 'Кэш обновлен' if success else 'Ошибка обновления',
        'last_update': data_cache['last_update'],
        'regions_count': len([k for k in data_cache['data'].keys() if not k.startswith('_')]) if data_cache['data'] else 0,
        'timestamp': datetime.now().strftime("%H:%M:%S")
    })

@app.route('/api/history', methods=['GET'])
def get_history():
    """Заглушка для истории (не реализована в упрощенной версии)"""
    return jsonify({
        'success': True,
        'message': 'История не доступна в упрощенной версии API',
        'timestamp': datetime.now().strftime("%H:%M:%S")
    })

@app.route('/api/region/<region_code>/history', methods=['GET'])
def get_region_history(region_code):
    """Заглушка для истории региона"""
    return jsonify({
        'success': True,
        'region_code': region_code,
        'message': 'История региона не доступна в упрощенной версии',
        'timestamp': datetime.now().strftime("%H:%M:%S")
    })

@app.errorhandler(404)
def not_found(error):
    """Обработчик 404 ошибок"""
    return jsonify({
        'success': False,
        'error': 'Endpoint не найден',
        'timestamp': datetime.now().strftime("%H:%M:%S"),
        'available_endpoints': [
            '/api/test',
            '/api/region/<код>',
            '/api/region/<код>/refresh',
            '/api/regions',
            '/api/cache/status',
            '/api/cache/refresh'
        ]
    }), 404

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 API СЕРВЕР ЗАПУЩЕН")
    print(f"📁 Источник данных: {GITHUB_DATA_URL}")
    print(f"🕐 Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if data_cache['data']:
        regions = [k for k in data_cache['data'].keys() if not k.startswith('_')]
        print(f"📊 Загружено регионов: {len(regions)}")
        if regions:
            print(f"   Примеры: {', '.join(regions[:5])}")
        print(f"⏰ Последнее обновление: {data_cache['last_update']}")
    else:
        print("⚠️ Данные не загружены!")
        if data_cache['error']:
            print(f"❌ Ошибка: {data_cache['error']}")
        print("   API будет возвращать тестовые данные")
    
    print("\n📡 Доступные endpoints:")
    print("   - GET  /api/test - тест сервера")
    print("   - GET  /api/region/<код> - данные региона")
    print("   - POST /api/region/<код>/refresh - обновить кэш")
    print("   - GET  /api/regions - список регионов")
    print("   - GET  /api/cache/status - статус кэша")
    print("   - POST /api/cache/refresh - обновить кэш")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=5000, debug=False)
