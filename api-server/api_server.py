from flask import Flask, jsonify, request
from flask_cors import CORS
import mysql.connector
from datetime import datetime, timedelta
import sqlite3
import re
import random

app = Flask(__name__)
CORS(app)

# Конфигурация БД (из вашего бота)
DB_CONFIG = {
    'host': '10.12.98.135',
    'user': 'DB_User',
    'password': 'DB_USER_admin',
    'database': 'sth_test',
    'port': 3306,
    'connection_timeout': 5,
    'connect_timeout': 5
}

# Конфигурация локальной SQLite для истории
HISTORY_DB = 'region_history.db'

# Информация о регионах (из вашего файла)
REGION_INFO = {
    # Байкал и Дальний Восток регионы
    'BRT': {'name': 'Бурятия', 'mr': 'Байкал и Дальний Восток'},
    'IRK': {'name': 'Иркутская область', 'mr': 'Байкал и Дальний Восток'},
    'KAM': {'name': 'Камчатский край', 'mr': 'Байкал и Дальний Восток'},
    'KHB': {'name': 'Хабаровский край', 'mr': 'Байкал и Дальний Восток'},
    'SAH': {'name': 'Сахалинская область', 'mr': 'Байкал и Дальний Восток'},
    'VLD': {'name': 'Владивосток', 'mr': 'Байкал и Дальний Восток'},
    'BIR': {'name': 'Биробиджан', 'mr': 'Байкал и Дальний Восток'},
    'AND': {'name': 'Андомский', 'mr': 'Байкал и Дальний Восток'},
    'MGD': {'name': 'Магаданская область', 'mr': 'Байкал и Дальний Восток'},

    # Волга регионы
    'CHV': {'name': 'Чувашия', 'mr': 'Волга'},
    'IZH': {'name': 'Ижевск', 'mr': 'Урал'},  # Ижевск относится к Уральскому региону
    'KAZ': {'name': 'Казань', 'mr': 'Волга'},
    'NIN': {'name': 'Нижний Новгород', 'mr': 'Волга'},
    'SAM': {'name': 'Самара', 'mr': 'Волга'},
    'YOL': {'name': 'Йошкар-Ола', 'mr': 'Волга'},
    'KIR': {'name': 'Киров', 'mr': 'Волга'},
    'ULN': {'name': 'Ульяновск', 'mr': 'Волга'},

    # Москва регионы
    'CNT': {'name': 'Центральный округ Москвы', 'mr': 'Москва'},
    'NEA': {'name': 'Северо-Восточный округ Москвы', 'mr': 'Москва'},
    'NWS': {'name': 'Северо-Западный округ Москвы', 'mr': 'Москва'},
    'SEA': {'name': 'Юго-Восточный округ Москвы', 'mr': 'Москва'},
    'SWS': {'name': 'Юго-Западный округ Москвы', 'mr': 'Москва'},

    # Северо-Запад регионы
    'ARH': {'name': 'Архангельская область', 'mr': 'Северо-запад'},
    'KLN': {'name': 'Калининградская область', 'mr': 'Северо-запад'},
    'MUR': {'name': 'Мурманская область', 'mr': 'Северо-запад'},
    'NOV': {'name': 'Новгородская область', 'mr': 'Северо-запад'},
    'PSK': {'name': 'Псковская область', 'mr': 'Северо-запад'},
    'PZV': {'name': 'Петрозаводск', 'mr': 'Северо-запад'},
    'SPE': {'name': 'Санкт-Петербург Восток', 'mr': 'Северо-запад'},
    'SPN': {'name': 'Санкт-Петербург Север', 'mr': 'Северо-запад'},
    'SPS': {'name': 'Санкт-Петербург Юг', 'mr': 'Северо-запад'},
    'SPW': {'name': 'Санкт-Петербург Запад', 'mr': 'Северо-запад'},
    'VOL': {'name': 'Вологда', 'mr': 'Северо-запад'},
    'NEN': {'name': 'Ненецкий автономный округ', 'mr': 'Северо-запад'},

    # Сибирь регионы
    'BRN': {'name': 'Барнаул', 'mr': 'Сибирь'},
    'KHA': {'name': 'Красноярский край', 'mr': 'Сибирь'},
    'KRS': {'name': 'Красноярск', 'mr': 'Сибирь'},
    'NSK': {'name': 'Новосибирская область', 'mr': 'Сибирь'},
    'OMS': {'name': 'Омская область', 'mr': 'Сибирь'},
    'TYV': {'name': 'Тыва', 'mr': 'Сибирь'},
    'GRN': {'name': 'Горно-Алтайск', 'mr': 'Сибирь'},
    'KEM': {'name': 'Кемеровская область', 'mr': 'Сибирь'},
    'TOM': {'name': 'Томская область', 'mr': 'Сибирь'},

    # Урал регионы
    'CHE': {'name': 'Челябинская область', 'mr': 'Урал'},
    'EKT': {'name': 'Екатеринбург', 'mr': 'Урал'},
    'HAN': {'name': 'Ханты-Мансийский АО', 'mr': 'Урал'},
    'KOM': {'name': 'Коми', 'mr': 'Урал'},
    'ORB': {'name': 'Оренбургская область', 'mr': 'Урал'},
    'PRM': {'name': 'Пермский край', 'mr': 'Урал'},
    'TUM': {'name': 'Тюменская область', 'mr': 'Урал'},
    'YNR': {'name': 'Ямало-Ненецкий АО', 'mr': 'Урал'},
    'KRG': {'name': 'Курганская область', 'mr': 'Урал'},
    'UFA': {'name': 'Уфа', 'mr': 'Урал'},

    # Центр регионы
    'IVN': {'name': 'Ивановская область', 'mr': 'Центр'},
    'KLG': {'name': 'Калужская область', 'mr': 'Центр'},
    'KOS': {'name': 'Костромская область', 'mr': 'Центр'},
    'RYZ': {'name': 'Рязанская область', 'mr': 'Центр'},
    'SMO': {'name': 'Смоленская область', 'mr': 'Центр'},
    'TUL': {'name': 'Тульская область', 'mr': 'Центр'},
    'TVE': {'name': 'Тверская область', 'mr': 'Центр'},
    'VLA': {'name': 'Владимирская область', 'mr': 'Центр'},
    'YRL': {'name': 'Ярославская область', 'mr': 'Центр'},

    # Черноземье регионы
    'BEL': {'name': 'Белгородская область', 'mr': 'Черноземье'},
    'BRY': {'name': 'Брянская область', 'mr': 'Черноземье'},
    'KUR': {'name': 'Курская область', 'mr': 'Черноземье'},
    'LIP': {'name': 'Липецкая область', 'mr': 'Черноземье'},
    'MRD': {'name': 'Мордовия', 'mr': 'Черноземье'},
    'ORL': {'name': 'Орловская область', 'mr': 'Черноземье'},
    'PNZ': {'name': 'Пензенская область', 'mr': 'Черноземье'},
    'SRV': {'name': 'Саратовская область', 'mr': 'Черноземье'},
    'TAM': {'name': 'Тамбовская область', 'mr': 'Черноземье'},
    'VRN': {'name': 'Воронежская область', 'mr': 'Черноземье'},

    # Юг регионы
    'KRA': {'name': 'Краснодарский край', 'mr': 'ЮГ'},
    'ROS': {'name': 'Ростовская область', 'mr': 'ЮГ'},
    'STV': {'name': 'Ставропольский край', 'mr': 'ЮГ'},
    'VLG': {'name': 'Волгоградская область', 'mr': 'ЮГ'}
}


def get_db_connection():
    """Создать новое соединение с БД"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as e:
        print(f"Ошибка подключения к БД: {e}")
        return None


def init_history_db():
    """Инициализировать базу данных для истории"""
    conn = sqlite3.connect(HISTORY_DB)
    cursor = conn.cursor()

    # Таблица для хранения истории регионов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS region_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region_code TEXT NOT NULL,
            base_layer_count INTEGER,
            total_bs_count INTEGER,
            power_problems INTEGER,
            non_priority_percentage INTEGER,
            timestamp DATETIME NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Индексы для быстрого поиска
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_region_code ON region_history(region_code)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON region_history(timestamp)')

    conn.commit()
    conn.close()
    print(f"✅ База данных истории инициализирована: {HISTORY_DB}")


def save_to_history(region_code, data):
    """Сохранить данные в историю"""
    try:
        conn = sqlite3.connect(HISTORY_DB)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO region_history 
            (region_code, base_layer_count, total_bs_count, power_problems, non_priority_percentage, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            region_code,
            data.get('base_layer_count', 0),
            data.get('total_bs_count', 0),
            data.get('power_problems', 0),
            data.get('non_priority_percentage', 0),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))

        conn.commit()
        conn.close()
        print(f"💾 Данные сохранены в историю для региона {region_code}")
        return True
    except Exception as e:
        print(f"❌ Ошибка при сохранении в историю: {e}")
        return False


def get_history(region_code, hours=24):
    """Получить историю данных за последние N часов"""
    try:
        conn = sqlite3.connect(HISTORY_DB)
        cursor = conn.cursor()

        time_threshold = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            SELECT 
                region_code,
                base_layer_count,
                total_bs_count,
                power_problems,
                non_priority_percentage,
                timestamp,
                created_at
            FROM region_history 
            WHERE region_code = ? AND timestamp >= ?
            ORDER BY timestamp DESC
            LIMIT 100
        ''', (region_code, time_threshold))

        history = []
        for row in cursor.fetchall():
            history.append({
                'region_code': row[0],
                'base_layer_count': row[1],
                'total_bs_count': row[2],
                'power_problems': row[3],
                'non_priority_percentage': row[4],
                'timestamp': row[5],
                'created_at': row[6],
                'base_layer_percentage': int((row[1] / row[2] * 100)) if row[2] > 0 else 0
            })

        conn.close()
        return history
    except Exception as e:
        print(f"❌ Ошибка при получении истории: {e}")
        return []


def get_latest_data(region_code):
    """Получить последние сохраненные данные"""
    try:
        conn = sqlite3.connect(HISTORY_DB)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT 
                base_layer_count,
                total_bs_count,
                power_problems,
                non_priority_percentage,
                timestamp
            FROM region_history 
            WHERE region_code = ?
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (region_code,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'base_layer_count': row[0],
                'total_bs_count': row[1],
                'power_problems': row[2],
                'non_priority_percentage': row[3],
                'timestamp': row[4],
                'base_layer_percentage': int((row[0] / row[1] * 100)) if row[1] > 0 else 0
            }
        return None
    except Exception as e:
        print(f"❌ Ошибка при получении последних данных: {e}")
        return None


def get_real_region_data(region_code):
    """Получить реальные данные региона из БД"""
    conn = get_db_connection()
    if not conn:
        return {
            'success': False,
            'error': 'Нет подключения к БД',
            'region_code': region_code,
            'region_name': REGION_INFO.get(region_code, {}).get('name', region_code),
            'timestamp': datetime.now().strftime("%H:%M:%S")
        }

    cursor = conn.cursor()

    try:
        # Получаем данные региона
        cursor.execute("""
            SELECT gm.*, nmg.*, nm.*, nw.* 
            FROM graf_map gm 
            LEFT JOIN noc_gen_map nmg ON gm.hostname = nmg.bs 
            LEFT JOIN noc_map nm ON gm.hostname = nm.bs 
            LEFT JOIN noc_wo nw ON gm.hostname = nw.bs 
            WHERE gm.zip_code = %s
        """, (region_code,))

        results = cursor.fetchall()

        cursor.execute("SELECT * FROM noc_gen_map WHERE reg = %s", (region_code,))
        registration = cursor.fetchall()

        cursor.execute("SELECT * FROM noc_map WHERE reg = %s", (region_code,))
        gen_prio = cursor.fetchall()

        cursor.close()
        conn.close()

        current = datetime.now()
        formatted = current.strftime("%d.%m.%Y %H:%M:")

        # Группируем результаты по уникальным BS (hostname)
        unique_bs = {}
        for i in results:
            bs_name = i[3]  # BS name
            if bs_name not in unique_bs:
                unique_bs[bs_name] = i

        # 1. БАЗОВЫЙ СЛОЙ (первое сообщение)
        base_layer_msg = f'{region_code} Базовый слой {formatted}\n\n'
        count = 0
        base_tech = []
        power_count = 0

        # Обрабатываем только уникальные BS
        for bs_name, i in unique_bs.items():
            if i[8] == 'N' or i[5] is not None:  # Проверяем базовый слой
                count += 1
                power = 'Да' if i[6] == 'Y' else 'Нет'
                presense = 'Да' if i[7] == 'Y' else 'Нет'
                wo = 'Есть' if i[34] is not None else 'Нет'

                base_layer_msg += f'{count}) {bs_name} {i[5]}\n'
                base_tech.append(bs_name)
                base_layer_msg += f'Power {power}; Посещение {presense}; WO {wo}\n'

        # Считаем POWER
        unique_power_bs = set()
        for i in results:
            bs_name = i[3]  # Номер БС
            if i[6] == 'N' and i[30] == 'POWER' and bs_name not in unique_power_bs:
                power_count += 1
                unique_power_bs.add(bs_name)

        base_layer_msg += f'\nВсего активных POWER на сети: {power_count}\n'
        base_layer_msg += f'Всего BS: {len(unique_bs)}\n'
        base_layer_msg += f'Базовый слой: {count}/{len(unique_bs)}\n'

        # Приоритеты
        prio_dict = {}
        for j in gen_prio:
            bs_name = j[4]  # BS name
            if bs_name not in prio_dict:
                prio = j[6]  # Приоритет
                alarm = j[5]  # Тип аварии
                prio_dict[bs_name] = {'prio': prio, 'alarm': alarm}

        wo9_bool = True
        wo3_bool = True
        wo10_bool = True

        for bs_name, i in unique_bs.items():
            if bs_name in prio_dict:
                prio_info = prio_dict[bs_name]
                wo_status = 'Есть' if i[34] is not None else 'Нет'

                if prio_info['prio'] == '10' and prio_info['alarm'] == 'POWER':
                    if wo10_bool:
                        base_layer_msg += f'\n10 приоритет:\n'
                        wo10_bool = False
                    base_layer_msg += f'- {bs_name}; wo {wo_status};Время {i[26]}\n'

                elif prio_info['prio'] == '9' and prio_info['alarm'] == 'POWER':
                    if wo9_bool:
                        base_layer_msg += f'\n9 приоритет:\n'
                        wo9_bool = False
                    base_layer_msg += f'- {bs_name}; wo {wo_status};Время {i[26]}\n'

                elif prio_info['prio'] == '3' and prio_info['alarm'] == 'POWER':
                    if wo3_bool:
                        base_layer_msg += f'\n3 приоритет:\n'
                        wo3_bool = False
                    base_layer_msg += f'- {bs_name}; wo {wo_status};Время {i[26]}\n'

        # Регистрации
        base_layer_msg += f'\nОткрытые посещения:\n'

        unique_registrations = {}
        for i in registration:
            bs_name = i[4]  # BS name
            if bs_name not in unique_registrations:
                unique_registrations[bs_name] = i

        count_reg = 0
        count_reg_gen = 0
        for bs_name, i in unique_registrations.items():
            if i[7] is not None:
                count_reg += 1
            if i[7] == 'f gen':
                count_reg_gen += 1

        base_layer_msg += f'Открыто всего посещений: {count_reg}\n'
        base_layer_msg += f'Открыто регистраций f gen: {count_reg_gen}\n'

        # 2. НЕПРИОРИТЕТНЫЕ ТЕХНОЛОГИИ (второе сообщение)
        non_priority_msg = f'{region_code} Неприоритетные технологии {formatted}\n\n'

        # LTE1800
        lte1800_bool = True
        count_1800 = 0
        lte1800_bs = set()
        for bs_name, i in unique_bs.items():
            if i[10] == 'N' and bs_name not in lte1800_bs:
                if lte1800_bool:
                    non_priority_msg += f'Недоступно LTE1800:\n'
                    lte1800_bool = False
                count_1800 += 1
                lte1800_bs.add(bs_name)
                non_priority_msg += f'{count_1800}) {bs_name}\n'

        # 3G/WCDMA
        wcdma_bool = True
        count_3g = 0
        wcdma_bs = set()
        for bs_name, i in unique_bs.items():
            if i[9] == 'N' and bs_name not in wcdma_bs:
                if wcdma_bool:
                    non_priority_msg += f'Недоступно 3G:\n'
                    wcdma_bool = False
                count_3g += 1
                wcdma_bs.add(bs_name)
                non_priority_msg += f'{count_3g}) {bs_name}\n'

        # LTE800
        lte800_bool = True
        count_800 = 0
        lte800_bs = set()
        for bs_name, i in unique_bs.items():
            if i[11] == 'N' and bs_name not in lte800_bs:
                if lte800_bool:
                    non_priority_msg += f'Недоступно LTE800:\n'
                    lte800_bool = False
                count_800 += 1
                lte800_bs.add(bs_name)
                non_priority_msg += f'{count_800}) {bs_name}\n'

        # LTE2600
        lte2600_bool = True
        count_2600 = 0
        lte2600_bs = set()
        for bs_name, i in unique_bs.items():
            if i[12] == 'N' and bs_name not in lte2600_bs:
                if lte2600_bool:
                    non_priority_msg += f'Недоступно LTE2600:\n'
                    lte2600_bool = False
                count_2600 += 1
                lte2600_bs.add(bs_name)
                non_priority_msg += f'{count_2600}) {bs_name}\n'

        # LTE2100
        lte2100_bool = True
        count_2100 = 0
        lte2100_bs = set()
        for bs_name, i in unique_bs.items():
            if i[14] == 'N' and bs_name not in lte2100_bs:
                if lte2100_bool:
                    non_priority_msg += f'Недоступно LTE2100:\n'
                    lte2100_bool = False
                count_2100 += 1
                lte2100_bs.add(bs_name)
                non_priority_msg += f'{count_2100}) {bs_name}\n'

        # LTE2300 (с проверкой исключений)
        excluded_regions = ['ROS', 'STV', 'KRA', 'VLG', 'CNT', 'NEA', 'NWS', 'SEA', 'SWS']
        if region_code not in excluded_regions:
            lte2300_bool = True
            count_2300 = 0
            lte2300_bs = set()
            for bs_name, i in unique_bs.items():
                if i[13] == 'N' and bs_name not in lte2300_bs:
                    if lte2300_bool:
                        non_priority_msg += f'Недоступно LTE2300:\n'
                        lte2300_bool = False
                    count_2300 += 1
                    lte2300_bs.add(bs_name)
                    non_priority_msg += f'{count_2300}) {bs_name}\n'

        return {
            'success': True,
            'region_code': region_code,
            'region_name': REGION_INFO.get(region_code, {}).get('name', region_code),
            'base_layer': base_layer_msg,
            'non_priority': non_priority_msg,
            'timestamp': current.strftime("%H:%M:%S"),
            'stats': {
                'total_bs': len(unique_bs),
                'base_layer_count': count,
                'power_problems': power_count,
                'non_priority_percentage': 100 - int((count / len(unique_bs) * 100)) if len(unique_bs) > 0 else 0
            }
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'region_code': region_code,
            'region_name': REGION_INFO.get(region_code, {}).get('name', region_code),
            'timestamp': datetime.now().strftime("%H:%M:%S")
        }


def get_mock_region_data(region_code):
    """Генерация тестовых данных"""
    # Генерация реалистичных данных
    total_bs = random.randint(50, 150)
    base_layer_count = int(total_bs * random.uniform(0.85, 0.95))
    base_layer_percentage = int((base_layer_count / total_bs) * 100)
    power_problems = random.randint(0, 10)

    current = datetime.now()
    formatted = current.strftime("%d.%m.%Y %H:%M")

    # Генерация сообщения базового слоя
    base_layer_msg = f'{region_code} Базовый слой {formatted}\n\n'
    for i in range(1, 6):
        base_layer_msg += f'{i}) BS_{region_code}_{i:03d} LTE800\n'
        base_layer_msg += f'Power Да; Посещение Да; WO Нет\n'

    base_layer_msg += f'\nВсего активных POWER на сети: {power_problems}\n'
    base_layer_msg += f'Всего BS: {total_bs}\n'
    base_layer_msg += f'Базовый слой: {base_layer_count}/{total_bs} ({base_layer_percentage}%)\n'

    # Генерация сообщения технологий
    non_priority_msg = f'{region_code} Технологии {formatted}\n\n'

    technologies = [
        ('LTE1800', random.randint(0, 5)),
        ('3G/WCDMA', random.randint(0, 3)),
        ('LTE800', random.randint(0, 2)),
        ('LTE2600', random.randint(0, 4)),
        ('LTE2100', random.randint(0, 6))
    ]

    for tech, count in technologies:
        if count > 0:
            non_priority_msg += f'Недоступно {tech}:\n'
            for j in range(1, count + 1):
                non_priority_msg += f'{j}) BS_{region_code}_{j:03d}\n'

    if all(count == 0 for _, count in technologies):
        non_priority_msg += '✅ Все технологии доступны\n'

    return {
        'success': True,
        'region_code': region_code,
        'region_name': REGION_INFO.get(region_code, {}).get('name', region_code),
        'base_layer': base_layer_msg,
        'non_priority': non_priority_msg,
        'timestamp': current.strftime("%H:%M:%S"),
        'is_mock': True,
        'stats': {
            'total_bs': total_bs,
            'base_layer_count': base_layer_count,
            'power_problems': power_problems,
            'non_priority_percentage': 100 - base_layer_percentage
        }
    }


def extract_stats_from_data(data):
    """Извлечь статистику из данных региона"""
    # Используем данные из stats, если они есть
    if 'stats' in data:
        stats = data['stats']
        return {
            'base_layer_count': stats.get('base_layer_count', 0),
            'total_bs_count': stats.get('total_bs', 0),
            'power_problems': stats.get('power_problems', 0),
            'non_priority_percentage': stats.get('non_priority_percentage', 0)
        }

    # Или парсим из текста
    base_layer_text = data.get('base_layer', '')

    total_bs = 0
    base_layer_count = 0
    power_problems = 0

    # Ищем "Всего BS: X"
    total_match = re.search(r'Всего BS:\s*(\d+)', base_layer_text)
    if total_match:
        total_bs = int(total_match.group(1))

    # Ищем "Базовый слой: X/Y"
    base_match = re.search(r'Базовый слой:\s*(\d+)/(\d+)', base_layer_text)
    if base_match:
        base_layer_count = int(base_match.group(1))
        if not total_bs:
            total_bs = int(base_match.group(2))

    # Ищем "Всего активных POWER на сети: X"
    power_match = re.search(r'Всего активных POWER на сети:\s*(\d+)', base_layer_text)
    if power_match:
        power_problems = int(power_match.group(1))

    # Рассчитываем процент
    non_priority_percentage = 100 - int((base_layer_count / total_bs * 100)) if total_bs > 0 else 0

    return {
        'base_layer_count': base_layer_count,
        'total_bs_count': total_bs,
        'power_problems': power_problems,
        'non_priority_percentage': non_priority_percentage
    }


@app.route('/api/test', methods=['GET'])
def test():
    """Тестовый endpoint"""
    return jsonify({
        'success': True,
        'message': 'API работает!',
        'timestamp': datetime.now().strftime("%H:%M:%S")
    })


@app.route('/api/test-db', methods=['GET'])
def test_db():
    """Тест подключения к БД"""
    conn = get_db_connection()
    if conn:
        conn.close()
        return jsonify({
            'success': True,
            'message': f'БД доступна на {DB_CONFIG["host"]}:{DB_CONFIG["port"]}',
            'timestamp': datetime.now().strftime("%H:%M:%S")
        })
    else:
        return jsonify({
            'success': False,
            'error': f'Не удалось подключиться к БД {DB_CONFIG["host"]}:{DB_CONFIG["port"]}',
            'timestamp': datetime.now().strftime("%H:%M:%S")
        })


@app.route('/api/region/<region_code>', methods=['GET'])
def get_region_data(region_code):
    """Получить данные региона"""
    print(f"📥 Запрос данных для региона: {region_code}")

    # Пытаемся получить реальные данные
    real_data = get_real_region_data(region_code)

    # Если не удалось, используем тестовые данные
    if not real_data['success']:
        print(f"⚠️ Используем тестовые данные для региона: {region_code}")
        real_data = get_mock_region_data(region_code)

    # Извлекаем статистику для сохранения в историю
    stats = extract_stats_from_data(real_data)

    # Сохраняем в историю, если прошло больше 10 минут с последнего сохранения
    latest = get_latest_data(region_code)
    should_save = True

    if latest:
        last_time = datetime.strptime(latest['timestamp'], '%Y-%m-%d %H:%M:%S')
        time_diff = datetime.now() - last_time
        if time_diff < timedelta(minutes=10):
            should_save = False
            print(f"⏰ Пропускаем сохранение, прошло только {time_diff.seconds // 60} минут")

    if should_save:
        save_to_history(region_code, stats)

    return jsonify(real_data)


@app.route('/api/region/<region_code>/history', methods=['GET'])
def get_region_history(region_code):
    """Получить историю данных региона"""
    hours = request.args.get('hours', default=24, type=int)

    history = get_history(region_code, hours)

    if not history:
        # Если истории нет, генерируем тестовые данные
        history = []
        now = datetime.now()
        for i in range(24):
            time = now - timedelta(hours=i)
            history.append({
                'region_code': region_code,
                'base_layer_count': random.randint(40, 60),
                'total_bs_count': random.randint(50, 70),
                'power_problems': random.randint(0, 5),
                'non_priority_percentage': random.randint(5, 15),
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'base_layer_percentage': random.randint(85, 95)
            })

    return jsonify({
        'success': True,
        'region_code': region_code,
        'history': history,
        'count': len(history),
        'timestamp': datetime.now().strftime("%H:%M:%S")
    })


@app.route('/api/region/<region_code>/refresh', methods=['POST'])
def refresh_region_data(region_code):
    """Принудительно обновить данные региона"""
    print(f"🔄 Принудительное обновление данных для региона: {region_code}")

    # Получаем свежие данные
    real_data = get_real_region_data(region_code)

    if not real_data['success']:
        real_data = get_mock_region_data(region_code)

    # Всегда сохраняем при принудительном обновлении
    stats = extract_stats_from_data(real_data)
    save_to_history(region_code, stats)

    # Добавляем флаг, что это принудительное обновление
    real_data['forced_refresh'] = True
    real_data['refresh_timestamp'] = datetime.now().strftime("%H:%M:%S")

    return jsonify(real_data)


@app.route('/api/regions', methods=['GET'])
def get_regions_list():
    """Получить список всех регионов"""
    regions_list = []
    for code, info in REGION_INFO.items():
        regions_list.append({
            'code': code,
            'name': info['name'],
            'macroregion': info['mr']
        })

    return jsonify({
        'success': True,
        'regions': regions_list,
        'count': len(regions_list),
        'timestamp': datetime.now().strftime("%H:%M:%S")
    })


# Инициализируем БД истории при запуске
init_history_db()

if __name__ == '__main__':
    print("🚀 API сервер запускается...")
    print(f"📊 Конфигурация БД: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"📁 База истории: {HISTORY_DB}")
    print("📡 Доступные endpoints:")
    print("   - GET /api/test - тест сервера")
    print("   - GET /api/test-db - тест подключения к БД")
    print("   - GET /api/region/<код> - данные региона")
    print("   - GET /api/region/<код>/history - история региона")
    print("   - POST /api/region/<код>/refresh - принудительное обновление")
    print("   - GET /api/regions - список всех регионов")

    app.run(host='0.0.0.0', port=5000, debug=True)