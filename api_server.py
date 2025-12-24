"""
API СЕРВЕР ДЛЯ ДОСТУПНОСТИ РЕГИОНОВ
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
        'version': '1.0.0'
    })

@app.route('/api/region/<region_code>', methods=['GET'])
def get_region_data(region_code):
    """Получение данных региона"""
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
    """Получение истории региона"""
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
                        item_time = datetime.fromisoformat(item.get('created_at', '2000-01-01').replace('Z', '+00:00'))
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
                        item_time = datetime.fromisoformat(item.get('created_at', '2000-01-01').replace('Z', '+00:00'))
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
                'timestamp': datetime.now().isoformat()
            })
        
        # Если истории нет, возвращаем пустую
        return jsonify({
            'success': True,
            'region_code': region_code,
            'history': [],
            'count': 0,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'region_code': region_code
        }), 500

@app.route('/api/region/<region_code>/refresh', methods=['POST'])
def refresh_region_data(region_code):
    """Принудительное обновление данных региона"""
    try:
        # В реальности здесь можно было бы запросить обновление у сборщика
        # Но пока просто возвращаем текущие данные с пометкой об обновлении
        
        data = fetch_from_github(f"region_{region_code}.json")
        if data:
            data['forced_refresh'] = True
            data['refresh_timestamp'] = datetime.now().isoformat()
            return jsonify(data)
        
        # Если данных нет, возвращаем mock с пометкой обновления
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
                        'last_updated': current.get('timestamp', '00:00:00')
                    })
            
            return jsonify({
                'success': True,
                'regions': regions_list,
                'count': len(regions_list),
                'timestamp': datetime.now().isoformat()
            })
        
        # Если данных нет, возвращаем пустой список
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
        'service': 'dostupnost-api'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
