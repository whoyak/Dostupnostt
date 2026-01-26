"""
🌐 API СЕРВЕР ДЛЯ ANDROID ПРИЛОЖЕНИЯ
Запускается на Render.com, берет РЕАЛЬНЫЕ данные из GitHub
"""

import os
import requests
import logging
import json
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
    CACHE_TIMEOUT = int(os.environ.get('CACHE_TIMEOUT', 60))  # кеширование 60 секунд
    
    # 📋 Список доступных регионов (будем брать из данных)
    AVAILABLE_REGIONS = []  # Инициализируем пустым, потом заполним

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

def fetch_from_github_raw(filename, force_refresh=False):
    """Получить данные из GitHub через raw.githubusercontent.com"""
    cache_key = f"github_raw_{filename}"
    
    # Проверяем кеш, если не требуется принудительное обновление
    if not force_refresh:
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
                try:
                    data = response.json()
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Ошибка парсинга JSON из {filename}: {e}")
                    return None
            else:
                data = response.text
            
            # Кешируем
            DataCache.set(cache_key, data)
            logger.info(f"✅ Данные получены из GitHub RAW: {filename}")
            return data
        else:
            logger.warning(f"⚠️ GitHub RAW вернул {response.status_code}: {filename}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error(f"⏰ Таймаут при запросе к GitHub: {filename}")
        return None
    except Exception as e:
        logger.error(f"❌ Ошибка при запросе GitHub RAW: {filename} - {e}")
        return None

def get_region_data(region_code, force_refresh=False):
    """Получить РЕАЛЬНЫЕ данные региона из GitHub"""
    region_code = region_code.upper()
    
    # Пробуем получить данные из файла региона
    region_data = fetch_from_github_raw(f"region_{region_code}.json", force_refresh)
    if region_data and 'success' in region_data:
        # Добавляем мета-информацию
        region_data['source'] = 'github_raw'
        region_data['data_type'] = 'region_file'
        region_data['api_timestamp'] = datetime.now().isoformat()
        return region_data
    
    # Пробуем получить из основного файла
    main_data = fetch_from_github_raw("cached_data.json", force_refresh)
    if main_data and region_code in main_data:
        if 'current' in main_data[region_code]:
            region_data = main_data[region_code]['current']
            region_data['success'] = True
            region_data['source'] = 'github_main'
            region_data['data_type'] = 'main_file'
            region_data['api_timestamp'] = datetime.now().isoformat()
            return region_data
    
    # Если данные не найдены - возвращаем ошибку
    return {
        'success': False,
        'error': f'Данные для региона {region_code} не найдены в GitHub',
        'region_code': region_code,
        'timestamp': datetime.now().isoformat(),
        'suggestions': [
            'Убедитесь, что сборщик данных работает и загружает данные в GitHub',
            f'Проверьте наличие файла region_{region_code}.json в репозитории',
            f'Или проверьте наличие региона {region_code} в cached_data.json'
        ]
    }

def get_region_history(region_code, force_refresh=False):
    """Получить РЕАЛЬНУЮ историю региона из GitHub"""
    region_code = region_code.upper()
    
    # Пробуем получить историю из отдельного файла
    history_data = fetch_from_github_raw(f"history_{region_code}.json", force_refresh)
    if history_data and 'history' in history_data:
        return {
            'success': True,
            'region_code': region_code,
            'history': history_data['history'],
            'count': len(history_data['history']),
            'source': 'github_history_file',
            'timestamp': datetime.now().isoformat()
        }
    
    # Пробуем получить из основного файла
    main_data = fetch_from_github_raw("cached_data.json", force_refresh)
    if main_data and region_code in main_data:
        if 'history' in main_data[region_code]:
            return {
                'success': True,
                'region_code': region_code,
                'history': main_data[region_code]['history'],
                'count': len(main_data[region_code]['history']),
                'source': 'github_main_file',
                'timestamp': datetime.now().isoformat()
            }
    
    # Если история не найдена
    return {
        'success': False,
        'error': f'История для региона {region_code} не найдена',
        'region_code': region_code,
        'timestamp': datetime.now().isoformat()
    }

def get_all_regions_summary(force_refresh=False):
    """Получить РЕАЛЬНУЮ сводку по всем регионам"""
    # Пробуем получить основной файл
    main_data = fetch_from_github_raw("cached_data.json", force_refresh)
    
    if main_data and '_meta' in main_data:
        # Обновляем список доступных регионов из данных
        available_regions = [k for k in main_data.keys() if k != '_meta' and k != 'available_regions']
        
        summary = {
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'total_regions': len(available_regions),
            'regions': [],
            'last_updated': main_data['_meta'].get('last_updated', 'unknown'),
            'source': 'github_main_file',
            'statistics': {}
        }
        
        # Собираем данные по регионам
        for region_code in available_regions:
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
                        'last_updated': current.get('timestamp', 'unknown'),
                        'collected_at': current.get('collected_at', 'unknown')
                    })
        
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
        'error': 'Основной файл данных не найден в GitHub',
        'timestamp': datetime.now().isoformat(),
        'github_repo': Config.GITHUB_REPO,
        'github_branch': Config.GITHUB_BRANCH
    }

def get_available_regions_from_github():
    """Получить список доступных регионов из GitHub"""
    main_data = fetch_from_github_raw("cached_data.json")
    
    if main_data:
        # Получаем регионы из данных
        available_regions = [k for k in main_data.keys() if k != '_meta' and k != 'available_regions']
        return available_regions
    
    return []

# ================== API ENDPOINTS ==================

@app.route('/api/region/<region_code>', methods=['GET'])
def region_data_endpoint(region_code):
    """
    🗺️ Получение данных региона (РЕАЛЬНЫЕ данные из GitHub)
    """
    force_refresh = request.args.get('refresh', 'false').lower() == 'true'
    
    logger.info(f"🗺️ Запрос данных региона: {region_code} (refresh: {force_refresh})")
    
    region_code = region_code.upper()
    
    # Получаем актуальные данные
    region_data = get_region_data(region_code, force_refresh)
    
    # Если регион не найден, но есть в списке доступных
    if not region_data.get('success') and Config.AVAILABLE_REGIONS:
        if region_code in Config.AVAILABLE_REGIONS:
            region_data['warning'] = f'Регион {region_code} есть в списке, но данных нет в GitHub'
    
    return jsonify(region_data)

@app.route('/api/region/<region_code>/history', methods=['GET'])
def region_history_endpoint(region_code):
    """
    📊 Получение истории региона (РЕАЛЬНАЯ история из GitHub)
    """
    force_refresh = request.args.get('refresh', 'false').lower() == 'true'
    
    logger.info(f"📊 Запрос истории региона: {region_code} (refresh: {force_refresh})")
    
    region_code = region_code.upper()
    
    history_data = get_region_history(region_code, force_refresh)
    
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
    📈 Сводка по всем регионам (РЕАЛЬНЫЕ данные из GitHub)
    """
    force_refresh = request.args.get('refresh', 'false').lower() == 'true'
    
    logger.info(f"📈 Запрос сводки по всем регионам (refresh: {force_refresh})")
    summary = get_all_regions_summary(force_refresh)
    return jsonify(summary)

@app.route('/api/regions/list', methods=['GET'])
def regions_list_endpoint():
    """
    📋 Список всех доступных регионов (из GitHub)
    """
    force_refresh = request.args.get('refresh', 'false').lower() == 'true'
    
    logger.info(f"📋 Запрос списка регионов (refresh: {force_refresh})")
    
    # Получаем актуальные данные
    summary = get_all_regions_summary(force_refresh)
    
    if summary.get('success'):
        # Используем данные из сводки
        return jsonify({
            'success': True,
            'count': len(summary['regions']),
            'regions': summary['regions'],
            'total_available': summary['total_regions'],
            'last_updated': summary['last_updated'],
            'timestamp': datetime.now().isoformat()
        })
    else:
        # Если не удалось получить данные, возвращаем пустой список
        return jsonify({
            'success': False,
            'error': summary.get('error', 'Не удалось получить список регионов'),
            'count': 0,
            'regions': [],
            'timestamp': datetime.now().isoformat()
        })

@app.route('/api/refresh', methods=['POST'])
def refresh_data_endpoint():
    """
    🔄 Принудительное обновление данных (очистка кеша)
    """
    logger.info("🔄 Принудительное обновление данных (очистка кеша)")
    
    # Простая проверка для безопасности
    auth_token = request.headers.get('X-Refresh-Token')
    if auth_token and auth_token == os.environ.get('REFRESH_TOKEN', ''):
        # Очищаем кеш
        cache_size_before = len(DataCache._cache)
        DataCache.clear()
        
        # Обновляем список регионов
        global_regions = get_available_regions_from_github()
        if global_regions:
            Config.AVAILABLE_REGIONS = global_regions
        
        logger.info(f"🗑️ Кеш очищен (было {cache_size_before} элементов)")
        
        return jsonify({
            'success': True,
            'message': 'Кеш успешно очищен',
            'cache_cleared': cache_size_before,
            'regions_updated': len(global_regions) if global_regions else 0,
            'timestamp': datetime.now().isoformat()
        })
    else:
        # Разрешаем обновление без токена, но с предупреждением
        cache_size_before = len(DataCache._cache)
        DataCache.clear()
        
        logger.warning(f"⚠️ Кеш очищен без авторизации (было {cache_size_before} элементов)")
        
        return jsonify({
            'success': True,
            'message': 'Кеш очищен (публичный доступ)',
            'warning': 'Для защищенного доступа используйте X-Refresh-Token',
            'cache_cleared': cache_size_before,
            'timestamp': datetime.now().isoformat()
        })

@app.route('/api/health', methods=['GET'])
def health_check():
    """
    🩺 Проверка здоровья API и подключения к GitHub
    """
    # Проверяем подключение к GitHub
    main_data = fetch_from_github_raw("cached_data.json", force_refresh=True)
    
    health_status = {
        'status': 'healthy',
        'service': 'region_data_api',
        'timestamp': datetime.now().isoformat(),
        'github': {
            'connected': main_data is not None,
            'repo': Config.GITHUB_REPO,
            'branch': Config.GITHUB_BRANCH
        },
        'cache': {
            'size': len(DataCache._cache),
            'timeout_seconds': Config.CACHE_TIMEOUT
        },
        'uptime': get_uptime(),
        'endpoints': [
            {'method': 'GET', 'path': '/api/region/{code}', 'desc': 'Данные региона'},
            {'method': 'GET', 'path': '/api/region/{code}/history', 'desc': 'История региона'},
            {'method': 'GET', 'path': '/api/regions/summary', 'desc': 'Сводка по регионам'},
            {'method': 'GET', 'path': '/api/regions/list', 'desc': 'Список регионов'},
            {'method': 'POST', 'path': '/api/refresh', 'desc': 'Обновление кеша'},
            {'method': 'GET', 'path': '/api/health', 'desc': 'Проверка здоровья'}
        ]
    }
    
    # Если GitHub недоступен, меняем статус
    if not main_data:
        health_status['status'] = 'degraded'
        health_status['warning'] = 'GitHub недоступен'
    
    return jsonify(health_status)

@app.route('/')
def home():
    """
    🏠 Домашняя страница
    """
    # Получаем актуальные данные для статуса
    main_data = fetch_from_github_raw("cached_data.json")
    
    if main_data:
        github_status = "✅ OK"
        github_status_class = "success"
        if '_meta' in main_data:
            last_updated = main_data['_meta'].get('last_updated', 'unknown')
            # Преобразуем ISO строку в читаемый формат
            try:
                dt = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                last_updated = dt.strftime('%d.%m.%Y %H:%M:%S')
            except:
                pass
        else:
            last_updated = 'unknown'
        
        # Считаем регионы
        regions_count = len([k for k in main_data.keys() if k != '_meta'])
    else:
        github_status = "❌ Ошибка"
        github_status_class = "error"
        last_updated = "неизвестно"
        regions_count = 0
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🌐 Region Data API</title>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
            .card {{ background: #f5f5f5; padding: 20px; margin: 20px 0; border-radius: 8px; }}
            .success {{ color: #4CAF50; font-weight: bold; }}
            .warning {{ color: #FF9800; font-weight: bold; }}
            .error {{ color: #f44336; font-weight: bold; }}
            code {{ background: #eee; padding: 2px 6px; border-radius: 3px; }}
            pre {{ background: #f8f8f8; padding: 10px; border-radius: 5px; overflow-x: auto; }}
            .endpoint {{ background: #e8f5e8; padding: 10px; margin: 5px 0; border-left: 4px solid #4CAF50; }}
            .refresh-btn {{ background: #4CAF50; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }}
            .refresh-btn:hover {{ background: #45a049; }}
        </style>
    </head>
    <body>
        <h1>🌐 Region Data API Server</h1>
        <p>API сервер для Android приложения мониторинга доступности базовых станций</p>
        <p>Данные берутся из GitHub репозитория: <code>{Config.GITHUB_REPO}</code> (ветка: <code>{Config.GITHUB_BRANCH}</code>)</p>
        
        <div class="card">
            <h2>📊 Статус системы</h2>
            <p>GitHub подключение: <span class="{github_status_class}">{github_status}</span></p>
            <p>Последнее обновление данных: <span class="success">🕒 {last_updated}</span></p>
            <p>Кеш: <span class="success">✅ {len(DataCache._cache)} элементов</span></p>
            <p>Время работы сервера: <span class="success">✅ {get_uptime()}</span></p>
            <p>Регионов доступно: <span class="success">✅ {regions_count}</span></p>
            
            <button class="refresh-btn" onclick="refreshCache()">🔄 Обновить данные</button>
            <script>
                function refreshCache() {{
                    fetch('/api/refresh', {{ method: 'POST' }})
                        .then(response => response.json())
                        .then(data => {{
                            if (data.success) {{
                                alert('Кеш обновлен! Запрос новых данных из GitHub...');
                                location.reload();
                            }} else {{
                                alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
                            }}
                        }})
                        .catch(error => {{
                            alert('Ошибка сети: ' + error);
                        }});
                }}
            </script>
        </div>
        
        <div class="card">
            <h2>🔗 Основные Endpoints</h2>
            
            <div class="endpoint">
                <h3>GET <code>/api/region/{{code}}</code></h3>
                <p>Получить данные конкретного региона</p>
                <p><strong>Пример:</strong> <a href="/api/region/BRT" target="_blank">/api/region/BRT</a></p>
                <p><strong>С параметром обновления:</strong> <a href="/api/region/BRT?refresh=true" target="_blank">/api/region/BRT?refresh=true</a></p>
            </div>
            
            <div class="endpoint">
                <h3>GET <code>/api/region/{{code}}/history</code></h3>
                <p>Получить историю региона</p>
                <p><strong>Пример:</strong> <a href="/api/region/BRT/history" target="_blank">/api/region/BRT/history</a></p>
            </div>
            
            <div class="endpoint">
                <h3>GET <code>/api/regions/summary</code></h3>
                <p>Сводка по всем регионам</p>
                <p><strong>Пример:</strong> <a href="/api/regions/summary" target="_blank">/api/regions/summary</a></p>
            </div>
            
            <div class="endpoint">
                <h3>GET <code>/api/regions/list</code></h3>
                <p>Список всех доступных регионов</p>
                <p><strong>Пример:</strong> <a href="/api/regions/list" target="_blank">/api/regions/list</a></p>
            </div>
            
            <div class="endpoint">
                <h3>GET <code>/api/health</code></h3>
                <p>Проверка здоровья API</p>
                <p><strong>Пример:</strong> <a href="/api/health" target="_blank">/api/health</a></p>
            </div>
        </div>
        
        <div class="card">
            <h2>⚙️ Конфигурация</h2>
            <p>GitHub репозиторий: <code>{Config.GITHUB_REPO}</code></p>
            <p>Ветка: <code>{Config.GITHUB_BRANCH}</code></p>
            <p>Таймаут запросов: <code>{Config.REQUEST_TIMEOUT} секунд</code></p>
            <p>Кеширование: <code>{Config.CACHE_TIMEOUT} секунд</code></p>
            <p>GitHub токен: <code>{'Установлен' if Config.GITHUB_TOKEN else 'Не установлен'}</code></p>
        </div>
        
        <div class="card">
            <h2>📱 Для Android приложения</h2>
            <p>В файле ApiClient.kt укажите базовый URL:</p>
            <pre>private const val BASE_URL = "https://ваш-сервис.onrender.com/"</pre>
            
            <p>Пример кода для получения данных региона:</p>
            <pre>
// Kotlin пример с обновлением данных
suspend fun getRegionData(regionCode: String, forceRefresh: Boolean = false): ApiResponse {{
    val url = if (forceRefresh) {{
        "/api/region/${{regionCode}}?refresh=true"
    }} else {{
        "/api/region/${{regionCode}}"
    }}
    return apiClient.get(url)
}}</pre>
        </div>
    </body>
    </html>
    """

# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================

# Глобальная переменная для времени запуска
_start_time = datetime.now()

def get_uptime():
    """Получить время работы сервера"""
    delta = datetime.now() - _start_time
    hours, remainder = divmod(delta.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours)}ч {int(minutes)}м {int(seconds)}с"

# ================== ИНИЦИАЛИЗАЦИЯ ==================

# При запуске получаем список регионов из GitHub
@app.before_first_request
def initialize_app():
    """Инициализация приложения при первом запросе"""
    logger.info("🚀 Инициализация API сервера...")
    
    # Получаем список регионов из GitHub
    global_regions = get_available_regions_from_github()
    if global_regions:
        Config.AVAILABLE_REGIONS = global_regions
        logger.info(f"✅ Загружено {len(global_regions)} регионов из GitHub")
    else:
        logger.warning("⚠️ Не удалось загрузить регионы из GitHub, используется пустой список")
        Config.AVAILABLE_REGIONS = []

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
    
    print(f"\n📋 ДОСТУПНЫЕ ENDPOINTS:")
    print(f"   • GET /api/region/{{code}}          - Данные региона (добавьте ?refresh=true для обновления)")
    print(f"   • GET /api/region/{{code}}/history  - История региона")
    print(f"   • GET /api/regions/summary         - Сводка по всем регионам")
    print(f"   • GET /api/regions/list            - Список регионов")
    print(f"   • POST /api/refresh                - Обновление кеша")
    print(f"   • GET /api/health                  - Проверка здоровья")
    
    print(f"\n📱 ДЛЯ ANDROID ПРИЛОЖЕНИЯ:")
    print(f"   Базовый URL: https://ваш-сервис.onrender.com/")
    print(f"   Для обновления данных: ?refresh=true или POST /api/refresh")
    
    print(f"\n⚠️  ВАЖНО:")
    print(f"   • Только РЕАЛЬНЫЕ данные из GitHub, без заглушек")
    print(f"   • Для принудительного обновления используйте параметр ?refresh=true")
    print(f"   • Или отправьте POST запрос на /api/refresh")
    print(f"   • Кеш автоматически обновляется каждые {Config.CACHE_TIMEOUT} секунд")
    print("=" * 70)
    
    print(f"\n🚀 Запуск API сервера на порту {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
