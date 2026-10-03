import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)

# Unicode alphabets
SETS = {
    "bold": (
        "𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙",
        "𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳"
    ),
    "italic": (
        "𝐴𝐵𝐶𝐷𝐸𝐹𝐺𝐻𝐼𝐽𝐾𝐿𝑀𝑁𝑂𝑃𝑄𝑅𝑆𝑇𝑈𝑉𝑊𝑋𝑌𝑍",
        "𝑎𝑏𝑐𝑑𝑒𝑓𝑔ℎ𝑖𝑗𝑘𝑙𝑚𝑛𝑜𝑝𝑞𝑟𝑠𝑡𝑢𝑣𝑤𝑥𝑦𝑧"
    ),
    "bold_italic": (
        "𝑨𝑩𝑪𝑫𝑬𝑭𝑮𝑯𝑰𝑱𝑲𝑳𝑴𝑵𝑶𝑷𝑸𝑹𝑺𝑻𝑼𝑽𝑾𝑿𝒀𝒁",
        "𝒂𝒃𝒄𝒅𝒆𝒇𝒈𝒉𝒊𝒋𝒌𝒍𝒎𝒏𝒐𝒑𝒒𝒓𝒔𝒕𝒖𝒗𝒘𝒙𝒚𝒛"
    ),
    "mono": (
        "𝙰𝙱𝙲𝙳𝙴𝙵𝙶𝙷𝙸𝙹𝙺𝙻𝙼𝙽𝙾𝙿𝚀𝚁𝚂𝚃𝚄𝚅𝚆𝚇𝚈𝚉",
        "𝚊𝚋𝚌𝚍𝚎𝚏𝚐𝚑𝚒𝚓𝚔𝚕𝚖𝚗𝚘𝚙𝚚𝚛𝚜𝚝𝚞𝚟𝚠𝚡𝚢𝚣"
    ),
    "gothic": (
        "𝔄𝔅ℭ𝔇𝔈𝔉𝔊ℌℑ𝔍𝔎𝔏𝔐𝔑𝔒𝔓𝔔ℜ𝔖𝔗𝔘𝔙𝔚𝔛𝔜ℨ",
        "𝔞𝔟𝔠𝔡𝔢𝔣𝔤𝔥𝔦𝔧𝔨𝔩𝔪𝔫𝔬𝔭𝔮𝔯𝔰𝔱𝔲𝔳𝔴𝔵𝔶𝔷"
    ),
    "double": (
        "𝔸𝔹ℂ𝔻𝔼𝔽𝔾ℍ𝕀𝕁𝕂𝕃𝕄ℕ𝕆ℙℚℝ𝕊𝕋𝕌𝕍𝕎𝕏𝕐ℤ",
        "𝕒𝕓𝕔𝕕𝕖𝕗𝕘𝕙𝕚𝕛𝕜𝕝𝕞𝕟𝕠𝕡𝕢𝕣𝕤𝕥𝕦𝕧𝕨𝕩𝕪𝕫"
    ),
}

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

def bubble(text):
    out=[]
    for ch in text:
        if "A" <= ch <= "Z":
            out.append(chr(ord("Ⓐ") + ord(ch)-65))
        elif "a" <= ch <= "z":
            out.append(chr(ord("ⓐ") + ord(ch)-97))
        else:
            out.append(ch)
    return "".join(out)

def make_fonts(text):
    return [
        ("𝐁𝐨𝐥𝐝", translate(text, "bold")),
        ("𝘐𝘵𝘢𝘭𝘪𝘤", translate(text, "italic")),
        ("𝓢𝓬𝓻𝓲𝓹𝓽", translate(text, "bold_italic")),
        ("𝙼𝚘𝚗𝚘", translate(text, "mono")),
        ("𝔊𝔬𝔱𝔥𝔦𝔠", translate(text, "gothic")),
        ("𝔻𝕠𝕦𝕓𝕝𝕖", translate(text, "double")),
        ("ⓑⓤⓑⓑⓛⓔ", bubble(text)),
        ("U̲n̲d̲e̲r̲l̲i̲n̲e̲", decorated(text, "\u0332")),
        ("S̅t̅r̅i̅k̅e̅", decorated(text, "\u0336")),
    ]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("✨ Как пользоваться", callback_data="help")]]
    await update.message.reply_text(
        "✨ Добро пожаловать в Fonty!\n\n"
        "Отправь мне любой текст — я превращу его в красивые шрифты.\n\n"
        "Например: Привет, мир! 👋",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def help_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "Просто отправь мне текст сообщением.\n"
        "Я верну несколько вариантов оформления.\n\n"
        "💡 Лучше всего декоративные Unicode-шрифты работают с латиницей. "
        "Для русского текста доступны подчёркивание, зачёркивание и другие украшения."
    )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return

    if len(text) > 1500:
        await update.message.reply_text("⚠️ Текст слишком длинный. Отправь до 1500 символов.")
        return

    chunks = ["✨ Вот твои варианты:\n"]
    for name, result in make_fonts(text):
        chunks.append(f"<b>{name}</b>\n<code>{result}</code>")

    # Telegram message limit is 4096 chars.
    current = ""
    for chunk in chunks:
        if len(current) + len(chunk) + 2 > 3900:
            await update.message.reply_text(current, parse_mode="HTML")
            current = chunk
        else:
            current += ("\n\n" if current else "") + chunk
    if current:
        await update.message.reply_text(current, parse_mode="HTML")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error("Update error: %s", context.error)

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN environment variable is not set")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(help_button, pattern="^help$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_error_handler(error_handler)

    print("Fonty bot started")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
