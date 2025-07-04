import os
import random
import sqlite3
import logging
from threading import Lock
from datetime import datetime, timedelta
from dotenv import load_dotenv
import telebot
from telebot import types
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import requests

# ===== НАСТРОЙКА ЛОГИРОВАНИЯ =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ===== КОНСТАНТЫ =====
WEDDING_DATE = "2025-07-10"
TIMEZONE = "Europe/Moscow"
ADMINS = [969123149, 1317385378]
MAX_CONCURRENT_USERS = 50
DB_TIMEOUT = 30

# Emoji для рейтинга настроения
EMOJI_MAP = ["😢", "🙁", "😐", "🙂", "😍"]

# ===== СЛОВАРИ ДАННЫХ =====
DATE_IDEAS = {
        # Ваш существующий словарь с идеями...
        # Рестораны и кафе
        "Ужин в ресторане 'Терраса'": {
            "desc": "Панорамный вид на Северную Двину, кухня северных народов",
            "url": "https://terrasa29.ru",
            "season": "круглый год"
        },
        "Дегустация в 'Поморском кафе'": {
            "desc": "Попробуйте тройчатку, козули и другие поморские деликатесы",
            "url": "https://vk.com/pomorskoe_cafe",
            "season": "круглый год"
        },
        "Ужин в 'Roomi'": {
            "desc": "Здесь вы можете попробовать блюда северной кухни, такие как уха на сушёной рыбе, оленина на шишках, треска с картофельным пюре и малосольными огурцами, а также десерты, такие как «Хлеб и соль» и северные десерты с ягелем, белым грибом и бородинским хлебом.",
            "url": "https://roomi.one/roomirestaurant",
            "season": "круглый год"
        },
        "Ужин в 'Анров'": {
            "desc": "Гостям нравится местная кухня, особенно пельмени из щуки с бульоном из белых грибов, палтус в икорном соусе, треска с муссом из цветной капусты, а также десерты, такие как черемуховое пирожное с чаем из брусники, ягод морошки, шишек и трав.",
            "url": "https://anrov.ru",
            "season": "круглый год"
        },
        "Ужин в 'El Fuego'": {
            "desc": "Ресторан El Fuego специализируется на аргентинской кухне, но также предлагает блюда поморской кухни. ",
            "url": "https://vk.com/elfuegorestaurant",
            "season": "круглый год"
        },
        "Ужин в 'Inside'": {
            "desc": "В меню представлены авторские блюда европейской кухни, изысканные десерты, крабы из меню «Аквариум», а также богатая винная карта. ",
            "url": "https://inside-rest.ru",
            "season": "круглый год"
        },
         "Ужин в 'Старый Тифлис'": {
            "desc": "Гости рекомендуют попробовать рулетики из баклажанов с сыром и чесноком, хачапури по-мегрельски, хинкали с бараниной и говядиной, жареный сулугуни и долму",
            "url": "https://vk.com/s_tiflis",
            "season": "круглый год"
        },
        "Ужин в 'Престо'": {
            "desc": "По словам посетителей, здесь готовят очень вкусную пиццу, роллы и суши, а также сырный крем-суп, карамелизированные баклажаны и телячьи щечки.",
            "url": "https://vk.com/presto",
            "season": "круглый год"
        },
        "Ужин в 'Старе Место'": {
            "desc": "«Старе Место» — это ресторан, стилизованный под чешскую пивную.",
            "url": "https://vk.com/presto",
            "season": "круглый год"
        },
        "Ужин в 'Старе Место'": {
            "desc": "«Старе Место» — это ресторан, стилизованный под чешскую пивную.",
            "url": "https://vk.com/presto",
            "season": "круглый год"
        },
        "Выпить кофе в '1234'": {
            "desc": "Меню разнообразное и вкусное, каждый найдет что-то себе по душе. Блюда приготовлены с душой, а порции щедрые. Особенное внимание заслуживает десертная карта — настоящие шедевры. ",
            "url": "https://vk.com/coffee_na_1234",
            "season": "круглый год"
        },
        "Выпить кофе в 'АндерСон'": {
            "desc": "Кафе «АндерСон» — это уютное семейное заведение, где можно не только вкусно поесть, но и насладиться прекрасной домашней атмосферой.",
            "url": "https://anderson29.ru",
            "season": "круглый год"
        },
        "Выпить кофе в 'ПиццаФабрика'": {
            "desc": "Ресторан «ПиццаФабрика» — это идеальное место для семейного отдыха или дружеских встреч. Здесь вы можете насладиться вкусной и свежей пиццей, а также другими блюдами, такими как салаты, супы, закуски и горячие блюда.",
            "url": "https://pizzafabrika.ru",
            "season": "круглый год"
        },
        # Активный отдых
        "Катание на хаски в 'Сугробе'": {
            "desc": "Питомник ездовых собак в 30 км от города",
            "url": "https://sugrob29.ru",
            "season": "декабрь-март"
        },
        "Экскурсия  на квадроциклах": {
            "desc": "Экскурсия по лесным тропам с обедом у костра",
            "url": "https://vk.com/quadro29",
            "season": "май-октябрь"
        },
        "Невероятная рыбалка на Белом море": {
            "desc": "Готовые программы от нескольких часов до нескольких дней возможны на различных типах яхт, скоростные и парусные, для большой компании или групповой рыбалки, для семейного и индивидуального отдыха.",
            "url": "https://yacht29.ru/fishing.html",
            "season": "круглый год"
        },
        "Тайники севера": {
            "desc": "Провести время с друзьями и любимыми в дали от города и суеты, на едите с природой, что может быть лучше? ",
            "url": "https://vk.com/tainik29",
            "season": "круглый год"
        },
        "Романтическая ночная прогулка ": {
            "desc": "Маршрут пролегает по западному рукаву Северной Двины – Никольскому. Вы пройдете по живописным протокам исторического фарватера обширной дельты реки, полюбуетесь пейзажами многочисленных островов и захватывающей панорамой города над Двиной. ",
            "url": "https://bulatova.travel/catalogs/1/sections/11/products/872",
            "season": "круглый год"
        },
        "Полет на параплане ": {
            "desc": "Полет на параплане может добавить экстрима в ваш отдых. Удивительная возможность взглянуть на мир с высоты полета. ",
            "url": "https://vk.com/paraplan29vel/catalogs/1/sections/11/products/872",
            "season": "круглый год"
        },
        "Конная прогулка": {
            "desc": "Еще один способ классно провести время на природе, и забыть что такое суета - это конная прогулка ",
            "url": "https://vk.com/countryclub2016",
            "season": "круглый год"
        },
        "Гильдия квестов": {
            "desc": "Здесь можно найти квесты по всем вашим потребностям, от интеллектуальных до страшных. Игрокам предстоит пройти лабиринт и найти сокровища. Это испытание на креативность, смелость и командную работу. ",
            "url": "https://arx.questguild.ru",
            "season": "круглый год"
        },


        # Культурные
        "Ночь в музее Малые Корелы": {
            "desc": "Вечерние экскурсии при свечах по деревянным церквям",
            "url": "https://korely.ru",
            "season": "июнь-август"
        },
        "Мастер-класс по козулям": {
            "desc": "Роспись традиционных пряников в музее 'Архангельский пряник'",
            "url": "https://arhmuseum.ru",
            "season": "круглый год"
        },
        "Архангельский театр драмы": {
            "desc": "Именно здесь культура перекликается с искусством",
            "url": "https://arhdrama.culture29.ru",
            "season": "круглый год"
        },
        "Историко-архитектурный комплекс «Архангельские Гостиные дворы»": {
            "desc": "Это один из первых краевых музеев страны. По богатству, музейный фонд историко-архитектурного комплекса насчитывает почти 300 тысяч экспонатов, что делает комплекс крупнейшим по мощи коллекции и одним из самых привлекательных для историков и краеведов. ",
            "url": "https://kraeved29.ru",
            "season": "круглый год"
        },
        # Необычные
        "Ночь в глэмпинге 'Северное сияние'": {
            "desc": "Прозрачные купола с подогревом в 50 км от города",
            "url": "https://glamping29.ru",
            "season": "сентябрь-апрель"
        },
        "Фотосессия у маяка Пур-Наволок": {
            "desc": "Самый северный маяк России с потрясающими видами",
            "url": None,
            "season": "круглый год"
        },
        "Ледовая арена в ТРЦ ТитанАрена": {
            "desc": "Отличная возможность провести время со второй половинкой. На арене ровный лед, большая площадь, есть возможность аренды коньков.",
            "url": "http://titanarena.ru/icearena/",
            "season": "круглый год"
        },
         "Гончарная мастерская АртКерамика": {
            "desc": "Индивидуальный 2-х часовой мастер-класс для пары от мастера в романтической обстановке. Сделанное вами изделие обожгут и окрасят, а у вас будет рукотворный символ вашей любви.",
            "url": "https://vk.com/market/product/svidanie-za-goncharnym-krugom-master-klass-dlya-pary-168852802-5704634?utm_act=show&utm_dmcah=&utm_hash=&utm_id=5704634&utm_is_znav=1&utm_loc=uslugi-168852802&utm_location_owner_id=-168852802&utm_oid=-168852802&utm_query=%7B%26quot%3Bsection%26quot%3B%3A%26quot%3Bsection%26quot%3B%2C%26quot%3Bsection_id%26quot%3B%3A%26quot%3BHUkaVBkFWVZxRwcDWVg2%26quot%3B%7D&utm_ref=",
            "season": "круглый год"
        },
        "Спа центр Sultan Spa": {
            "desc": "Спа центр Sultan Spa - здесь вы не только приятно проведете время вместе, но и проведете его с пользой. В спа центре имеется множество программ под каждый ваш запрос.",
            "url": "https://sultanspa.tilda.ws/dates",
            "season": "круглый год"
        },
        # Загородные
        "Тур на Соловки на выходные": {
            "desc": "Перелет на самолете из Архангельска (1 час в пути)",
            "url": "https://solovki29.ru",
            "season": "июнь-сентябрь"
        },
        "Рыбалка на озере Лача": {
            "desc": "Аренда домика с баней и снастями",
            "url": "https://vk.com/lacha_fishing",
            "season": "круглый год"
        }

}

COMPLIMENTS = [
    "Ты — моя радость!", "С тобой каждый день — праздник!","Ты превращаешь обычные моменты в волшебные","Каждый день с тобой — как маленькое чудо"," Твои глаза — как две вселенных, в которых я хочу потеряться","Спасибо, что ты есть. Ты делаешь мою жизнь ярче и теплее","Ты умеешь поддержать так, как никто другой","Мне нравится, как ты заботишься обо мне, даже в мелочах","Ты — мой самый надёжный человек, моя тихая гавань","Ты — человек, ради которого хочется становиться лучше","Рядом с тобой даже тишина становится комфортной","Ты — тот человек, рядом с которым я забываю, что такое одиночество","Твоя улыбка — мой самый любимый вид счастья","Ты затмеваешь солнце, когда появляешься в комнате","Даже спустя годы ты заставляешь мое сердце биться чаще","Ты — мой личный антистресс","С тобой я чувствую себя в безопасности, как ни с кем другим"
]

TRUTHS = [
     "Какое твое самое неловкое воспоминание о нас?",
    "Что тебе больше всего во мне нравится?",
    "О чем ты мечтал(а) в детстве?",
    "Какой наш момент был самым романтичным?",
    "Был(а) ли ты влюблен(а) в кого-то из моих друзей?",
    "Какой мой недостаток тебя раздражает?",
    "Если бы мы могли поехать в любое место, куда бы ты выбрал(а)?",
    "Что ты впервые подумал(а) обо мне при встрече?",
    "Какой секрет ты мне никогда не рассказывал(а)?",
    "Что бы ты изменил(а) в наших отношениях?",
    "Ты ревнуешь меня к кому-то? К кому именно?",
    "Какой твой самый постыдный поступок?",
    "Было ли у тебя предчувствие, что мы будем вместе?",
    "Какой момент в наших отношениях ты хотел(а) бы пережить снова?",
    "Что тебя во мне бесит, но ты терпишь?",
    "Если бы ты мог(ла) изменить одну мою привычку, какую бы выбрал(а)?",
    "О чем ты чаще всего лжешь мне?",
    "Какой твой самый странный фетиш?",
    "Был(а) ли ты в отношениях с кем-то только из-за внешности?",
    "Что самое безумное, что ты делал(а) ради любви?",
    "Ты когда-нибудь проверял(а) мой телефон?",
    "Какой комплимент тебе запомнился больше всего?",
    "Ты когда-нибудь представлял(а) нас через 10 лет? Как мы выглядим?",
    "Что самое глупое, что ты делал(а), чтобы привлечь мое внимание?",
    "Какой твой любимый момент нашей интимной близости?",
    "Если бы у тебя был один день без обязательств, что бы ты сделал(а)?",
    "Ты когда-нибудь плакал(а) из-за меня?",
    "Что самое рискованное, что ты делал(а) в отношениях?",
    "Какой фильм или сериал напоминает тебе наши отношения?",
    "Ты когда-нибудь хотел(а) расстаться со мной? Почему?",
    "Какой поступок ты никогда мне не простишь?",
    "Что ты скрываешь от меня прямо сейчас?",
    "Если бы ты мог(ла) узнать правду об одном событии в моей жизни, что бы это было?",
    "Ты когда-нибудь флиртовал(а) с кем-то, пока мы вместе?",
    "Что самое странное, что ты находил(а) во мне привлекательным?",
    "Какой твой самый большой страх в наших отношениях?",
    "Ты когда-нибудь говорил(а) 'Я тебя люблю' неискренне?",
    "Что бы ты сделал(а), если бы я предложил(а) тебе секс в общественном месте?",
    "Какой момент в наших отношениях был для тебя самым трудным?"
]

DARES = [
    "Спой куплет любимой песни партнера голосовым сообщением!",
    "Напиши комплимент, который начинается на каждую букву имени партнера",
    "Станцуй под первую песню, которую найдешь в плейлисте",
    "Пришли фото, где тебе меньше всего лет",
    "Покажи самое смешное фото в своем телефоне",
    "Сделай массаж партнеру в течение 3 минут",
    "Изобрази известную личность, пока партнер не угадает",
    "Напиши любовное стихотворение с тремя словами, которые скажет партнер",
    "Съешь что-то острое без воды и не морщись",
    "Сними видео, как ты пытаешься сесть на шпагат",
    "Пришли голосовое с самым соблазнительным голосом",
    "Сделай смешное селфи с необычным выражением лица",
    "Покажи самую странную вещь в твоей комнате",
    "Съешь ложку чего-то (кетчуп, горчица) без ничего",
    "Спой детскую песенку с серьезным выражением лица",
    "Станцуй танец маленьких утят и пришли видео",
    "Нарисуй портрет партнера с закрытыми глазами",
    "Сделай 10 отжиманий, если не сможешь - 20 приседаний",
    "Позвони партнеру и прокукарекай в трубку",
    "Изобрази 5 эмоций подряд, которые скажет партнер",
    "Съешь что-нибудь с закрытыми глазами, что даст тебе партнер",
    "Спой любовную песню, зажав нос пальцами",
    "Пришли последний смайлик в своем телефоне и объясни, почему он там",
    "Сними видео, как ты пытаешься лизнуть свой локоть",
    "Напиши сообщение партнеру только с помощью стикеров",
    "Сделай вид, что ты ведущий ток-шоу и интервьюируй партнера 2 минуты",
    "Покажи свою самую неудачную фотографию",
    "Изобрази статую любви и стой неподвижно 1 минуту",
    "Съешь банан или клубнику самым соблазнительным способом",
    "Пришли скриншот своей последней покупки в интернете",
    "Сделай пародию на известного актера/певицу",
    "Опиши партнера тремя словами, не используя стандартные комплименты",
    "Сними видео, как ты наносишь макияж одной рукой",
    "Покажи, как ты выглядишь сразу после пробуждения",
    "Съешь что-то не смешивая вкусы (например, шоколад с горчицей)",
    "Спой песню, заменяя все слова названием фруктов",
    "Станцуй медленный танец с воображаемым партнером",
    "Пришли фото своей самой странной позы для сна",
    "Сними видео, как ты пытаешься коснуться языком носа",
    "Напиши признание в любви, используя только эмодзи"
]
# ===== БЛОКИРОВКИ И СОСТОЯНИЯ =====
db_lock = Lock()
user_states = {}
state_lock = Lock()

# ===== ИНИЦИАЛИЗАЦИЯ БОТА =====
load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TOKEN:
    raise ValueError("Токен не найден в .env-файле!")

bot = telebot.TeleBot(TOKEN, threaded=True, num_threads=10)

# ===== УЛУЧШЕННОЕ ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ =====
def get_db_connection():
    """Потокобезопасное подключение к SQLite с таймаутом"""
    return sqlite3.connect(
        'wedding_bot.db',
        timeout=DB_TIMEOUT,
        check_same_thread=False,
        isolation_level=None
    )

# ===== ОПТИМИЗИРОВАННАЯ ИНИЦИАЛИЗАЦИЯ БД =====
def init_db():
    """Инициализация базы данных с индексами и настройками"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Включение WAL режима для лучшей параллельной работы
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-10000")  # 10MB кэша
        
        # Таблица поздравлений с индексом
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS congratulations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_name TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        cursor.execute('CREATE INDEX IF NOT EXISTS congrats_user_idx ON congratulations(user_id)')
        
        # Таблица настроений с индексом
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS moods (
            user_id INTEGER NOT NULL,
            score INTEGER CHECK(score BETWEEN 1 AND 5),
            note TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        cursor.execute('CREATE INDEX IF NOT EXISTS moods_user_idx ON moods(user_id)')
        
        # Таблица капсул времени с индексом
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS timecapsules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            send_at DATETIME NOT NULL,
            is_sent INTEGER DEFAULT 0,
            chat_id INTEGER NOT NULL
        )''')
        cursor.execute('CREATE INDEX IF NOT EXISTS capsules_user_idx ON timecapsules(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS capsules_sent_idx ON timecapsules(is_sent)')
        
        # Таблица желаний с индексом
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS wishes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            wish TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        cursor.execute('CREATE INDEX IF NOT EXISTS wishes_user_idx ON wishes(user_id)')
        
        conn.commit()
        logger.info("База данных успешно инициализирована")
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}")
        raise
    finally:
        if conn:
            conn.close()

# ===== ОПТИМИЗИРОВАННЫЕ ФУНКЦИИ БАЗЫ ДАННЫХ =====
def safe_db_execute(query, params=(), fetch=False):
    """Безопасное выполнение SQL-запросов с блокировкой"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        with db_lock:
            cursor.execute(query, params)
            if fetch:
                result = cursor.fetchall()
                conn.commit()
                return result
            conn.commit()
    except Exception as e:
        logger.error(f"Ошибка выполнения запроса: {e}\nQuery: {query}\nParams: {params}")
        if fetch:
            return []
        raise
    finally:
        if conn:
            conn.close()

# ===== УПРАВЛЕНИЕ СОСТОЯНИЯМИ =====
def set_user_state(user_id, state_data):
    """Потокобезопасное сохранение состояния пользователя"""
    with state_lock:
        user_states[user_id] = state_data

def get_user_state(user_id):
    """Потокобезопасное получение состояния пользователя"""
    with state_lock:
        return user_states.get(user_id)
# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
def get_plural(number, one, few, many):
    """Склонение слов в зависимости от числа"""
    if number % 10 == 1 and number % 100 != 11:
        return one
    elif 2 <= number % 10 <= 4 and (number % 100 < 10 or number % 100 >= 20):
        return few
    else:
        return many

def get_random_photo():
    """Получение случайного фото из папки"""
    photo_dir = "photos"
    if os.path.exists(photo_dir):
        photos = [f for f in os.listdir(photo_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
        if photos:
            return os.path.join(photo_dir, random.choice(photos))
    return None

def fetch_cocktail(cocktail_name=None):
    """Получение данных о коктейле из API"""
    try:
        url = (f"https://www.thecocktaildb.com/api/json/v1/1/search.php?s={cocktail_name}"
              if cocktail_name else "https://www.thecocktaildb.com/api/json/v1/1/random.php")
        response = requests.get(url)
        data = response.json()
        return data['drinks'][0] if data.get('drinks') else None
    except Exception as e:
        logging.error(f"Cocktail API error: {str(e)}")
        return None
# ===== ОБРАБОТЧИКИ КОМАНД =====
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = """
💖 <b>Добро пожаловать в LoveBot!</b> 💖
Я ваш персональный помощник в сердечных делах.
Напишите <b>/help</b> чтобы увидеть все возможности.
"""
    try:
        with open("images/1.jpg", "rb") as photo:
            bot.send_photo(message.chat.id, photo, caption=welcome_text, parse_mode="HTML")
    except:
        bot.send_message(message.chat.id, welcome_text, parse_mode="HTML")


@bot.message_handler(commands=['help'])
def send_help(message):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("💑 Романтика", callback_data="help_romance"),
        types.InlineKeyboardButton("🎲 Развлечения", callback_data="help_fun"),
        types.InlineKeyboardButton("📊 Утилиты", callback_data="help_utils"),
        types.InlineKeyboardButton("🍹 Коктейли", callback_data="help_cocktails")
    ]
    keyboard.add(*buttons)
    
    bot.send_message(
        message.chat.id,
        "🌟 <b>Главное меню помощника</b>\nВыберите категорию:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# Сокращенные тексты для каждого раздела
HELP_TEXTS = {
    "romance": """
<b>💑 Романтические команды</b>
/date - Идея для свидания
/love - Случайный комплимент
/anniversary - Годовщина свадьбы
/memory - Случайное совместное фото
/wishlist - Список желаний 
/timecapsule - Капсула времени
""",
    "fun": """
<b>🎲 Развлекательные команды:</b>
/truth_or_dare - Игра
/dispute - Решить спор
""",
    "utils": """
<b>📊 Полезные утилиты</b>
/mood - Отметить настроение
/mood_stats - Статистика настроения
/congratulate - Добавить поздравление
/congrats - Прочитать поздравления
/export_db - Скачать базу данных с поздравлениями
""",
    "cocktails": """
<b>🍹 Коктейльные команды</b>
/drink - Случайный рецепт коктейля
/cocktail [название] - Поиск коктейля
Пример: <code>/cocktail mojito</code>
"""
}

@bot.callback_query_handler(func=lambda call: call.data.startswith('help_'))
def show_help_category(call):
    category = call.data.split('_')[1]
    text = HELP_TEXTS.get(category, "Раздел не найден")
    
    try:
        # Просто редактируем сообщение с новым текстом
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            parse_mode="HTML"
        )
        # Короткий подтверждающий ответ
        bot.answer_callback_query(call.id)
    except Exception as e:
        # В случае ошибки просто отвечаем без текста
        bot.answer_callback_query(call.id)
        print(f"Ошибка при показе категории: {e}")



@bot.message_handler(commands=['date'])
def send_date_idea(message):
    ideas = random.sample(list(DATE_IDEAS.items()), 5)
    response = "💡 <b>Топ-5 идей для свидания:</b>\n\n"
    
    for i, (idea, details) in enumerate(ideas, 1):
        link = f"\n🔗 <a href='{details['url']}'>Подробнее</a>" if details['url'] else ""
        response += (f"{i}. <b>{idea}</b>\n"
                    f"   {details['desc']}\n"
                    f"   🗓️ {details['season']}{link}\n\n")
    
    bot.send_message(message.chat.id, response, parse_mode='HTML', 
                    disable_web_page_preview=True)

@bot.message_handler(commands=['love'])
def send_compliment(message):
    bot.send_message(message.chat.id, random.choice(COMPLIMENTS))

@bot.message_handler(commands=['memory'])
def send_random_photo(message):
    photo_path = get_random_photo()
    if photo_path:
        with open(photo_path, 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption="Вот ваше случайное воспоминание ❤️")
    else:
        bot.send_message(message.chat.id, "Фото не найдены 😢 Добавьте их в папку /photos")

@bot.message_handler(commands=['anniversary'])
def wedding_anniversary(message):
    now = datetime.now(pytz.timezone(TIMEZONE))
    wedding_day = datetime.strptime(WEDDING_DATE, "%Y-%m-%d").replace(tzinfo=pytz.timezone(TIMEZONE))
    delta = now - wedding_day
    
    years = delta.days // 365
    months = (delta.days % 365) // 30
    days = delta.days
    hours = delta.seconds // 3600
    
    anniversary_text = (f"💍 Ваша свадьба была {wedding_day.strftime('%d.%m.%Y')}\n"
                      f"⏳ С тех пор прошло:\n"
                      f"• {years} {get_plural(years, 'год', 'года', 'лет')}\n"
                      f"• {months} {get_plural(months, 'месяц', 'месяца', 'месяцев')}\n"
                      f"• {days} {get_plural(days, 'день', 'дня', 'дней')}\n"
                      f"• {hours} {get_plural(hours, 'час', 'часа', 'часов')}\n\n"
                      f"Следующая годовщина через {365 - (delta.days % 365)} дней!")
    
    bot.send_message(message.chat.id, anniversary_text)


@bot.message_handler(commands=['congrats'])
def show_congrats(message):
    try:
        conn = sqlite3.connect('wedding_bot.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_name, message, timestamp FROM congratulations ORDER BY timestamp DESC LIMIT 50')
        congrats = cursor.fetchall()
        
        if congrats:
            response = "💌 Последние поздравления:\n\n" + "\n".join(
                [f"🏷️ {item[0]} ({item[2][:10]}):\n{item[1]}\n" for item in congrats])
            bot.send_message(message.chat.id, response)
        else:
            bot.send_message(message.chat.id, "Пока нет поздравлений 😢")
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Ошибка: {e}")
    finally:
        conn.close()

@bot.message_handler(commands=['mood'])
def ask_mood(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row("1 😢", "2 🙁", "3 😐")
    markup.row("4 🙂", "5 😍")
    msg = bot.send_message(message.chat.id, "Оцените ваше настроение сегодня:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_mood)

def process_mood(message):
    try:
        mood_map = {"1 😢":1, "2 🙁":2, "3 😐":3, "4 🙂":4, "5 😍":5}
        score = mood_map.get(message.text, 3)
        
        conn = sqlite3.connect('wedding_bot.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO moods (user_id, score) VALUES (?, ?)",
                      (message.from_user.id, score))
        conn.commit()
        
        reactions = {
            1: "Обнимаю вас 🤗 Может, чашечку чая?",
            2: "Надеюсь, день станет лучше 🌈",
            5: "Отлично! Поделитесь настроением с близкими 😊"
        }
        if score in reactions:
            bot.send_message(message.chat.id, reactions[score], reply_markup=types.ReplyKeyboardRemove())
        else:
            bot.send_message(message.chat.id, "Спасибо!", reply_markup=types.ReplyKeyboardRemove())
    except Exception as e:
        bot.reply_to(message, f"⚠️ Ошибка: {e}")
    finally:
        conn.close()

@bot.message_handler(commands=['mood_stats'])
def mood_stats(message):
    try:
        conn = sqlite3.connect('wedding_bot.db')
        cursor = conn.cursor()
        cursor.execute('''
        SELECT AVG(score), COUNT(*), SUM(CASE WHEN score < 3 THEN 1 ELSE 0 END) 
        FROM moods WHERE user_id = ? AND timestamp >= datetime('now', '-30 days')
        ''', (message.from_user.id,))
        
        avg_score, total_days, bad_days = cursor.fetchone()
        avg_score = avg_score or 0
        emoji_index = min(4, max(0, int(round(avg_score)) - 1))
        
        response = (f"📊 <b>Ваша эмоциональная статистика</b>\n\n"
                   f"Среднее настроение: {avg_score:.1f} {EMOJI_MAP[emoji_index]}\n"
                   f"Дней с оценкой: {total_days or 0}\n"
                   f"Сложных дней: {bad_days or 0}\n\n"
                   f"Используйте /mood для новой оценки")
        
        bot.send_message(message.chat.id, response, parse_mode='HTML')
    except Exception as e:
        bot.reply_to(message, f"⚠️ Ошибка: {e}")
    finally:
        conn.close()

@bot.message_handler(commands=['truth_or_dare'])
def truth_or_dare(message):
    markup = types.InlineKeyboardMarkup()
    btn_truth = types.InlineKeyboardButton("Правда", callback_data="truth")
    btn_dare = types.InlineKeyboardButton("Действие", callback_data="dare")
    markup.add(btn_truth, btn_dare)
    bot.send_message(message.chat.id, "Выбери: Правду или Действие? 😏", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["truth", "dare"])
def handle_truth_or_dare(call):
    response = random.choice(TRUTHS) if call.data == "truth" else random.choice(DARES)
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                         text=f"✨ Твое задание:\n\n{response}")

# 2. Функция просмотра желаний (должна быть объявлена перед обработчиками)
def show_wishes(chat_id, user_id, bot):
    try:
        conn = sqlite3.connect('wishlist.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT wish FROM wishes WHERE user_id=?", (user_id,))
        wishes = c.fetchall()
        
        if wishes:
            response = "🎁 Ваш список желаний:\n\n" + "\n".join([f"• {wish[0]}" for wish in wishes])
        else:
            response = "Ваш список желаний пока пуст."
            
        bot.send_message(chat_id, response)
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Ошибка: {str(e)}")
    finally:
        if conn:
            conn.close()

# 3. Функция обработки нового желания
def process_wish_step(message, user_id, bot):
    try:
        conn = sqlite3.connect('wishlist.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("INSERT INTO wishes (user_id, wish) VALUES (?, ?)", 
                 (user_id, message.text))
        conn.commit()
        bot.send_message(message.chat.id, "✅ Желание успешно добавлено!")
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Ошибка: {str(e)}")
    finally:
        if conn:
            conn.close()

# 4. Обработчик команды /wishlist
@bot.message_handler(commands=['wishlist'])
def handle_wishlist(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Добавить желание", callback_data="add_wish"))
    markup.add(types.InlineKeyboardButton("Показать мои желания", callback_data="show_wishes"))
    markup.add(types.InlineKeyboardButton("Очистить список", callback_data="clear_wishes"))
    
    bot.send_message(message.chat.id, 
                   "Выберите действие:", 
                   reply_markup=markup)

# 5. Обработчик кнопок
@bot.callback_query_handler(func=lambda call: True)
def handle_wishlist_actions(call):
    if call.data == "add_wish":
        msg = bot.send_message(call.message.chat.id, "📝 Введите ваше желание:")
        bot.register_next_step_handler(msg, process_wish_step, call.from_user.id, bot)
    elif call.data == "show_wishes":
        show_wishes(call.message.chat.id, call.from_user.id, bot)
    elif call.data == "clear_wishes":
        handle_clear_wishes(call)

# 6. Обработчик очистки списка
def handle_clear_wishes(call):
    try:
        conn = sqlite3.connect('wishlist.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("DELETE FROM wishes WHERE user_id=?", (call.from_user.id,))
        conn.commit()
        bot.answer_callback_query(call.id, "✅ Список желаний очищен!")
    except Exception as e:
        bot.answer_callback_query(call.id, f"⚠️ Ошибка: {str(e)}")
    finally:
        if conn:
            conn.close()


# Решение споров
@bot.message_handler(commands=['dispute'])
def solve_dispute(message):
    decision = random.choice(["Ты", "Твоя половинка"])
    bot.send_message(message.chat.id, f"Сегодня моет посуду: {decision} 🍽️")

@bot.message_handler(commands=['drink'])
def send_random_cocktail(message):
    cocktail = fetch_cocktail()
    if not cocktail:
        bot.reply_to(message, "🚫 Не удалось загрузить коктейль. Попробуйте позже!")
        return

    ingredients = "\n".join(
        f"• {cocktail[f'strIngredient{i}']} - {cocktail.get(f'strMeasure{i}', 'по вкусу')}"
        for i in range(1, 16) if cocktail.get(f'strIngredient{i}')
    )
    
    text = (f"🍹 <b>{cocktail['strDrink']}</b> ({cocktail['strAlcoholic']})\n"
           f"<i>Категория:</i> {cocktail['strCategory']}\n"
           f"<i>Стекло:</i> {cocktail['strGlass']}\n\n"
           f"<b>Ингредиенты:</b>\n{ingredients}\n\n"
           f"<b>Рецепт:</b>\n{cocktail['strInstructions']}")
    
    if cocktail.get('strDrinkThumb'):
        bot.send_photo(message.chat.id, cocktail['strDrinkThumb'], caption=text, parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, text, parse_mode="HTML")

@bot.message_handler(commands=['cocktail'])
def search_cocktail(message):
    try:
        cocktail_name = message.text.split(' ', 1)[1] if len(message.text.split()) > 1 else None
        
        if not cocktail_name:
            bot.reply_to(message, "ℹ️ Введите название, например: <code>/cocktail mojito</code>", parse_mode="HTML")
            return

        cocktail = fetch_cocktail(cocktail_name)
        if not cocktail:
            bot.reply_to(message, f"🔍 Коктейль '{cocktail_name}' не найден")
            return

        ingredients = "\n".join(
            f"• {cocktail[f'strIngredient{i}']} - {cocktail.get(f'strMeasure{i}', 'по вкусу')}"
            for i in range(1, 16) if cocktail.get(f'strIngredient{i}')
        )
        
        text = (f"🍹 <b>{cocktail['strDrink']}</b> ({cocktail['strAlcoholic']})\n"
               f"<i>Категория:</i> {cocktail['strCategory']}\n"
               f"<i>Стекло:</i> {cocktail['strGlass']}\n\n"
               f"<b>Ингредиенты:</b>\n{ingredients}\n\n"
               f"<b>Рецепт:</b>\n{cocktail['strInstructions']}")
        
        if cocktail.get('strDrinkThumb'):
            bot.send_photo(message.chat.id, cocktail['strDrinkThumb'], caption=text, parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, text, parse_mode="HTML")
            
    except IndexError:
        bot.reply_to(message, "ℹ️ Введите название после команды, например: <code>/cocktail mojito</code>", parse_mode="HTML")
    except Exception as e:
        logging.error(f"Error in search_cocktail: {str(e)}")
        bot.reply_to(message, "⚠️ Произошла ошибка при поиске коктейля")

@bot.message_handler(commands=['export_db'])
def export_db(message):
    if message.from_user.id in ADMINS:
        try:
            with open('wedding_bot.db', 'rb') as db_file:
                bot.send_document(message.chat.id, db_file)
        except Exception as e:
            bot.reply_to(message, f"⚠️ Ошибка экспорта: {e}")
    else:
        bot.reply_to(message, "🚫 Эта команда только для администраторов")

# ===== ОБРАБОТЧИКИ КОМАНД С УЧЕТОМ МНОГОПОЛЬЗОВАТЕЛЬСКОЙ РАБОТЫ =====
@bot.message_handler(commands=['congratulate'])
def start_congratulation(message):
    """Обработчик поздравлений с проверкой нагрузки"""
    try:
        if message.from_user.id in ADMINS:
            bot.reply_to(message, "Вы не можете поздравлять сами себя 😊")
            return
            
        # Проверка количества активных пользователей
        if len(user_states) > MAX_CONCURRENT_USERS * 0.8:
            bot.reply_to(message, "Сервер перегружен, попробуйте позже")
            return
            
        set_user_state(message.from_user.id, {'waiting_for_congratulation': True})
        msg = bot.reply_to(message, "Напишите ваше поздравление:")
        bot.register_next_step_handler(msg, process_congratulation)
    except Exception as e:
        logger.error(f"Ошибка в start_congratulation: {e}")
        bot.reply_to(message, "⚠️ Произошла ошибка, попробуйте позже")

def process_congratulation(message):
    """Обработка текста поздравления"""
    try:
        user_state = get_user_state(message.from_user.id)
        if not user_state or not user_state.get('waiting_for_congratulation'):
            bot.reply_to(message, "Сессия устарела, начните заново")
            return
            
        safe_db_execute(
            "INSERT INTO congratulations (user_id, user_name, message) VALUES (?, ?, ?)",
            (message.from_user.id, message.from_user.first_name, message.text)
        )
        bot.reply_to(message, "✅ Ваше поздравление сохранено!")
        set_user_state(message.from_user.id, None)
    except Exception as e:
        logger.error(f"Ошибка в process_congratulation: {e}")
        bot.reply_to(message, "⚠️ Ошибка сохранения, попробуйте позже")


# ===== ОПТИМИЗИРОВАННЫЙ ПЛАНИРОВЩИК КАПСУЛ ВРЕМЕНИ =====
scheduler = BackgroundScheduler({
    'apscheduler.job_defaults.max_instances': 100,
    'apscheduler.executors.default': {
        'class': 'apscheduler.executors.pool:ThreadPoolExecutor',
        'max_workers': 30
    }
})

def check_and_send_capsules():
    """Периодическая проверка и отправка капсул"""
    try:
        capsules = safe_db_execute(
            "SELECT id, user_id, message, chat_id FROM timecapsules "
            "WHERE is_sent = 0 AND send_at <= datetime('now')",
            fetch=True
        )
        
        for capsule in capsules:
            try:
                bot.send_message(
                    capsule[3], 
                    f"📬 Пришло время вашей капсулы!\n\n{capsule[2]}"
                )
                safe_db_execute(
                    "UPDATE timecapsules SET is_sent = 1 WHERE id = ?",
                    (capsule[0],)
                )
            except Exception as e:
                logger.error(f"Ошибка отправки капсулы {capsule[0]}: {e}")
    except Exception as e:
        logger.error(f"Ошибка в check_and_send_capsules: {e}")

@bot.message_handler(commands=['timecapsule'])
def timecapsule_command(message):
    msg = bot.send_message(message.chat.id, "📨 Введите сообщение для будущего:")
    bot.register_next_step_handler(msg, process_capsule_message)

def process_capsule_message(message):
    user_data = {'text': message.text}
    msg = bot.send_message(message.chat.id, "Через сколько дней отправить? (1-365)")
    bot.register_next_step_handler(msg, process_capsule_days, user_data)

def process_capsule_days(message, user_data):
    try:
        days = int(message.text)
        if not 1 <= days <= 365:
            raise ValueError("Число дней должно быть от 1 до 365")
        
        send_date = datetime.now() + timedelta(days=days)
        user_id = message.from_user.id
        
        conn = sqlite3.connect('wedding_bot.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO timecapsules (user_id, message, send_at) VALUES (?, ?, ?)",
                     (user_id, user_data['text'], send_date))
        conn.commit()
        
        scheduler.add_job(
            send_capsule,
            'date',
            run_date=send_date,
            args=[user_id, user_data['text'], message.chat.id]
        )
        
        bot.send_message(message.chat.id, f"⏳ Капсула сохранена! Откроется {send_date.strftime('%d.%m.%Y')}")
    except ValueError:
        bot.reply_to(message, "Пожалуйста, введите число от 1 до 365")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Ошибка: {e}")
    finally:
        conn.close()

def send_capsule(user_id, message_text, chat_id):
    try:
        bot.send_message(chat_id, f"📬 Пришло время вашей капсулы!\n\n{message_text}")
        
        conn = sqlite3.connect('wedding_bot.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE timecapsules SET is_sent=1 WHERE user_id=? AND message=? AND is_sent=0", 
                      (user_id, message_text))
        conn.commit()
    except Exception as e:
        logging.error(f"Ошибка при отправке капсулы: {e}")
    finally:
        conn.close()
# ===== ЗАПУСК ИНИЦИАЛИЗАЦИИ =====
#init_db()
scheduler.add_job(check_and_send_capsules, 'interval', minutes=5)
scheduler.start()

# ===== ЗАПУСК БОТА С ОБРАБОТКОЙ ОШИБОК =====
if __name__ == "__main__":
    logger.info("Бот запускается...")
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=30)
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}")
    finally:
        scheduler.shutdown()
        logger.info("Бот остановлен")