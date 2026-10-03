import os
import html
import sqlite3
import logging
from threading import Lock

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Forbidden, TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)
DB_PATH = os.environ.get("DB_PATH", "fonty.db")
DB_LOCK = Lock()

ADMIN_USERNAMES = {
    x.strip().lstrip("@").lower()
    for x in os.environ.get("ADMIN_USERNAMES", "").split(",")
    if x.strip()
}
ADMIN_IDS = {
    int(x.strip())
    for x in os.environ.get("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}

# Per-admin temporary action. The important data itself is stored in SQLite.
ADMIN_ACTIONS = {}

# Unicode alphabets
SETS = {
    "bold": (
        "𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙",
        "𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳",
    ),
    "italic": (
        "𝐴𝐵𝐶𝐷𝐸𝐹𝐺𝐻𝐼𝐽𝐾𝐿𝑀𝑁𝑂𝑃𝑄𝑅𝑆𝑇𝑈𝑉𝑊𝑋𝑌𝑍",
        "𝑎𝑏𝑐𝑑𝑒𝑓𝑔ℎ𝑖𝑗𝑘𝑙𝑚𝑛𝑜𝑝𝑞𝑟𝑠𝑡𝑢𝑣𝑤𝑥𝑦𝑧",
    ),
    "bold_italic": (
        "𝑨𝑩𝑪𝑫𝑬𝑭𝑮𝑯𝑰𝑱𝑲𝑳𝑴𝑵𝑶𝑷𝑸𝑹𝑺𝑻𝑼𝑽𝑾𝑿𝒀𝒁",
        "𝒂𝒃𝒄𝒅𝒆𝒇𝒈𝒉𝒊𝒋𝒌𝒍𝒎𝒏𝒐𝒑𝒒𝒓𝒔𝒕𝒖𝒗𝒘𝒙𝒚𝒛",
    ),
    "mono": (
        "𝙰𝙱𝙲𝙳𝙴𝙵𝙶𝙷𝙸𝙹𝙺𝙻𝙼𝙽𝙾𝙿𝚀𝚁𝚂𝚃𝚄𝚅𝚆𝚇𝚈𝚉",
        "𝚊𝚋𝚌𝚍𝚎𝚏𝚐𝚑𝚒𝚓𝚔𝚕𝚖𝚗𝚘𝚙𝚚𝚛𝚜𝚝𝚞𝚟𝚠𝚡𝚢𝚣",
    ),
    "gothic": (
        "𝔄𝔅ℭ𝔇𝔈𝔉𝔊ℌℑ𝔍𝔎𝔏𝔐𝔑𝔒𝔓𝔔ℜ𝔖𝔗𝔘𝔙𝔚𝔛𝔜ℨ",
        "𝔞𝔟𝔠𝔡𝔢𝔣𝔤𝔥𝔦𝔧𝔨𝔩𝔪𝔫𝔬𝔭𝔮𝔯𝔰𝔱𝔲𝔳𝔴𝔵𝔶𝔷",
    ),
    "double": (
        "𝔸𝔹ℂ𝔻𝔼𝔽𝔾ℍ𝕀𝕁𝕂𝕃𝕄ℕ𝕆ℙℚℝ𝕊𝕋𝕌𝕍𝕎𝕏𝕐ℤ",
        "𝕒𝕓𝕔𝕕𝕖𝕗𝕘𝕙𝕚𝕛𝕜𝕝𝕞𝕟𝕠𝕡𝕢𝕣𝕤𝕥𝕦𝕧𝕨𝕩𝕪𝕫",
    ),
}

STYLE_NAMES = {
    "bold": "𝐁𝐨𝐥𝐝",
    "italic": "𝘐𝘵𝘢𝘭𝘪𝘤",
    "bold_italic": "𝓢𝓬𝓻𝓲𝓹𝓽",
    "mono": "𝙼𝚘𝚗𝚘",
    "gothic": "𝔊𝔬𝔱𝔥𝔦𝔠",
    "double": "𝔻𝕠𝕦𝕓𝕝𝕖",
    "bubble": "ⓑⓤⓑⓑⓛⓔ",
    "underline": "U̲n̲d̲e̲r̲l̲i̲n̲e",
    "strike": "S̅t̅r̅i̅k̅e̅",
}


def db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with DB_LOCK, db() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_text TEXT DEFAULT '',
                active INTEGER DEFAULT 1
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS exceptions (
                user_id INTEGER PRIMARY KEY,
                username TEXT
            )"""
        )
        conn.commit()


def save_user(user):
    with DB_LOCK, db() as conn:
        conn.execute(
            """INSERT INTO users(user_id, username, first_name, active)
               VALUES(?, ?, ?, 1)
               ON CONFLICT(user_id) DO UPDATE SET
                 username=excluded.username,
                 first_name=excluded.first_name,
                 active=1""",
            (user.id, user.username or "", user.first_name or ""),
        )
        conn.commit()


def save_last_text(user_id, text):
    with DB_LOCK, db() as conn:
        conn.execute("UPDATE users SET last_text=? WHERE user_id=?", (text, user_id))
        conn.commit()


def get_last_text(user_id):
    with DB_LOCK, db() as conn:
        row = conn.execute("SELECT last_text FROM users WHERE user_id=?", (user_id,)).fetchone()
        return row["last_text"] if row else ""


def get_users():
    with DB_LOCK, db() as conn:
        return [row["user_id"] for row in conn.execute("SELECT user_id FROM users WHERE active=1")]


def deactivate_user(user_id):
    with DB_LOCK, db() as conn:
        conn.execute("UPDATE users SET active=0 WHERE user_id=?", (user_id,))
        conn.commit()


def get_subscriptions():
    with DB_LOCK, db() as conn:
        return conn.execute("SELECT id, chat_id, title, url FROM subscriptions ORDER BY id").fetchall()


def add_subscription(chat_id, title, url):
    with DB_LOCK, db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO subscriptions(chat_id,title,url) VALUES(?,?,?)",
            (chat_id, title, url),
        )
        conn.commit()


def delete_subscription(sub_id):
    with DB_LOCK, db() as conn:
        conn.execute("DELETE FROM subscriptions WHERE id=?", (sub_id,))
        conn.commit()


def add_exception(user_id, username):
    with DB_LOCK, db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO exceptions(user_id, username) VALUES(?,?)",
            (user_id, username),
        )
        conn.commit()


def delete_exception(user_id):
    with DB_LOCK, db() as conn:
        conn.execute("DELETE FROM exceptions WHERE user_id=?", (user_id,))
        conn.commit()


def is_exception(user_id):
    with DB_LOCK, db() as conn:
        return conn.execute(
            "SELECT 1 FROM exceptions WHERE user_id=?", (user_id,)
        ).fetchone() is not None


def get_exceptions():
    with DB_LOCK, db() as conn:
        return conn.execute(
            "SELECT user_id, username FROM exceptions ORDER BY username"
        ).fetchall()


def find_user_by_username(username):
    username = username.lstrip("@").lower()
    with DB_LOCK, db() as conn:
        return conn.execute(
            "SELECT user_id FROM users WHERE lower(username)=?",
            (username,),
        ).fetchone()


def is_admin(user):
    username = (user.username or "").lstrip("@").lower()
    return user.id in ADMIN_IDS or username in ADMIN_USERNAMES


def translate(text, style):
    upper, lower = SETS[style]
    result = []
    for ch in text:
        if "A" <= ch <= "Z":
            result.append(upper[ord(ch) - 65])
        elif "a" <= ch <= "z":
            result.append(lower[ord(ch) - 97])
        else:
            result.append(ch)
    return "".join(result)


def decorated(text, mark):
    return "".join(ch + mark if ch != " " else ch for ch in text)


CIRCLED_UPPER = "ⒶⒷⒸⒹⒺⒻⒼⒽⒾⒿⓀⓁⓂⓃⓄⓅⓆⓇⓈⓉⓊⓋⓌⓍⓎⓏ"
CIRCLED_LOWER = "ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ"


def bubble(text):
    out = []
    for ch in text:
        if "A" <= ch <= "Z":
            out.append(CIRCLED_UPPER[ord(ch) - 65])
        elif "a" <= ch <= "z":
            out.append(CIRCLED_LOWER[ord(ch) - 97])
        else:
            out.append(ch)
    return "".join(out)


def make_font(text, style):
    if style in SETS:
        return translate(text, style)
    if style == "bubble":
        return bubble(text)
    if style == "underline":
        return decorated(text, "\u0332")
    if style == "strike":
        return decorated(text, "\u0336")
    return text


def font_keyboard():
    keys = [
        ("bold", "𝐁𝐨𝐥𝐝"),
        ("italic", "𝘐𝘵𝘢𝘭𝘪𝘤"),
        ("bold_italic", "𝓢𝓬𝓻𝓲𝓹𝓽"),
        ("mono", "𝙼𝚘𝚗𝚘"),
        ("gothic", "𝔊𝔬𝔱𝔥𝔦𝔠"),
        ("double", "𝔻𝕠𝕦𝕓𝕝𝕖"),
        ("bubble", "ⓑⓤⓑⓑⓛⓔ"),
        ("underline", "U̲n̲d̲e̲r̲l̲i̲n̲e"),
        ("strike", "S̅t̅r̅i̅k̅e̅"),
    ]
    rows = []
    for i in range(0, len(keys), 2):
        rows.append(
            [
                InlineKeyboardButton(keys[i][1], callback_data=f"font:{keys[i][0]}"),
                InlineKeyboardButton(keys[i + 1][1], callback_data=f"font:{keys[i + 1][0]}")
                if i + 1 < len(keys)
                else InlineKeyboardButton("—", callback_data="noop"),
            ]
        )
    return InlineKeyboardMarkup(rows)


def admin_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📢 Обязательные подписки", callback_data="adm:subs")],
            [InlineKeyboardButton("👤 Исключения", callback_data="adm:exceptions")],
            [InlineKeyboardButton("📣 Рассылка", callback_data="adm:broadcast")],
            [InlineKeyboardButton("📊 Статистика", callback_data="adm:stats")],
        ]
    )


async def missing_subscriptions(user_id, bot):
    if is_exception(user_id):
        return []
    missing = []
    for sub in get_subscriptions():
        try:
            member = await bot.get_chat_member(sub["chat_id"], user_id)
            if member.status in ("left", "kicked"):
                missing.append(sub)
        except TelegramError as exc:
            logging.warning("Subscription check failed for %s: %s", sub["chat_id"], exc)
            # If the bot cannot check the channel, treat it as not subscribed.
            missing.append(sub)
    return missing


async def require_subscription(update, context):
    user = update.effective_user
    if not user:
        return True
    save_user(user)
    if is_admin(user) or is_exception(user.id):
        return True

    missing = await missing_subscriptions(user.id, context.bot)
    if not missing:
        return True

    buttons = [
        [InlineKeyboardButton(f"📢 {sub['title']}", url=sub["url"])]
        for sub in missing
    ]
    buttons.append([InlineKeyboardButton("✅ Проверить подписку", callback_data="check_subs")])

    text = (
        "🔒 <b>Доступ ограничен</b>\n\n"
        "Чтобы пользоваться ботом, подпишись на обязательные каналы:"
    )
    if update.callback_query:
        await update.callback_query.message.reply_text(
            text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons)
        )
    elif update.message:
        await update.message.reply_text(
            text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons)
        )
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)

    if not await require_subscription(update, context):
        return

    keyboard = [
        [InlineKeyboardButton("✨ Как пользоваться", callback_data="help")],
    ]
    if is_admin(user):
        keyboard.append([InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin")])

    await update.message.reply_text(
        "✨ <b>Добро пожаловать в Fonty!</b>\n\n"
        "Отправь мне текст — я превращу его в красивые шрифты.\n\n"
        "После отправки текста выбери нужный стиль кнопкой.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def help_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await require_subscription(update, context):
        return
    await query.message.reply_text(
        "Просто отправь мне текст сообщением.\n"
        "После этого появятся кнопки с вариантами шрифтов.\n\n"
        "💡 Декоративные Unicode-шрифты лучше всего работают с латиницей. "
        "Русский текст сохраняется, а подчёркивание/зачёркивание работают и для кириллицы."
    )


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)

    # Admin action has priority.
    action = ADMIN_ACTIONS.get(user.id)
    if is_admin(user) and action:
        await handle_admin_action(update, context, action)
        return

    if not await require_subscription(update, context):
        return

    text = update.message.text or ""
    if not text:
        return

    if len(text) > 1500:
        await update.message.reply_text("⚠️ Текст слишком длинный. Отправь до 1500 символов.")
        return

    save_last_text(user.id, text)
    await update.message.reply_text(
        "✨ <b>Выбери шрифт:</b> 👇",
        parse_mode="HTML",
        reply_markup=font_keyboard(),
    )


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)
    action = ADMIN_ACTIONS.get(user.id)

    if is_admin(user) and action == "broadcast":
        await send_broadcast(update, context)
        return

    if not await require_subscription(update, context):
        return


async def font_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    if not await require_subscription(update, context):
        return

    if query.data == "noop":
        return

    style = query.data.split(":", 1)[1]
    text = get_last_text(user.id)
    if not text:
        await query.message.reply_text("Сначала отправь мне текст.")
        return

    result = make_font(text, style)
    safe = html.escape(result)
    await query.message.reply_text(
        f"<b>{STYLE_NAMES.get(style, 'Шрифт')}</b>\n<code>{safe}</code>",
        parse_mode="HTML",
    )


async def check_subs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Проверяю подписки…")
    user = query.from_user
    missing = await missing_subscriptions(user.id, context.bot)

    if not missing:
        await query.message.reply_text(
            "✅ Подписка подтверждена!\n\nТеперь отправь мне текст."
        )
    else:
        buttons = [
            [InlineKeyboardButton(f"📢 {sub['title']}", url=sub["url"])]
            for sub in missing
        ]
        buttons.append([InlineKeyboardButton("✅ Проверить подписку", callback_data="check_subs")])
        await query.message.reply_text(
            "❌ Ты ещё не подписался на все обязательные каналы.",
            reply_markup=InlineKeyboardMarkup(buttons),
        )


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user):
        await update.message.reply_text("⛔ У тебя нет доступа к админ-панели.")
        return
    await update.message.reply_text(
        "⚙️ <b>Админ-панель</b>",
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    if not is_admin(user):
        await query.message.reply_text("⛔ Нет доступа.")
        return

    data = query.data

    if data == "admin":
        await query.message.reply_text(
            "⚙️ <b>Админ-панель</b>",
            parse_mode="HTML",
            reply_markup=admin_keyboard(),
        )
        return

    if data == "adm:subs":
        await show_subscriptions(query)
        return

    if data == "adm:exceptions":
        await show_exceptions(query)
        return

    if data == "adm:broadcast":
        ADMIN_ACTIONS[user.id] = "broadcast"
        await query.message.reply_text(
            "📣 <b>Рассылка</b>\n\n"
            "Отправь следующим сообщением <b>текст или картинку с подписью</b>.\n"
            "Это сообщение будет отправлено всем пользователям, которые нажали /start.\n\n"
            "Для отмены напиши /cancel.",
            parse_mode="HTML",
        )
        return

    if data == "adm:stats":
        users = len(get_users())
        subs = len(get_subscriptions())
        exceptions = len(get_exceptions())
        await query.message.reply_text(
            f"📊 <b>Статистика</b>\n\n"
            f"👤 Пользователей: <b>{users}</b>\n"
            f"📢 Обязательных подписок: <b>{subs}</b>\n"
            f"🛡 Исключений: <b>{exceptions}</b>",
            parse_mode="HTML",
        )
        return

    if data == "adm:add_sub":
        ADMIN_ACTIONS[user.id] = "add_sub"
        await query.message.reply_text(
            "📢 Отправь данные канала одной строкой:\n\n"
            "<code>@channel | Название | https://t.me/channel</code>\n\n"
            "Бот должен быть добавлен в канал и иметь права администратора, "
            "чтобы Telegram разрешил проверять подписку.",
            parse_mode="HTML",
        )
        return

    if data.startswith("adm:del_sub:"):
        sub_id = int(data.rsplit(":", 1)[1])
        delete_subscription(sub_id)
        await query.message.reply_text("✅ Обязательная подписка удалена.")
        await show_subscriptions(query)
        return

    if data == "adm:add_exception":
        ADMIN_ACTIONS[user.id] = "add_exception"
        await query.message.reply_text(
            "🛡 Отправь @username пользователя.\n\n"
            "Пример: <code>@username</code>",
            parse_mode="HTML",
        )
        return

    if data.startswith("adm:del_exception:"):
        user_id = int(data.rsplit(":", 1)[1])
        delete_exception(user_id)
        await query.message.reply_text("✅ Исключение удалено.")
        await show_exceptions(query)
        return


async def show_subscriptions(query):
    subs = get_subscriptions()
    buttons = []
    for sub in subs:
        buttons.append(
            [InlineKeyboardButton(f"❌ {sub['title']}", callback_data=f"adm:del_sub:{sub['id']}")]
        )
    buttons.append([InlineKeyboardButton("➕ Добавить подписку", callback_data="adm:add_sub")])
    buttons.append([InlineKeyboardButton("⬅️ Админ-панель", callback_data="admin")])

    if subs:
        text = "📢 <b>Обязательные подписки</b>\n\nНажми на канал, чтобы удалить его из обязательных."
    else:
        text = "📢 <b>Обязательные подписки</b>\n\nСписок пуст."
    await query.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))


async def show_exceptions(query):
    exceptions = get_exceptions()
    buttons = []
    for row in exceptions:
        title = f"❌ @{row['username']}" if row["username"] else f"❌ {row['user_id']}"
        buttons.append(
            [InlineKeyboardButton(title, callback_data=f"adm:del_exception:{row['user_id']}")]
        )
    buttons.append([InlineKeyboardButton("➕ Добавить исключение", callback_data="adm:add_exception")])
    buttons.append([InlineKeyboardButton("⬅️ Админ-панель", callback_data="admin")])

    text = (
        "🛡 <b>Исключения</b>\n\n"
        "Эти пользователи могут пользоваться ботом без обязательных подписок."
    )
    if not exceptions:
        text += "\n\nСписок пуст."
    await query.message.reply_text(
        text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons)
    )


async def handle_admin_action(update, context, action):
    user = update.effective_user

    if update.message and update.message.text == "/cancel":
        ADMIN_ACTIONS.pop(user.id, None)
        await update.message.reply_text("✅ Действие отменено.", reply_markup=admin_keyboard())
        return

    if action == "broadcast":
        await send_broadcast(update, context)
        return

    text = (update.message.text or "").strip() if update.message else ""

    if action == "add_sub":
        parts = [p.strip() for p in text.split("|")]
        if len(parts) != 3 or not parts[0] or not parts[1] or not parts[2]:
            await update.message.reply_text(
                "❌ Неверный формат.\n\n"
                "Используй:\n"
                "<code>@channel | Название | https://t.me/channel</code>",
                parse_mode="HTML",
            )
            return

        chat_id, title, url = parts
        try:
            await context.bot.get_chat(chat_id)
        except TelegramError:
            await update.message.reply_text(
                "❌ Не удалось найти этот канал.\n"
                "Проверь @username и убедись, что бот добавлен в канал."
            )
            return

        add_subscription(chat_id, title, url)
        ADMIN_ACTIONS.pop(user.id, None)
        await update.message.reply_text(
            f"✅ Канал <b>{html.escape(title)}</b> добавлен в обязательные подписки.",
            parse_mode="HTML",
            reply_markup=admin_keyboard(),
        )
        return

    if action == "add_exception":
        username = text.lstrip("@").strip()
        if not username:
            await update.message.reply_text("❌ Укажи @username.")
            return

        row = find_user_by_username(username)
        if not row:
            await update.message.reply_text(
                "❌ Пользователь не найден в базе бота. "
                "Пусть сначала нажмёт /start, затем добавь его в исключения."
            )
            return
        target_id = row["user_id"]

        add_exception(target_id, username)
        ADMIN_ACTIONS.pop(user.id, None)
        await update.message.reply_text(
            f"✅ @{html.escape(username)} добавлен в исключения.",
            parse_mode="HTML",
            reply_markup=admin_keyboard(),
        )


async def send_broadcast(update, context):
    user = update.effective_user
    if not is_admin(user):
        return

    if not update.message:
        return

    if update.message.text == "/cancel":
        ADMIN_ACTIONS.pop(user.id, None)
        await update.message.reply_text("✅ Рассылка отменена.", reply_markup=admin_keyboard())
        return

    users = get_users()
    sent = 0
    failed = 0

    for user_id in users:
        try:
            await context.bot.copy_message(
                chat_id=user_id,
                from_chat_id=user.id,
                message_id=update.message.message_id,
            )
            sent += 1
        except Forbidden:
            deactivate_user(user_id)
            failed += 1
        except TelegramError as exc:
            logging.warning("Broadcast to %s failed: %s", user_id, exc)
            failed += 1

    ADMIN_ACTIONS.pop(user.id, None)
    await update.message.reply_text(
        f"📣 <b>Рассылка завершена</b>\n\n"
        f"✅ Отправлено: <b>{sent}</b>\n"
        f"❌ Не доставлено: <b>{failed}</b>",
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


async def generic_media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)
    if is_admin(user) and ADMIN_ACTIONS.get(user.id) == "broadcast":
        await send_broadcast(update, context)
        return
    if not await require_subscription(update, context):
        return


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error("Update error: %s", context.error)


def main():
    init_db()

    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN environment variable is not set")

    port = int(os.environ.get("PORT", "10000"))
    base_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not base_url:
        raise RuntimeError("RENDER_EXTERNAL_URL is not available")

    webhook_url = f"{base_url.rstrip('/')}/telegram"

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("cancel", cancel_command))

    app.add_handler(CallbackQueryHandler(check_subs, pattern="^check_subs$"))
    app.add_handler(CallbackQueryHandler(font_button, pattern="^font:"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^(admin|adm:)"))
    app.add_handler(CallbackQueryHandler(help_button, pattern="^help$"))

    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.AUDIO | filters.VOICE | filters.ANIMATION, generic_media_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    app.add_error_handler(error_handler)

    print(f"Fonty bot started on port {port}")
    print(f"Webhook URL: {webhook_url}")
    print("Admin usernames:", ", ".join(sorted(ADMIN_USERNAMES)) or "none")
    print("Admin IDs:", ", ".join(map(str, sorted(ADMIN_IDS))) or "none")

    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="telegram",
        webhook_url=webhook_url,
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )


async def cancel_command(update, context):
    user = update.effective_user
    if is_admin(user):
        ADMIN_ACTIONS.pop(user.id, None)
        await update.message.reply_text("✅ Действие отменено.", reply_markup=admin_keyboard())


if __name__ == "__main__":
    main()
