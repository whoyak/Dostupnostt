"""
🌐 API СЕРВЕР ДЛЯ ANDROID ПРИЛОЖЕНИЯ
Запускается на Render.com, берет данные из GitHub
"""

import os
import requests
import logging
import json
import base64
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS

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
    
    # 🔗 GitHub репозиторий с данными
    GITHUB_REPO = os.environ.get('GITHUB_REPO', 'whoyak/region-data-cache')
    GITHUB_BRANCH = os.environ.get('GITHUB_BRANCH', 'main')
    
    # 🔑 GitHub токен (для большего лимита запросов, необязательно)
    GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
    
    # ⚙️ Настройки запросов
    REQUEST_TIMEOUT = int(os.environ.get('REQUEST_TIMEOUT', 10))
    CACHE_TIMEOUT = int(os.environ.get('CACHE_TIMEOUT', 300))  # кеширование 5 минут
    
    # 🔧 Прямой доступ к GitHub API (если нужна история через API)
    USE_GITHUB_API = os.environ.get('USE_GITHUB_API', 'false').lower() == 'true'
    
    # 📋 Список доступных регионов
    AVAILABLE_REGIONS = [
        'BRT', 'IRK', 'KAM', 'KHB', 'SAH', 'VLD', 'BIR', 'AND', 'MGD', 'CHV',
        'IZH', 'KAZ', 'NIN', 'SAM', 'YOL', 'KIR', 'ULN', 'CNT', 'NEA', 'NWS',
        'SEA', 'SWS', 'ARH', 'KLN', 'MUR', 'NOV', 'PSK', 'PZV', 'SPE', 'SPN',
        'SPS', 'SPW', 'VOL', 'NEN', 'BRN', 'KHA', 'KRS', 'NSK', 'OMS', 'TYV',
        'GRN', 'KEM', 'TOM', 'CHE', 'EKT', 'HAN', 'KOM', 'ORB', 'PRM', 'TUM',
        'YNR', 'KRG', 'UFA', 'IVN', 'KLG', 'KOS', 'RYZ', 'SMO', 'TUL', 'TVE',
        'VLA', 'YRL', 'BEL', 'BRY', 'KUR', 'LIP', 'MRD', 'ORL', 'PNZ', 'SRV',
        'TAM', 'VRN', 'KRA', 'ROS', 'STV', 'VLG'
    ]

# ================== КЕШИРОВАНИЕ ==================

class DataCache:
    """Простой кеш для данных GitHub"""
    
    _cache = {}
    
    @classmethod
    def get(cls, key):
        """Получить данные из кеша"""
        if key in cls._cache:
            data, timestamp = cls._cache[key]
            if datetime.now() - timestamp < timedelta(seconds=Config.CACHE_TIMEOUT):
                logger.debug(f"📦 Данные из кеша: {key}")
                return data
        return None
    
    @classmethod
    def set(cls, key, data):
        """Сохранить данные в кеш"""
        cls._cache[key] = (data, datetime.now())
    
    @classmethod
    def clear(cls):
        """Очистить кеш"""
        cls._cache = {}

# ================== GITHUB КЛИЕНТ ==================

def get_github_headers():
    """Получить заголовки для запросов к GitHub"""
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'RegionDataAPI/1.0'
    }
    
    if Config.GITHUB_TOKEN:
        headers['Authorization'] = f'token {Config.GITHUB_TOKEN}'
    
    return headers

def fetch_from_github_raw(filename):
    """Получить данные из GitHub через raw.githubusercontent.com"""
    cache_key = f"github_raw_{filename}"
    
    # Проверяем кеш
    cached_data = DataCache.get(cache_key)
    if cached_data:
        return cached_data
    
    try:
        url = f"https://raw.githubusercontent.com/{Config.GITHUB_REPO}/{Config.GITHUB_BRANCH}/{filename}"
        
        logger.info(f"🌐 Запрос к GitHub RAW: {filename}")
        response = requests.get(
            url, 
            headers=get_github_headers(),
            timeout=Config.REQUEST_TIMEOUT
        )
        
        if response.status_code == 200:
            if filename.endswith('.json'):
                data = response.json()
            else:
                data = response.text
            
            # Кешируем
            DataCache.set(cache_key, data)
            logger.info(f"✅ Данные получены из GitHub RAW: {filename}")
            return data
        else:
            logger.warning(f"⚠️ GitHub RAW вернул {response.status_code}: {filename}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Ошибка при запросе GitHub RAW: {filename} - {e}")
        return None

def fetch_from_github_api(filename):
    """Получить данные из GitHub через API (для получения метаданных)"""
    if not Config.USE_GITHUB_API:
        return None
    
    cache_key = f"github_api_{filename}"
    
    # Проверяем кеш
    cached_data = DataCache.get(cache_key)
    if cached_data:
        return cached_data
    
    try:
        url = f"https://api.github.com/repos/{Config.GITHUB_REPO}/contents/{filename}?ref={Config.GITHUB_BRANCH}"
        
        logger.info(f"🌐 Запрос к GitHub API: {filename}")
        response = requests.get(
            url, 
            headers=get_github_headers(),
            timeout=Config.REQUEST_TIMEOUT
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if 'content' in data:
                # Декодируем base64 контент
                content = base64.b64decode(data['content']).decode('utf-8')
                if filename.endswith('.json'):
                    data['decoded_content'] = json.loads(content)
                else:
                    data['decoded_content'] = content
            
            # Кешируем
            DataCache.set(cache_key, data)
            logger.info(f"✅ Данные получены из GitHub API: {filename}")
            return data
        else:
            logger.warning(f"⚠️ GitHub API вернул {response.status_code}: {filename}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Ошибка при запросе GitHub API: {filename} - {e}")
        return None

def get_region_data(region_code):
    """Получить данные региона из GitHub"""
    region_code = region_code.upper()
    
    # Пробуем получить данные из файла региона
    region_data = fetch_from_github_raw(f"region_{region_code}.json")
    if region_data and 'success' in region_data:
        return region_data
    
    # Пробуем получить из основного файла
    main_data = fetch_from_github_raw("cached_data.json")
    if main_data and region_code in main_data:
        if 'current' in main_data[region_code]:
            region_data = main_data[region_code]['current']
            region_data['success'] = True
            return region_data
    
    # Если данные не найдены
    return {
        'success': False,
        'error': f'Данные для региона {region_code} не найдены',
        'region_code': region_code,
        'timestamp': datetime.now().isoformat()
    }

def get_region_history(region_code):
    """Получить историю региона из GitHub"""
    region_code = region_code.upper()
    
    # Пробуем получить историю из отдельного файла
    history_data = fetch_from_github_raw(f"history_{region_code}.json")
    if history_data and 'history' in history_data:
        return {
            'success': True,
            'region_code': region_code,
            'history': history_data['history'],
            'count': len(history_data['history']),
            'timestamp': datetime.now().isoformat()
        }
    
    # Пробуем получить из основного файла
    main_data = fetch_from_github_raw("cached_data.json")
    if main_data and region_code in main_data:
        if 'history' in main_data[region_code]:
            return {
                'success': True,
                'region_code': region_code,
                'history': main_data[region_code]['history'],
                'count': len(main_data[region_code]['history']),
                'timestamp': datetime.now().isoformat()
            }
    
    # Если история не найдена
    return {
        'success': False,
        'error': f'История для региона {region_code} не найдена',
        'region_code': region_code,
        'timestamp': datetime.now().isoformat()
    }

def get_all_regions_summary():
    """Получить сводку по всем регионам"""
    # Пробуем получить основной файл
    main_data = fetch_from_github_raw("cached_data.json")
    
    if main_data and '_meta' in main_data:
        summary = {
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'total_regions': 0,
            'regions': [],
            'last_updated': main_data['_meta'].get('last_updated', 'unknown'),
            'statistics': {}
        }
        
        # Собираем данные по регионам
        for region_code in Config.AVAILABLE_REGIONS:
            if region_code in main_data:
                region_info = main_data[region_code]
                if 'current' in region_info:
                    current = region_info['current']
                    stats = current.get('stats', {})
                    
                    summary['regions'].append({
                        'region_code': region_code,
                        'region_name': current.get('region_name', region_code),
                        'macroregion': current.get('macroregion', 'Неизвестно'),
                        'total_bs': stats.get('total_bs', 0),
                        'base_layer_percentage': stats.get('base_layer_percentage', 0),
                        'power_problems': stats.get('power_problems', 0),
                        'timestamp': current.get('timestamp', 'unknown')
                    })
        
        summary['total_regions'] = len(summary['regions'])
        
        # Статистика
        if summary['regions']:
            summary['statistics'] = {
                'total_basestations': sum(r['total_bs'] for r in summary['regions']),
                'avg_availability': sum(r['base_layer_percentage'] for r in summary['regions']) / len(summary['regions']),
                'total_power_problems': sum(r['power_problems'] for r in summary['regions']),
                'regions_with_problems': len([r for r in summary['regions'] if r['power_problems'] > 0])
            }
        
        return summary
    
    # Если основной файл не найден
    return {
        'success': False,
        'error': 'Основной файл данных не найден',
        'timestamp': datetime.now().isoformat()
    }

# ================== API ENDPOINTS ==================

@app.route('/api/region/<region_code>', methods=['GET'])
def region_data_endpoint(region_code):
    """
    🗺️ Получение данных региона
    """
    logger.info(f"🗺️ Запрос данных региона: {region_code}")
    
    region_code = region_code.upper()
    if region_code not in Config.AVAILABLE_REGIONS:
        return jsonify({
            'success': False,
            'error': f'Регион {region_code} не найден',
            'available_regions': Config.AVAILABLE_REGIONS,
            'timestamp': datetime.now().isoformat()
        }), 404
    
    region_data = get_region_data(region_code)
    return jsonify(region_data)

@app.route('/api/region/<region_code>/history', methods=['GET'])
def region_history_endpoint(region_code):
    """
    📊 Получение истории региона
    """
    logger.info(f"📊 Запрос истории региона: {region_code}")
    
    region_code = region_code.upper()
    if region_code not in Config.AVAILABLE_REGIONS:
        return jsonify({
            'success': False,
            'error': f'Регион {region_code} не найден',
            'available_regions': Config.AVAILABLE_REGIONS,
            'timestamp': datetime.now().isoformat()
        }), 404
    
    history_data = get_region_history(region_code)
    
    # Ограничиваем количество записей, если нужно
    limit = request.args.get('limit')
    if limit and limit.isdigit():
        limit = int(limit)
        if history_data.get('success') and 'history' in history_data:
            history_data['history'] = history_data['history'][:limit]
            history_data['count'] = len(history_data['history'])
    
    return jsonify(history_data)

@app.route('/api/regions/summary', methods=['GET'])
def regions_summary_endpoint():
    """
    📈 Сводка по всем регионам
    """
    logger.info("📈 Запрос сводки по всем регионам")
    summary = get_all_regions_summary()
    return jsonify(summary)

@app.route('/api/regions/list', methods=['GET'])
def regions_list_endpoint():
    """
    📋 Список всех доступных регионов
    """
    logger.info("📋 Запрос списка регионов")
    
    # Пробуем получить актуальные данные из GitHub
    main_data = fetch_from_github_raw("cached_data.json")
    
    if main_data and '_meta' in main_data:
        regions_list = []
        for region_code in Config.AVAILABLE_REGIONS:
            if region_code in main_data:
                region_info = main_data[region_code]
                if 'current' in region_info:
                    current = region_info['current']
                    regions_list.append({
                        'code': region_code,
                        'name': current.get('region_name', region_code),
                        'macroregion': current.get('macroregion', 'Неизвестно'),
                        'has_data': True,
                        'last_updated': current.get('timestamp', 'unknown')
                    })
                else:
                    regions_list.append({
                        'code': region_code,
                        'name': region_code,
                        'macroregion': 'Неизвестно',
                        'has_data': False,
                        'last_updated': 'unknown'
                    })
            else:
                regions_list.append({
                    'code': region_code,
                    'name': region_code,
                    'macroregion': 'Неизвестно',
                    'has_data': False,
                    'last_updated': 'unknown'
                })
        
        return jsonify({
            'success': True,
            'count': len(regions_list),
            'regions': regions_list,
            'total_available': len(Config.AVAILABLE_REGIONS),
            'last_updated': main_data['_meta'].get('last_updated', 'unknown'),
            'timestamp': datetime.now().isoformat()
        })
    
    # Если не удалось получить данные из GitHub
    return jsonify({
        'success': True,
        'count': len(Config.AVAILABLE_REGIONS),
        'regions': [{
            'code': code,
            'name': code,
            'macroregion': 'Неизвестно',
            'has_data': False
        } for code in Config.AVAILABLE_REGIONS],
        'total_available': len(Config.AVAILABLE_REGIONS),
        'warning': 'Не удалось получить актуальные данные, показан список регионов по умолчанию',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/test/github', methods=['GET'])
def test_github_endpoint():
    """
    🧪 Тестирование подключения к GitHub
    """
    logger.info("🧪 Тест подключения к GitHub")
    
    test_results = {
        'test': 'github_connection_test',
        'timestamp': datetime.now().isoformat(),
        'config': {
            'github_repo': Config.GITHUB_REPO,
            'github_branch': Config.GITHUB_BRANCH,
            'github_token_set': bool(Config.GITHUB_TOKEN),
            'use_github_api': Config.USE_GITHUB_API,
            'cache_timeout': Config.CACHE_TIMEOUT
        },
        'tests': {}
    }
    
    # Тест 1: Проверка конфигурации
    test_results['tests']['config_check'] = {
        'passed': bool(Config.GITHUB_REPO),
        'message': 'GitHub репозиторий настроен' if Config.GITHUB_REPO else 'GitHub репозиторий не настроен',
        'repo': Config.GITHUB_REPO,
        'branch': Config.GITHUB_BRANCH
    }
    
    # Тест 2: Проверка основного файла
    main_data = fetch_from_github_raw("cached_data.json")
    test_results['tests']['main_file'] = {
        'passed': main_data is not None,
        'message': 'Основной файл данных найден' if main_data else 'Основной файл данных не найден',
        'file': 'cached_data.json'
    }
    
    # Тест 3: Проверка файла региона (пример BRT)
    region_data = fetch_from_github_raw("region_BRT.json")
    test_results['tests']['region_file'] = {
        'passed': region_data is not None,
        'message': 'Файл региона BRT найден' if region_data else 'Файл региона BRT не найден',
        'file': 'region_BRT.json'
    }
    
    # Тест 4: Количество доступных регионов
    if main_data:
        regions_in_data = [k for k in main_data.keys() if k != '_meta']
        test_results['tests']['regions_count'] = {
            'passed': len(regions_in_data) > 0,
            'message': f'Найдено {len(regions_in_data)} регионов в данных',
            'count': len(regions_in_data),
            'regions': regions_in_data[:10]  # Показываем первые 10
        }
    
    # Общая оценка
    passed_tests = [t for t in test_results['tests'].values() if t.get('passed', False)]
    if len(passed_tests) == len(test_results['tests']):
        test_results['overall'] = 'PASSED'
    elif len(passed_tests) >= 2:
        test_results['overall'] = 'PARTIAL'
    else:
        test_results['overall'] = 'FAILED'
    
    return jsonify(test_results)

@app.route('/api/cache/clear', methods=['POST'])
def clear_cache_endpoint():
    """
    🗑️ Очистка кеша (только для администраторов)
    """
    # Простая проверка для безопасности
    auth_token = request.headers.get('X-Admin-Token')
    if not auth_token or auth_token != os.environ.get('ADMIN_TOKEN', ''):
        return jsonify({
            'success': False,
            'error': 'Доступ запрещен',
            'timestamp': datetime.now().isoformat()
        }), 403
    
    DataCache.clear()
    logger.info("🗑️ Кеш очищен")
    
    return jsonify({
        'success': True,
        'message': 'Кеш успешно очищен',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/health', methods=['GET'])
def health_check():
    """
    🩺 Проверка здоровья API
    """
    # Проверяем подключение к GitHub
    main_data = fetch_from_github_raw("cached_data.json")
    
    return jsonify({
        'status': 'healthy',
        'service': 'region_data_api',
        'timestamp': datetime.now().isoformat(),
        'github_connection': 'ok' if main_data else 'unavailable',
        'cache_size': len(DataCache._cache),
        'uptime': get_uptime(),
        'endpoints': [
            '/api/region/{code}',
            '/api/region/{code}/history',
            '/api/regions/summary',
            '/api/regions/list',
            '/api/test/github',
            '/api/health'
        ]
    })

@app.route('/')
def home():
    """
    🏠 Домашняя страница
    """
    main_data = fetch_from_github_raw("cached_data.json")
    
   
# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================

# Глобальная переменная для времени запуска
_start_time = datetime.now()

def get_uptime():
    """Получить время работы сервера"""
    delta = datetime.now() - _start_time
    hours, remainder = divmod(delta.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours)}ч {int(minutes)}м {int(seconds)}с"

# ================== ЗАПУСК СЕРВЕРА ==================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    
    print("=" * 70)
    print("🌐 REGION DATA API СЕРВЕР НА RENDER.COM")
    print("Данные берутся из GitHub репозитория")
    print("=" * 70)
    
    print(f"\n⚙️  ТЕКУЩАЯ КОНФИГУРАЦИЯ:")
    print(f"   • GitHub репозиторий: {Config.GITHUB_REPO}")
    print(f"   • Ветка:              {Config.GITHUB_BRANCH}")
    print(f"   • GitHub токен:       {'✅ Установлен' if Config.GITHUB_TOKEN else '⚠️ Не установлен'}")
    print(f"   • Таймаут запросов:   {Config.REQUEST_TIMEOUT} секунд")
    print(f"   • Кеширование:        {Config.CACHE_TIMEOUT} секунд")
    print(f"   • Регионов доступно:  {len(Config.AVAILABLE_REGIONS)}")
    
    print(f"\n📋 ДОСТУПНЫЕ ENDPOINTS:")
    print(f"   • GET /api/region/{{code}}          - Данные региона")
    print(f"   • GET /api/region/{{code}}/history  - История региона")
    print(f"   • GET /api/regions/summary         - Сводка по всем регионам")
    print(f"   • GET /api/regions/list            - Список регионов")
    print(f"   • GET /api/test/github             - Тест GitHub")
    print(f"   • GET /api/health                  - Проверка здоровья")
    
    print(f"\n📱 ДЛЯ ANDROID ПРИЛОЖЕНИЯ:")
    print(f"   Базовый URL: https://ваш-сервис.onrender.com/")
    
    print(f"\n⚠️  ВАЖНО:")
    print(f"   • Данные обновляются на GitHub каждые 10 минут")
    print(f"   • API кеширует данные на {Config.CACHE_TIMEOUT} секунд")
    print(f"   • Для увеличения лимита запросов установите GITHUB_TOKEN")
    print("=" * 70)
    
    print(f"\n🚀 Запуск API сервера на порту {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
