from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, abort, Response)
import sqlite3
import hashlib
import os
import csv
import io
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'atlas-events-2024-secret-key')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE  = os.path.join(BASE_DIR, 'events.db')

# ── translations for multilingual support ────────────────────────────────────
T = {
    'register_title': {'ru': 'Регистрация', 'en': 'Registration', 'nl': 'Registratie'},
    'participant':    {'ru': 'Участник', 'en': 'Participant', 'nl': 'Deelnemer'},
    'guest':          {'ru': 'Гость', 'en': 'Guest', 'nl': 'Gast'},
    'volunteer':      {'ru': 'Волонтёр', 'en': 'Volunteer', 'nl': 'Vrijwilliger'},
    'name':           {'ru': 'Имя и фамилия', 'en': 'Full name', 'nl': 'Volledige naam'},
    'email':          {'ru': 'Email', 'en': 'Email', 'nl': 'E-mail'},
    'phone':          {'ru': 'Телефон', 'en': 'Phone', 'nl': 'Telefoon'},
    'organization':   {'ru': 'Организация', 'en': 'Organization', 'nl': 'Organisatie'},
    'position':       {'ru': 'Должность', 'en': 'Position', 'nl': 'Functie'},
    'notes':          {'ru': 'Примечание', 'en': 'Notes', 'nl': 'Opmerkingen'},
    'submit':         {'ru': 'Зарегистрироваться', 'en': 'Register', 'nl': 'Registreren'},
    'success_title':  {'ru': 'Вы зарегистрированы!', 'en': "You're registered!", 'nl': 'U bent geregistreerd!'},
    'success_body':   {
        'ru': 'Ваша заявка принята. Мы свяжемся с вами для подтверждения.',
        'en': 'Your application has been received. We will contact you to confirm.',
        'nl': 'Uw aanmelding is ontvangen. We nemen contact met u op ter bevestiging.',
    },
    'reg_type':       {'ru': 'Тип участия', 'en': 'Participation type', 'nl': 'Type deelname'},
    'schedule':       {'ru': 'Программа', 'en': 'Programme', 'nl': 'Programma'},
    'about':          {'ru': 'О мероприятии', 'en': 'About', 'nl': 'Over het evenement'},
    'goals':          {'ru': 'Цели мероприятия', 'en': 'Goals', 'nl': 'Doelstellingen'},
    'date':           {'ru': 'Дата', 'en': 'Date', 'nl': 'Datum'},
    'venue':          {'ru': 'Место', 'en': 'Venue', 'nl': 'Locatie'},
    'register_btn':   {'ru': 'Зарегистрироваться', 'en': 'Register now', 'nl': 'Nu registreren'},
}

def tr(key, lang='ru'):
    return T.get(key, {}).get(lang, T.get(key, {}).get('ru', key))

app.jinja_env.globals['tr'] = tr

# ── event registry ────────────────────────────────────────────────────────────
EVENTS = {
    'india-week': {
        'name': 'Неделя культуры Индии в Казахстане',
        'name_en': 'India Culture Week in Kazakhstan',
        'theme': 'india',
        'primary': '#FF9933', 'secondary': '#138808', 'accent': '#000080', 'bg': '#FFF8EE',
        'text_primary': '#FFFFFF',
        'type': 'cultural', 'emoji': '🇮🇳',
        'date': '15–22 сентября 2024',
        'venue': 'Государственный музей искусств им. Кастеева',
        'city': 'Алматы, Казахстан',
        'languages': ['ru'],
        'tags': ['культура', 'посольство', 'международный'],
        'short': 'Погружение в богатую культуру Индии: искусство, музыка, танцы, кухня и философия.',
        'description': (
            'Неделя культуры Индии — это уникальная возможность познакомиться с тысячелетней '
            'цивилизацией через живое искусство, традиционные танцы, классическую музыку, '
            'аутентичную кухню и духовные практики. Мероприятие организовано совместно с '
            'Посольством Индии в Республике Казахстан.'
        ),
        'goals': [
            'Укрепление культурных связей между Индией и Казахстаном',
            'Знакомство широкой аудитории с традиционными искусствами',
            'Развитие туристического и образовательного обмена',
            'Продвижение индийской культуры среди молодёжи',
        ],
        'reg_types': {'participant': 'Участник программы', 'guest': 'Гость мероприятия'},
        'has_staff': False,
        'schedule': [
            {'day': 1, 'date': '15 сентября', 'items': [
                {'time': '10:00', 'title': 'Торжественное открытие', 'speaker': 'Посол Индии в РК', 'loc': 'Главный зал'},
                {'time': '11:00', 'title': 'Выставка живописи и скульптуры', 'loc': 'Галерея A'},
                {'time': '14:00', 'title': 'Мастер-класс: классический танец Bharatanatyam', 'loc': 'Танцевальный зал'},
                {'time': '17:00', 'title': 'Концерт классической индийской музыки', 'loc': 'Главный зал'},
            ]},
            {'day': 2, 'date': '16 сентября', 'items': [
                {'time': '10:00', 'title': 'Мастер-класс по йоге', 'loc': 'Открытая площадка'},
                {'time': '13:00', 'title': 'Мастер-класс: индийская кухня', 'loc': 'Демо-кухня'},
                {'time': '15:00', 'title': 'Кинопоказ: лучшее индийское кино', 'loc': 'Кинозал'},
                {'time': '18:00', 'title': 'Вечер болливудских танцев', 'loc': 'Главный зал'},
            ]},
            {'day': 3, 'date': '17 сентября', 'items': [
                {'time': '10:00', 'title': 'Лекция: история и философия Индии', 'speaker': 'Проф. Рама Кришна', 'loc': 'Конференц-зал'},
                {'time': '13:00', 'title': 'Мастер-класс по мехенди (хна)', 'loc': 'Галерея B'},
                {'time': '16:00', 'title': 'Дегустация чаёв и специй', 'loc': 'Фойе'},
                {'time': '18:30', 'title': 'Гала-концерт артистов из Индии', 'loc': 'Главный зал'},
            ]},
        ],
    },
    'kings-day': {
        'name': 'День Короля Нидерландов',
        'name_en': "King's Day of the Netherlands",
        'name_nl': 'Koningsdag van Nederland',
        'theme': 'netherlands',
        'primary': '#F96E11', 'secondary': '#003DA5', 'accent': '#AE1C28', 'bg': '#FFF5EE',
        'text_primary': '#FFFFFF',
        'type': 'diplomatic', 'emoji': '🇳🇱',
        'date': '27 апреля 2024',
        'venue': 'Резиденция Посла Нидерландов',
        'city': 'Астана, Казахстан',
        'languages': ['ru', 'en', 'nl'],
        'tags': ['посольство', 'дипломатия', 'международный'],
        'short': 'Торжественный приём по случаю Дня Рождения Его Величества Короля Нидерландов Виллема-Александра.',
        'description': (
            'Ежегодный дипломатический приём объединяет представителей международных организаций, '
            'дипломатического корпуса, делового сообщества и культурных деятелей Казахстана. '
            'Мероприятие проходит в трёх языках: русском, английском и нидерландском.'
        ),
        'goals': [
            'Укрепление двусторонних дипломатических отношений',
            'Встреча представителей международных организаций',
            'Культурный обмен и деловой нетворкинг',
        ],
        'reg_types': {'participant': 'Официальный участник', 'guest': 'Приглашённый гость'},
        'has_staff': True,
        'schedule': [
            {'day': 1, 'date': '27 апреля', 'items': [
                {'time': '17:00', 'title': 'Регистрация / Registration / Registratie', 'loc': 'Вход / Entrance'},
                {'time': '18:00', 'title': 'Торжественный приём / Official reception / Officiële ontvangst', 'speaker': 'Посол Нидерландов', 'loc': 'Главный зал'},
                {'time': '18:30', 'title': 'Нидерландская культурная программа / Dutch cultural programme', 'loc': 'Сцена'},
                {'time': '19:00', 'title': 'Фуршет / Dinner reception / Diner receptie', 'loc': 'Банкетный зал'},
                {'time': '21:00', 'title': 'Завершение / End of event / Einde evenement', 'loc': ''},
            ]},
        ],
    },
    'charity-fair': {
        'name': 'Благотворительная ярмарка',
        'name_en': 'Charity Fair',
        'theme': 'charity',
        'primary': '#C0392B', 'secondary': '#E67E22', 'accent': '#27AE60', 'bg': '#FFFCF5',
        'text_primary': '#FFFFFF',
        'type': 'social', 'emoji': '❤️',
        'date': '7 декабря 2024',
        'venue': 'EXPO Convention Center',
        'city': 'Астана, Казахстан',
        'languages': ['ru'],
        'tags': ['благотворительность', 'социальный', 'ярмарка'],
        'short': 'Ежегодная ярмарка объединяет НКО, творцов, музыкантов и неравнодушных горожан.',
        'description': (
            'Благотворительная ярмарка — крупнейшее социальное событие года. '
            'Здесь можно познакомиться с деятельностью некоммерческих организаций, '
            'приобрести изделия мастеров, послушать живую музыку и поддержать тех, '
            'кто нуждается в помощи. Все средства направляются на конкретные социальные проекты.'
        ),
        'goals': [
            'Сбор средств для социальных и благотворительных проектов',
            'Объединение НКО, волонтёров и меценатов',
            'Поддержка местных мастеров, художников и музыкантов',
        ],
        'reg_types': {'participant': 'Участник-экспонент', 'guest': 'Гость ярмарки', 'volunteer': 'Волонтёр'},
        'has_staff': True,
        'schedule': [
            {'day': 1, 'date': '7 декабря', 'items': [
                {'time': '10:00', 'title': 'Открытие ярмарки', 'loc': 'Центральный вход'},
                {'time': '10:30', 'title': 'Выступление детских коллективов', 'loc': 'Главная сцена'},
                {'time': '12:00', 'title': 'Аукцион картин в поддержку НКО', 'loc': 'Зал A'},
                {'time': '14:00', 'title': 'Музыкальные выступления', 'loc': 'Главная сцена'},
                {'time': '16:00', 'title': 'Подведение итогов сбора', 'loc': 'Главная сцена'},
                {'time': '17:00', 'title': 'Закрытие', 'loc': ''},
            ]},
        ],
    },
    'storytelling': {
        'name': 'Фестиваль сторителлинга',
        'name_en': 'Storytelling Festival',
        'theme': 'storytelling',
        'primary': '#6C3483', 'secondary': '#1A5276', 'accent': '#D4AC0D', 'bg': '#F8F4FF',
        'text_primary': '#FFFFFF',
        'type': 'cultural', 'emoji': '📖',
        'date': '20 октября 2024',
        'venue': 'Центр современного искусства',
        'city': 'Алматы, Казахстан',
        'languages': ['ru'],
        'tags': ['культура', 'сторителлинг', 'вдохновение'],
        'short': 'Истории, которые меняют жизнь. Живые выступления выдающихся людей страны.',
        'description': (
            'Фестиваль сторителлинга — это вечер, где реальные люди делятся настоящими историями '
            'из своей жизни: о преодолении, открытиях, любви и смысле. Никаких слайдов — только голос, '
            'слова и честность. Каждое выступление длится 15–20 минут.'
        ),
        'goals': [
            'Вдохновить аудиторию через личные истории успеха и преодоления',
            'Создать сообщество storytellers Казахстана',
            'Показать силу слова, опыта и личного примера',
        ],
        'reg_types': {'participant': 'Спикер', 'guest': 'Гость'},
        'has_staff': False,
        'schedule': [
            {'day': 1, 'date': '20 октября', 'items': [
                {'time': '18:00', 'title': 'Регистрация гостей', 'loc': 'Фойе'},
                {'time': '18:30', 'title': 'Открытие. Приветственное слово', 'loc': 'Главный зал'},
                {'time': '19:00', 'title': 'История 1: Путь предпринимателя', 'speaker': 'Айбек Сатыбалдиев', 'loc': 'Сцена'},
                {'time': '19:20', 'title': 'История 2: Из врача в художника', 'speaker': 'Алина Жакупова', 'loc': 'Сцена'},
                {'time': '19:40', 'title': 'История 3: Кругосветное путешествие на велосипеде', 'speaker': 'Максат Ержанов', 'loc': 'Сцена'},
                {'time': '20:00', 'title': 'Перерыв. Нетворкинг', 'loc': 'Фойе'},
                {'time': '20:30', 'title': 'История 4: Строим школы в отдалённых аулах', 'speaker': 'Гульнар Сейткали', 'loc': 'Сцена'},
                {'time': '20:50', 'title': 'История 5: Музыкант мирового уровня', 'speaker': 'Данияр Абенов', 'loc': 'Сцена'},
                {'time': '21:10', 'title': 'Открытый микрофон: истории от гостей', 'loc': 'Сцена'},
                {'time': '21:30', 'title': 'Закрытие', 'loc': 'Главный зал'},
            ]},
        ],
    },
    'city-day': {
        'name': 'День города Астаны',
        'name_en': 'Astana City Day',
        'theme': 'city',
        'primary': '#1ABC9C', 'secondary': '#2980B9', 'accent': '#E74C3C', 'bg': '#F0FFFD',
        'text_primary': '#FFFFFF',
        'type': 'city', 'emoji': '🏙️',
        'date': '6–7 июля 2024',
        'venue': 'Площадь Независимости и EXPO',
        'city': 'Астана, Казахстан',
        'languages': ['ru'],
        'tags': ['город', 'праздник', 'общество'],
        'short': 'Масштабный городской праздник: концерты, выставки, спорт и мастер-классы для всей семьи.',
        'description': (
            'День города Астаны — главное городское событие года, объединяющее десятки тысяч '
            'горожан. Два дня насыщенной программы: парады, концерты звёзд казахстанской эстрады, '
            'спортивные мероприятия, выставки и детские площадки. Завершается праздничным фейерверком.'
        ),
        'goals': [
            'Объединить жителей города в праздновании',
            'Представить культурные и спортивные достижения Астаны',
            'Создать яркую атмосферу для всех возрастов',
        ],
        'reg_types': {'participant': 'Участник программы', 'guest': 'Гость праздника', 'volunteer': 'Волонтёр'},
        'has_staff': False,
        'schedule': [
            {'day': 1, 'date': '6 июля', 'items': [
                {'time': '10:00', 'title': 'Открытие праздника. Торжественный парад', 'loc': 'Площадь Независимости'},
                {'time': '12:00', 'title': 'Концерт казахских народных коллективов', 'loc': 'Главная сцена'},
                {'time': '14:00', 'title': 'Спортивные состязания и мастер-классы', 'loc': 'Спортивная зона'},
                {'time': '16:00', 'title': 'Выставка «Астана сквозь годы»', 'loc': 'Выставочный павильон'},
                {'time': '20:00', 'title': 'Гала-концерт звёзд казахстанской эстрады', 'loc': 'Главная сцена'},
                {'time': '22:00', 'title': 'Праздничный фейерверк', 'loc': 'Набережная'},
            ]},
            {'day': 2, 'date': '7 июля', 'items': [
                {'time': '11:00', 'title': 'Семейный день: мастер-классы для детей', 'loc': 'EXPO'},
                {'time': '13:00', 'title': 'Гастрономический фестиваль', 'loc': 'EXPO, зал B'},
                {'time': '15:00', 'title': 'Молодёжный форум «Будущее Астаны»', 'loc': 'Конференц-зал EXPO'},
                {'time': '18:00', 'title': 'Финальный концерт и закрытие праздника', 'loc': 'Главная сцена EXPO'},
            ]},
        ],
    },
}

TYPE_LABELS = {
    'all': 'Все',
    'cultural': 'Культурные',
    'diplomatic': 'Дипломатические',
    'social': 'Социальные',
    'city': 'Городские',
}

STAFF_CATEGORIES = {
    'organizer': {'ru': 'Организаторы', 'icon': 'bi-person-badge'},
    'selector':  {'ru': 'Подборщики участников', 'icon': 'bi-funnel'},
    'musician':  {'ru': 'Музыканты', 'icon': 'bi-music-note-beamed'},
    'catering':  {'ru': 'Кейтеринг', 'icon': 'bi-cup-hot'},
}

STATUS_LABELS = {
    'pending':   'Ожидает',
    'confirmed': 'Подтверждён',
    'declined':  'Отказ',
    'attended':  'Присутствовал',
}

STAFF_STATUS = {
    'active':    'Активен',
    'standby':   'В резерве',
    'cancelled': 'Отменён',
}

# ── DB ────────────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name          TEXT,
                role          TEXT NOT NULL DEFAULT 'staff',
                event_slug    TEXT
            );
            CREATE TABLE IF NOT EXISTS registrations (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                event_slug   TEXT NOT NULL,
                reg_type     TEXT NOT NULL,
                name         TEXT NOT NULL,
                email        TEXT,
                phone        TEXT,
                organization TEXT,
                position     TEXT,
                language     TEXT DEFAULT 'ru',
                notes        TEXT,
                status       TEXT DEFAULT 'pending',
                created_at   TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS staff (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                event_slug  TEXT NOT NULL,
                category    TEXT NOT NULL,
                name        TEXT NOT NULL,
                phone       TEXT,
                email       TEXT,
                role        TEXT,
                instrument  TEXT,
                company     TEXT,
                menu_items  TEXT,
                assignment  TEXT,
                status      TEXT DEFAULT 'active',
                notes       TEXT,
                created_at  TEXT DEFAULT (datetime('now','localtime'))
            );
        """)
        if not conn.execute("SELECT id FROM users WHERE username='admin'").fetchone():
            seed = [
                ('admin',       hash_pw('admin123'),   'Главный администратор',        'superadmin', None),
                ('india',       hash_pw('india123'),   'Координатор (Индия)',           'admin',      'india-week'),
                ('netherlands', hash_pw('nl123'),      'Координатор (Нидерланды)',      'admin',      'kings-day'),
                ('charity',     hash_pw('charity123'), 'Координатор (Ярмарка)',         'admin',      'charity-fair'),
                ('storytell',   hash_pw('story123'),   'Координатор (Сторителлинг)',    'admin',      'storytelling'),
                ('city',        hash_pw('city123'),    'Координатор (День города)',      'admin',      'city-day'),
            ]
            conn.executemany(
                "INSERT INTO users (username,password_hash,name,role,event_slug) VALUES (?,?,?,?,?)", seed
            )

# ── auth helpers ──────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Необходима авторизация.', 'error')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated

def can_access(slug):
    if session.get('role') == 'superadmin':
        return True
    return session.get('role') in ('admin', 'staff') and session.get('event_slug') == slug

# ── public routes ─────────────────────────────────────────────────────────────
@app.route('/')
def index():
    ftype = request.args.get('type', 'all')
    evs = EVENTS if ftype == 'all' else {k: v for k, v in EVENTS.items() if v['type'] == ftype}
    return render_template('index.html', events=evs, filter_type=ftype, type_labels=TYPE_LABELS)

@app.route('/event/<slug>')
def event_detail(slug):
    ev = EVENTS.get(slug)
    if not ev:
        abort(404)
    lang = request.args.get('lang', 'ru')
    if lang not in ev.get('languages', ['ru']):
        lang = 'ru'
    return render_template('event.html', ev=ev, slug=slug, lang=lang)

@app.route('/event/<slug>/register', methods=['GET', 'POST'])
def register(slug):
    ev = EVENTS.get(slug)
    if not ev:
        abort(404)
    lang = request.args.get('lang', 'ru')
    if lang not in ev.get('languages', ['ru']):
        lang = 'ru'

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Имя обязательно для заполнения.' if lang == 'ru' else 'Name is required.', 'error')
            return render_template('register.html', ev=ev, slug=slug, lang=lang)
        with get_db() as conn:
            conn.execute(
                "INSERT INTO registrations "
                "(event_slug,reg_type,name,email,phone,organization,position,language,notes) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (slug,
                 request.form.get('reg_type', 'guest'),
                 name,
                 request.form.get('email') or None,
                 request.form.get('phone') or None,
                 request.form.get('organization') or None,
                 request.form.get('position') or None,
                 lang,
                 request.form.get('notes') or None)
            )
        return redirect(url_for('register_success', slug=slug, lang=lang))

    return render_template('register.html', ev=ev, slug=slug, lang=lang)

@app.route('/event/<slug>/success')
def register_success(slug):
    ev = EVENTS.get(slug)
    if not ev:
        abort(404)
    lang = request.args.get('lang', 'ru')
    return render_template('success.html', ev=ev, slug=slug, lang=lang)

# ── auth routes ───────────────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('username', '').strip()
        p = request.form.get('password', '')
        with get_db() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE username=? AND password_hash=?",
                (u, hash_pw(p))
            ).fetchone()
        if user:
            session.update({
                'user_id': user['id'],
                'username': user['username'],
                'name': user['name'],
                'role': user['role'],
                'event_slug': user['event_slug'],
            })
            return redirect(url_for('admin_dashboard'))
        flash('Неверный логин или пароль.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ── admin routes ──────────────────────────────────────────────────────────────
@app.route('/admin')
@login_required
def admin_dashboard():
    stats = {}
    with get_db() as conn:
        for slug in EVENTS:
            if not can_access(slug):
                continue
            row = conn.execute(
                "SELECT COUNT(*) total, "
                "SUM(status='confirmed') confirmed, "
                "SUM(status='attended') attended "
                "FROM registrations WHERE event_slug=?", (slug,)
            ).fetchone()
            stats[slug] = dict(row)
    visible = {k: v for k, v in EVENTS.items() if can_access(k)}
    return render_template('admin/dashboard.html', events=visible, stats=stats)

@app.route('/admin/event/<slug>/participants')
@login_required
def admin_participants(slug):
    if not can_access(slug):
        abort(403)
    ev = EVENTS.get(slug)
    if not ev:
        abort(404)
    sf = request.args.get('status', 'all')
    tf = request.args.get('type', 'all')
    q = "SELECT * FROM registrations WHERE event_slug=?"
    params = [slug]
    if sf != 'all':
        q += " AND status=?"; params.append(sf)
    if tf != 'all':
        q += " AND reg_type=?"; params.append(tf)
    q += " ORDER BY created_at DESC"
    with get_db() as conn:
        regs = conn.execute(q, params).fetchall()
        counts_raw = conn.execute(
            "SELECT status, COUNT(*) c FROM registrations WHERE event_slug=? GROUP BY status", (slug,)
        ).fetchall()
    counts = {r['status']: r['c'] for r in counts_raw}
    return render_template('admin/participants.html',
                           ev=ev, slug=slug, regs=regs, counts=counts,
                           sf=sf, tf=tf,
                           status_labels=STATUS_LABELS)

@app.route('/admin/event/<slug>/participants/update', methods=['POST'])
@login_required
def admin_update_participant(slug):
    if not can_access(slug):
        abort(403)
    rid = request.form.get('reg_id')
    ns  = request.form.get('status')
    if ns in STATUS_LABELS:
        with get_db() as conn:
            conn.execute("UPDATE registrations SET status=? WHERE id=? AND event_slug=?", (ns, rid, slug))
    return redirect(url_for('admin_participants', slug=slug,
                            status=request.form.get('sf', 'all'),
                            type=request.form.get('tf', 'all')))

@app.route('/admin/event/<slug>/participants/delete', methods=['POST'])
@login_required
def admin_delete_participant(slug):
    if not can_access(slug):
        abort(403)
    rid = request.form.get('reg_id')
    with get_db() as conn:
        conn.execute("DELETE FROM registrations WHERE id=? AND event_slug=?", (rid, slug))
    return redirect(url_for('admin_participants', slug=slug))

@app.route('/admin/event/<slug>/participants/export')
@login_required
def admin_export(slug):
    if not can_access(slug):
        abort(403)
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM registrations WHERE event_slug=? ORDER BY created_at", (slug,)
        ).fetchall()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['ID', 'Тип', 'Имя', 'Email', 'Телефон', 'Организация', 'Должность', 'Язык', 'Статус', 'Дата'])
    for r in rows:
        w.writerow([r['id'], r['reg_type'], r['name'], r['email'], r['phone'],
                    r['organization'], r['position'], r['language'], r['status'], r['created_at']])
    return Response(
        out.getvalue().encode('utf-8-sig'),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={slug}-participants.csv'}
    )

@app.route('/admin/event/<slug>/staff')
@login_required
def admin_staff(slug):
    if not can_access(slug):
        abort(403)
    ev = EVENTS.get(slug)
    if not ev or not ev.get('has_staff'):
        abort(404)
    cat = request.args.get('category', 'organizer')
    with get_db() as conn:
        staff_list = conn.execute(
            "SELECT * FROM staff WHERE event_slug=? AND category=? ORDER BY name", (slug, cat)
        ).fetchall()
        cat_counts_raw = conn.execute(
            "SELECT category, COUNT(*) c FROM staff WHERE event_slug=? GROUP BY category", (slug,)
        ).fetchall()
    cat_counts = {r['category']: r['c'] for r in cat_counts_raw}
    return render_template('admin/staff.html',
                           ev=ev, slug=slug, staff_list=staff_list,
                           category=cat, cat_counts=cat_counts,
                           staff_cats=STAFF_CATEGORIES,
                           staff_status=STAFF_STATUS)

@app.route('/admin/event/<slug>/staff/add', methods=['POST'])
@login_required
def admin_add_staff(slug):
    if not can_access(slug):
        abort(403)
    cat = request.form.get('category', 'organizer')
    name = request.form.get('name', '').strip()
    if name:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO staff (event_slug,category,name,phone,email,role,"
                "instrument,company,menu_items,assignment,notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (slug, cat, name,
                 request.form.get('phone') or None,
                 request.form.get('email') or None,
                 request.form.get('role') or None,
                 request.form.get('instrument') or None,
                 request.form.get('company') or None,
                 request.form.get('menu_items') or None,
                 request.form.get('assignment') or None,
                 request.form.get('notes') or None)
            )
    return redirect(url_for('admin_staff', slug=slug, category=cat))

@app.route('/admin/event/<slug>/staff/action', methods=['POST'])
@login_required
def admin_staff_action(slug):
    if not can_access(slug):
        abort(403)
    sid    = request.form.get('staff_id')
    action = request.form.get('action')
    cat    = request.form.get('category', 'organizer')
    with get_db() as conn:
        if action == 'delete':
            conn.execute("DELETE FROM staff WHERE id=? AND event_slug=?", (sid, slug))
        elif action in STAFF_STATUS:
            conn.execute("UPDATE staff SET status=? WHERE id=? AND event_slug=?", (action, sid, slug))
    return redirect(url_for('admin_staff', slug=slug, category=cat))

# ── run ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    print("\n  ATLAS Events запущен → http://127.0.0.1:5000\n")
    print("  Аккаунты:")
    print("    admin / admin123   (все мероприятия)")
    print("    india / india123   (Неделя Индии)")
    print("    netherlands / nl123 (День Короля)")
    print("    charity / charity123 (Ярмарка)\n")
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
