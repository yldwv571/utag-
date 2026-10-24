import asyncio
import html
import logging
import math
import os
import random
import sys
import time
from contextlib import suppress

import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatMemberStatus, ChatType, ParseMode
from aiogram.exceptions import (TelegramBadRequest, TelegramForbiddenError,
                                TelegramRetryAfter)
from aiogram.filters import (JOIN_TRANSITION, LEAVE_TRANSITION,
                             ChatMemberUpdatedFilter, Command, CommandObject,
                             StateFilter)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (BotCommand, BotCommandScopeAllChatAdministrators,
                           BotCommandScopeAllGroupChats,
                           BotCommandScopeAllPrivateChats, BotCommandScopeChat,
                           BotCommandScopeDefault, CallbackQuery,
                           ChatMemberUpdated, InlineKeyboardButton,
                           InlineKeyboardMarkup, Message, ReplyParameters)
from aiohttp import web

# ======================= SOZLAMALAR =======================
TOKEN = os.getenv("BOT_TOKEN") or sys.exit("BOT_TOKEN topilmadi! (export BOT_TOKEN=...)")

# ASOSIY EGASI. Admin panel faqat shu ID(lar)da ishlaydi va ko'rinadi.
OWNER_ID = 8495751297
OWNERS = {OWNER_ID} | {int(x) for x in os.getenv("OWNER_ID", "").replace(" ", "").split(",") if x.isdigit()}

DB_PATH = os.getenv("DB_PATH", "utag.db")

# ---- Oddiy va Premium limitlar ----
FREE_MAX_BATCH, FREE_MIN_DELAY, FREE_COOLDOWN, FREE_EMOJI_BATCH = 5, 3.0, 30, 8
VIP_MAX_BATCH, VIP_MIN_DELAY, VIP_COOLDOWN, VIP_EMOJI_BATCH = 10, 2.0, 10, 10
DEF_BATCH, DEF_DELAY = 5, 3.0

GROUPS = (ChatType.GROUP, ChatType.SUPERGROUP)
START_TIME = time.time()

# ---------- PREMIUM EMOJI ----------
# Premium emoji ID larini shu yerga yozing (botga premium emoji yuborsangiz, bot ID ni qaytaradi).
# Bo'sh qoldirsangiz oddiy emoji ishlatiladi.
PREMIUM_EMOJI = {
    "fire": "", "star": "", "rocket": "", "crown": "",
    "bell": "", "check": "", "cross": "", "gem": "",
}
FALLBACK = {"fire": "🔥", "star": "⭐️", "rocket": "🚀", "crown": "👑",
            "bell": "🔔", "check": "✅", "cross": "❌", "gem": "💎"}


def pe(key: str) -> str:
    eid = PREMIUM_EMOJI.get(key)
    fb = FALLBACK[key]
    return f'<tg-emoji emoji-id="{eid}">{fb}</tg-emoji>' if eid else fb


# ---------- SO'ZLAR (har biri 50 tadan) ----------
DEFAULT_TEXTS = [
    "📢 Hammaga salom, bu yerga qarang!", "🔔 Guruh a'zolari, yig'ilamiz!",
    "👋 Assalomu alaykum, hamma shu yerda bo'lsin!", "📣 Diqqat, diqqat! Hamma e'tibor bering!",
    "🌟 Jamoa, sizni kutyapmiz!", "💬 Gaplashamiz, hamma kelsin!",
    "🎯 Hamma shu yerga, tezroq!", "🤝 Do'stlar, bir yerga to'planamiz!",
    "☀️ Xayrli kun, guruh!", "🕊 Hammaga salom va hurmat bilan!",
    "📌 Muhim gap bor, hamma o'qisin!", "⚡️ Tezkor chaqiruv! Hamma bu yerda!",
    "🌹 Hurmatli a'zolar, marhamat qilib kelinglar!", "🎊 Bayram kayfiyati, hamma qatnashsin!",
    "🧭 Yo'nalish bir: hamma shu yerda!", "🪁 Qani, kim bor? Javob bering!",
    "📡 Signal yuborildi, hamma qabul qilsin!", "🌍 Butun guruh, e'tiboringizga!",
    "🕌 Xayrli kun, aziz do'stlar!", "🌙 Xayrli kech, guruh a'zolari!",
    "🌅 Xayrli tong, hamma uyg'onsin!", "🛡 Jamoa safda, siz-chi?",
    "📖 Suhbatga qo'shiling, hamma kerak!", "🎤 Mikrofon sizda, gapiring!",
    "🧩 Jamoamizning har bir a'zosi muhim!", "🏁 Start berildi, hamma shu yerda!",
    "🔥 Guruh qizib ketdi, qo'shiling!", "💡 Fikringiz kerak, yozing!",
    "🌠 Bugun hammamiz birgamiz!", "🧡 Sizni sog'indik, ko'rinib turing!",
    "📬 Yangi xabar bor, tekshiring!", "🗣 Hamma ovoz bersin, fikr bildiring!",
    "⏰ Vaqt keldi, hamma safga!", "🎈 Gap bor, hamma yig'ilsin!",
    "🏡 Bizning katta oilamiz, hamma shu yerda!", "🔊 Ovoz balandroq! Hamma eshitsin!",
    "🚪 Eshik ochiq, kirib keling!", "🪄 Sehrli chaqiriq! Hamma kelsin!",
    "🧠 Aqlli odamlar, bu yerga!", "🌻 Kayfiyat a'lo, hamma kelsin!",
    "🛰 Aloqa o'rnatildi, hamma tayyormi?", "🎖 Faollar, safga turing!",
    "🧲 Hamma magnitdek shu yerga tortilsin!", "🍃 Salom-alik qilamiz, hamma keling!",
    "🔖 Eslatma: guruhda hamma faol bo'lsin!", "🥁 Nog'ora chalindi, hamma yig'ilsin!",
    "🏅 Eng faol guruh bo'lamiz, kelinglar!", "🌐 Online bo'lganlar, javob bering!",
    "💌 Sizga salom yo'lladik, ko'rib qo'ying!", "🙌 Qo'llarni baland ko'taring, hamma shu yerda!",
]

RANDOM_HEADERS = [
    "🔥 Uyg'on, guruh seni kutyapti!", "😎 Qani, kim bor bu yerda?",
    "🎉 Bugun kayfiyat zo'r, hamma kelsin!", "🚀 Tezroq kelinglar, gap bor!",
    "🌟 Yulduzlar yig'ilmoqda!", "😂 Kim uxlab qoldi? Uyg'oninglar!",
    "🤝 Jamoa, to'planamiz!", "💬 Gaplashamizmi? Hamma shu yerda!",
    "🍿 Qiziq narsa bo'lyapti, kelinglar!", "🏃‍♂️ Yuguring, kech qolmang!",
    "🎶 Musiqa boshlandi, hamma raqsga!", "🧨 Portlovchi yangilik! Hamma shu yerga!",
    "🦅 Burgutlar uchib keldi, siz-chi?", "🌈 Hamma kelsin, kayfiyat ko'taramiz!",
    "🍀 Omad sizlarga kulib boqsin, kelinglar!", "🛎 Qo'ng'iroq chalindi, hamma yig'ilsin!",
    "🎮 O'yin vaqti! Kim bor?", "☕️ Choy damlandi, hamma kelsin!",
    "🚨 Ogohlantirish: juda qiziq suhbat!", "🏆 Chempionlar, safga turing!",
    "🎁 Sovg'a bor, hamma shu yerga!", "🌙 Kech bo'ldi, lekin hamma uyg'oq bo'lsin!",
    "🐺 Bo'rilar to'dasi, yig'ilinglar!", "🍉 Tarvuz kesildi, hamma kelsin!",
    "🥳 Ziyofat boshlandi, kim kelmadi?", "🧙‍♂️ Sehrgar chaqiryapti, kelinglar!",
    "🎪 Sirk boshlandi, hamma shu yerga!", "🛸 UFO qo'nib o'tdi, hamma ko'rsin!",
    "🥇 Birinchi bo'lib kelgan g'olib!", "🍕 Pitsa keldi, hamma stolga!",
    "🌋 Vulqon otilmoqda, yig'iling!", "🎬 Kino boshlandi, joyingizni oling!",
    "🐉 Ajdaho uyg'ondi, jasurlar chiqsin!", "📺 Jonli efir! Hamma ekran oldiga!",
    "🏄 To'lqin keldi, hammamiz ustida!", "🔮 Folbin aytdi: hamma shu yerda bo'ladi!",
    "🧃 Sharbat tayyor, hamma kelsin!", "🎢 Attraksion boshlandi, o'tiring!",
    "🦄 Yakshox bo'lgan kun, hamma kelsin!", "🚁 Vertolyot qo'ndi, hamma shu yerga!",
    "🔔 Dring-dring! Dars boshlandi!", "💥 Bom! Hamma uyg'ondi!",
    "🥷 Ninjalar, yashirinishni bas qiling!", "🍯 Asal bor, hamma shu yerga!",
    "🏰 Qal'a darvozasi ochildi, kiring!", "🎯 Nishon aniq: hamma shu yerda!",
    "🌪 Bo'ron kelyapti, birga bo'laylik!", "🐝 Asalarilar yig'iladi, siz-chi?",
    "🎈 Havo sharlari uchdi, hamma qo'shilsin!", "🌟 Eng zo'r jamoa — bizniki, kelinglar!",
]

RANDOM_WORDS = [
    "do'stim", "birodar", "azizim", "sevimli", "yulduz", "chempion", "daho", "qahramon",
    "kapitan", "usta", "botir", "epchil", "jonim", "omadli", "sho'x", "mard",
    "polvon", "sardor", "akam", "ukam", "opam", "singlim", "xonim", "janob",
    "lochin", "sher", "burgut", "afsona", "komandir", "general", "professor", "doktor",
    "shoh", "bek", "fidoyi", "dono", "zukko", "tetik", "kuchli", "mehribon",
    "jasur", "g'olib", "qoplon", "bahodir", "alp", "ustoz", "jigarim", "aka", "opa", "gultoj",
]

RANDOM_EMOJI = [
    "😎", "🔥", "⚡️", "🌟", "💎", "🎯", "🍀", "🦁", "🚀", "🎉", "😄", "💪",
    "👑", "🦅", "🌈", "🎈", "🍭", "🧿", "🎸", "🏆", "💫", "🪄", "🐯", "🦋",
    "🌸", "🍉", "🍓", "🐼", "🦄", "🐬", "🌞", "🌙", "⭐️", "💥", "🎁", "🧸",
    "🎧", "🛸", "🏀", "⚽️", "🥇", "🍩", "🍕", "🍒", "🐱", "🦊", "🐺", "🌺", "🎨", "💖",
]

QUESTIONS = [
    "🤔 Bugun kayfiyatingiz 10 balldan necha?", "🍽 Bugun nima yedingiz?",
    "🎵 Hozir qanday qo'shiq tinglayapsiz?", "🎬 Oxirgi ko'rgan kinongiz qaysi?",
    "🌍 Qaysi davlatga borishni orzu qilasiz?", "📚 Oxirgi o'qigan kitobingiz nima?",
    "☕️ Choy yoki qahva?", "🌅 Erta turasizmi yoki kechki boyqushmisiz?",
    "🎮 Qaysi o'yinni yaxshi ko'rasiz?", "🐱 Mushuk yoki it?",
    "🏖 Dengiz yoki tog'?", "🧠 Eng yaxshi olgan maslahatingiz qaysi?",
    "🍕 Eng sevimli taomingiz?", "💭 Bugun nima haqida o'ylayapsiz?",
    "🎯 Shu oyda qanday maqsadingiz bor?", "📱 Telefonda eng ko'p vaqtingiz qaysi ilovada o'tadi?",
    "🌟 Bugun nima yaxshi bo'ldi?", "🎁 Qanday sovg'a olsangiz xursand bo'lasiz?",
    "🚗 Kelajakda qanday mashina olmoqchisiz?", "😂 Oxirgi marta qachon qattiq kuldingiz?",
]

WELCOMES = [
    "🎉 Xush kelibsiz, {m}! Guruhimiz sizga mehmon bo'lsin!",
    "👋 Assalomu alaykum, {m}! Bizga qo'shilganingizdan xursandmiz!",
    "🌟 {m}, oramizga xush kelibsiz! O'zingizni uydagidek his qiling!",
    "🤝 Salom, {m}! Tanishib olamiz, o'zingiz haqingizda yozing!",
    "🎈 {m} guruhga qo'shildi! Hamma salom bersin!",
    "🌹 Marhamat, {m}! Guruh qoidalariga amal qiling va suhbatlashing!",
    "🔥 Yangi a'zo: {m}! Qani, hamma qarsak chalsin!",
    "💫 {m}, xush kelibsiz! Bizda doim qiziq!",
]

BULLETS = ["👉", "🔹", "▪️", "🔸", "➡️", "✨"]

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
db: aiosqlite.Connection
BOT_USERNAME = ""
running: dict[int, dict] = {}
cooldowns: dict[int, float] = {}
tasks: set[asyncio.Task] = set()


# ======================= BAZA =======================
async def add_column(table: str, col: str, ddl: str):
    cur = await db.execute(f"PRAGMA table_info({table})")
    cols = {r["name"] for r in await cur.fetchall()}
    if col not in cols:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")


async def init_db():
    global db
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.executescript("""
    CREATE TABLE IF NOT EXISTS groups(
        chat_id INTEGER PRIMARY KEY, title TEXT, banned INTEGER DEFAULT 0,
        batch INTEGER DEFAULT 5, delay REAL DEFAULT 3, only_admins INTEGER DEFAULT 1,
        added_at INTEGER, premium_until INTEGER DEFAULT 0, welcome INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS members(
        chat_id INTEGER, user_id INTEGER, name TEXT, msgs INTEGER DEFAULT 0,
        last_seen INTEGER, optout INTEGER DEFAULT 0, PRIMARY KEY(chat_id, user_id));
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY, name TEXT, started_at INTEGER);
    CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, val INTEGER DEFAULT 0);
    """)
    # eski bazalarni yangilash
    await add_column("groups", "premium_until", "INTEGER DEFAULT 0")
    await add_column("groups", "welcome", "INTEGER DEFAULT 0")
    await add_column("members", "optout", "INTEGER DEFAULT 0")
    await db.commit()


async def flusher():
    while True:
        await asyncio.sleep(5)
        with suppress(Exception):
            await db.commit()


async def get_group(chat_id: int, title: str | None = None) -> dict:
    cur = await db.execute("SELECT * FROM groups WHERE chat_id=?", (chat_id,))
    row = await cur.fetchone()
    if not row:
        await db.execute("INSERT INTO groups(chat_id,title,added_at,batch,delay) VALUES(?,?,?,?,?)",
                         (chat_id, title, int(time.time()), DEF_BATCH, DEF_DELAY))
        await db.commit()
        cur = await db.execute("SELECT * FROM groups WHERE chat_id=?", (chat_id,))
        row = await cur.fetchone()
    elif title and row["title"] != title:
        await db.execute("UPDATE groups SET title=? WHERE chat_id=?", (title, chat_id))
    return dict(row)


async def update_group(chat_id: int, **kw):
    allowed = {"batch", "delay", "only_admins", "banned", "title", "premium_until", "welcome"}
    kw = {k: v for k, v in kw.items() if k in allowed}
    if not kw:
        return
    sets = ", ".join(f"{k}=?" for k in kw)
    await db.execute(f"UPDATE groups SET {sets} WHERE chat_id=?", (*kw.values(), chat_id))
    await db.commit()


async def touch_member(chat_id: int, user_id: int, name: str, msgs: int = 0):
    await db.execute(
        """INSERT INTO members(chat_id,user_id,name,msgs,last_seen) VALUES(?,?,?,?,?)
           ON CONFLICT(chat_id,user_id) DO UPDATE SET
           name=excluded.name, msgs=msgs+excluded.msgs, last_seen=excluded.last_seen""",
        (chat_id, user_id, name, msgs, int(time.time())))


async def remove_member(chat_id: int, user_id: int):
    await db.execute("DELETE FROM members WHERE chat_id=? AND user_id=?", (chat_id, user_id))


async def get_members(chat_id: int):
    cur = await db.execute("SELECT user_id, name FROM members WHERE chat_id=? AND optout=0", (chat_id,))
    return [(r["user_id"], r["name"]) for r in await cur.fetchall()]


async def save_private_user(u):
    await db.execute("INSERT OR IGNORE INTO users(user_id,name,started_at) VALUES(?,?,?)",
                     (u.id, u.full_name, int(time.time())))
    await db.commit()


async def kv_add(key: str, n: int = 1):
    await db.execute("""INSERT INTO kv(key,val) VALUES(?,?)
                        ON CONFLICT(key) DO UPDATE SET val=val+excluded.val""", (key, n))
    await db.commit()


async def kv_get(key: str) -> int:
    cur = await db.execute("SELECT val FROM kv WHERE key=?", (key,))
    row = await cur.fetchone()
    return row["val"] if row else 0


async def scalar(sql: str, *args) -> int:
    cur = await db.execute(sql, args)
    row = await cur.fetchone()
    return row[0] or 0


# ======================= YORDAMCHI =======================
def clean(name: str | None) -> str:
    n = (name or "").replace("\u200b", "").strip()[:25]
    return html.escape(n or "Do'st")


def mention(uid: int, name: str | None) -> str:
    return f'<a href="tg://user?id={uid}">{clean(name)}</a>'


async def is_admin_id(chat_id: int, user_id: int) -> bool:
    if user_id in OWNERS:
        return True
    try:
        m = await bot.get_chat_member(chat_id, user_id)
    except TelegramBadRequest:
        return False
    return m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR)


async def is_admin_msg(m: Message) -> bool:
    if m.sender_chat and m.sender_chat.id == m.chat.id:   # anonim admin
        return True
    return await is_admin_id(m.chat.id, m.from_user.id)


def is_prem(g: dict) -> bool:
    return (g.get("premium_until") or 0) > time.time()


def prem_days(g: dict) -> int:
    return max(0, int(((g.get("premium_until") or 0) - time.time()) / 86400) + 1)


def limits(prem: bool):
    """(max_batch, min_delay, cooldown, emoji_batch)"""
    if prem:
        return VIP_MAX_BATCH, VIP_MIN_DELAY, VIP_COOLDOWN, VIP_EMOJI_BATCH
    return FREE_MAX_BATCH, FREE_MIN_DELAY, FREE_COOLDOWN, FREE_EMOJI_BATCH


def progress_bar(done: int, total: int, n: int = 10) -> str:
    f = int(n * done / max(total, 1))
    return "▰" * f + "▱" * (n - f)


def fmt_uptime() -> str:
    s = int(time.time() - START_TIME)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    mi, _ = divmod(s, 60)
    return f"{d}k {h}s {mi}d"


def premium_offer() -> str:
    return (f"{pe('gem')} <b>Premium</b>\n\n<blockquote>"
            f"• Bir xabarda {VIP_MAX_BATCH} tagacha odam\n• Pauza {VIP_MIN_DELAY:g} soniyagacha\n"
            f"• Cooldown {VIP_COOLDOWN} soniya\n• /utagvip — maxsus VIP dizayn\n"
            f"• Emoji tagda {VIP_EMOJI_BATCH} tadan</blockquote>\n\n"
            f'Premium olish uchun <a href="tg://user?id={OWNER_ID}">egasiga</a> murojaat qiling.')


# ======================= TAG XABARI =======================
MODE_NAMES = {"default": "Oddiy tag", "random": "Random tag", "emoji": "Emoji tag",
              "admin": "Admin tag", "vip": "VIP tag", "savol": "Savol tag"}


def build_message(chunk, mode: str, text: str | None) -> str:
    custom = html.escape(text) if text else None

    if mode == "emoji":
        head = f"<b>{custom}</b>" if custom else random.choice(DEFAULT_TEXTS)
        body = " ".join(f'<a href="tg://user?id={uid}">{random.choice(RANDOM_EMOJI)}</a>'
                        for uid, _ in chunk)
        return f"{head}\n\n{body}"

    if mode == "vip":
        line = "━━━━━━━━━━━━━━"
        head = f"{pe('crown')} <b>{custom or 'VIP chaqiruv'}</b> {pe('crown')}"
        lines = [f"{pe('gem')} {random.choice(RANDOM_WORDS)} {mention(uid, n)}" for uid, n in chunk]
        return f"{head}\n{line}\n<blockquote>" + "\n".join(lines) + f"</blockquote>\n{line}"

    if mode == "savol":
        head = f"❓ <b>Kun savoli</b>\n{custom or random.choice(QUESTIONS)}"
        lines = [f"{random.choice(BULLETS)} {mention(uid, n)}" for uid, n in chunk]
    elif mode == "random":
        head = random.choice(RANDOM_HEADERS)
        if custom:
            head = f"<b>{custom}</b>\n{head}"
        lines = [f"{random.choice(RANDOM_EMOJI)} {random.choice(RANDOM_WORDS)} {mention(uid, n)}"
                 for uid, n in chunk]
    elif mode == "admin":
        head = f"{pe('crown')} <b>{custom or 'Adminlar, bu yerga!'}</b>"
        lines = [f"👮 {mention(uid, n)}" for uid, n in chunk]
    else:
        head = f"<b>{custom}</b>" if custom else random.choice(DEFAULT_TEXTS)
        bullet = random.choice(BULLETS)
        lines = [f"{bullet} {mention(uid, n)}" for uid, n in chunk]

    return f"{head}\n\n<blockquote>" + "\n".join(lines) + "</blockquote>"


async def safe_send(chat_id: int, text: str, reply_to: int | None = None):
    """True = yuborildi, False = xato, None = bot chiqarib yuborilgan."""
    rp = ReplyParameters(message_id=reply_to, allow_sending_without_reply=True) if reply_to else None
    for _ in range(3):
        try:
            await bot.send_message(chat_id, text, reply_parameters=rp)
            return True
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except TelegramForbiddenError:
            return None
        except TelegramBadRequest as e:
            logging.warning("send error: %s", e)
            if rp:
                rp = None
                continue
            return False
    return False


async def tag_job(chat_id: int, users, mode: str, text, reply_to, batch: int, delay: float, status: Message):
    st = running[chat_id]
    total, done, t0 = len(users), 0, time.time()
    stopped = False
    try:
        for n, i in enumerate(range(0, total, batch)):
            if st["stop"]:
                stopped = True
                break
            chunk = users[i:i + batch]
            ok = await safe_send(chat_id, build_message(chunk, mode, text), reply_to)
            if ok is None:
                stopped = True
                break
            done += len(chunk)
            if n % 4 == 3 and done < total:
                with suppress(TelegramBadRequest):
                    await status.edit_text(
                        f"{pe('rocket')} <b>{MODE_NAMES[mode]}</b> ketyapti...\n"
                        f"{progress_bar(done, total)}  {done}/{total}")
            await asyncio.sleep(delay)
        took = int(time.time() - t0)
        icon, word = ("🛑", "To'xtatildi") if stopped else (pe("check"), "Tag tugadi")
        with suppress(TelegramBadRequest):
            await status.edit_text(
                f"{icon} <b>{word}</b>\n👥 Tag qilindi: <b>{done}</b>/{total}\n⏱ Vaqt: {took} soniya")
    except Exception:
        logging.exception("tag_job error")
    finally:
        running.pop(chat_id, None)
        cooldowns[chat_id] = time.time()
        await kv_add("tags", done)
        await kv_add("runs", 1)


async def start_tag(m: Message, command: CommandObject, mode: str):
    chat = m.chat
    g = await get_group(chat.id, chat.title)
    if g["banned"]:
        return
    uid = m.from_user.id if m.from_user else 0
    is_owner = uid in OWNERS
    if g["only_admins"] and not await is_admin_msg(m):
        return await m.reply(f"{pe('cross')} Bu buyruq faqat adminlar uchun.")

    prem = is_prem(g)
    max_batch, min_delay, cooldown, emoji_batch = limits(prem)

    if mode == "vip" and not prem:
        return await m.reply(f"{pe('gem')} <b>/utagvip faqat premium guruhlar uchun.</b>\n\n" + premium_offer())
    if chat.id in running:
        return await m.reply("⏳ Tag allaqachon ketyapti. To'xtatish: /stop")
    left = cooldown - (time.time() - cooldowns.get(chat.id, 0))
    if left > 0 and not is_owner:
        return await m.reply(f"⏳ Yana <b>{int(left) + 1}</b> soniya kuting (cooldown).")

    try:
        admins = await bot.get_chat_administrators(chat.id)
    except TelegramBadRequest:
        admins = []
    admin_users = [(a.user.id, a.user.full_name) for a in admins if not a.user.is_bot]
    for a_id, a_name in admin_users:
        await touch_member(chat.id, a_id, a_name)

    users = admin_users if mode == "admin" else await get_members(chat.id)
    if not users:
        return await m.reply("Bazada hali hech kim yo'q. Odamlar guruhda yozgach to'planadi.")
    if mode in ("random", "vip"):
        random.shuffle(users)

    text = command.args.strip() if command.args else None
    reply_to = m.reply_to_message.message_id if m.reply_to_message else None
    batch = emoji_batch if mode == "emoji" else min(g["batch"], max_batch)
    delay = max(g["delay"], min_delay)
    eta = math.ceil(len(users) / batch) * delay

    running[chat.id] = {"stop": False, "by": uid}
    status = await m.answer(
        f"{pe('rocket')} <b>{MODE_NAMES[mode]}</b> boshlandi\n"
        f"👥 Odamlar: <b>{len(users)}</b>\n⏱ Taxminan: ~{int(eta)} soniya\n"
        f"To'xtatish: /stop")
    t = asyncio.create_task(tag_job(chat.id, users, mode, text, reply_to, batch, delay, status))
    tasks.add(t)
    t.add_done_callback(tasks.discard)


# ======================= GURUH BUYRUQLARI =======================
GROUP = F.chat.type.in_(GROUPS)


@dp.message(Command("utag", "tagall", "all"), GROUP)
async def c_utag(m: Message, command: CommandObject):
    await start_tag(m, command, "default")


@dp.message(Command("utagrd", "randomtag"), GROUP)
async def c_utagrd(m: Message, command: CommandObject):
    await start_tag(m, command, "random")


@dp.message(Command("utagemoji", "emojitag"), GROUP)
async def c_utagemoji(m: Message, command: CommandObject):
    await start_tag(m, command, "emoji")


@dp.message(Command("utagsavol", "savol"), GROUP)
async def c_utagsavol(m: Message, command: CommandObject):
    await start_tag(m, command, "savol")


@dp.message(Command("utagvip", "viptag"), GROUP)
async def c_utagvip(m: Message, command: CommandObject):
    await start_tag(m, command, "vip")


@dp.message(Command("uadmin", "admins"), GROUP)
async def c_uadmin(m: Message, command: CommandObject):
    await start_tag(m, command, "admin")


@dp.message(Command("stop", "cancel"), GROUP)
async def c_stop(m: Message):
    st = running.get(m.chat.id)
    if not st:
        return await m.reply("Hozir tag ketmayapti.")
    uid = m.from_user.id if m.from_user else 0
    if await is_admin_msg(m) or st["by"] == uid:
        st["stop"] = True
    else:
        await m.reply(f"{pe('cross')} Faqat adminlar to'xtata oladi.")


@dp.message(Command("count"), GROUP)
async def c_count(m: Message):
    n = len(await get_members(m.chat.id))
    out = await scalar("SELECT COUNT(*) FROM members WHERE chat_id=? AND optout=1", m.chat.id)
    total = await bot.get_chat_member_count(m.chat.id)
    await m.reply(f"👥 Bazada (tag qilinadigan): <b>{n}</b>\n🔕 Tag xohlamaganlar: <b>{out}</b>\n"
                  f"👤 Guruhda jami: <b>{total}</b>\n\n"
                  "<i>Bot faqat o'zi ko'rgan (yozgan yoki qo'shilgan) odamlarni tag qila oladi.</i>")


@dp.message(Command("top"), GROUP)
async def c_top(m: Message):
    cur = await db.execute(
        "SELECT user_id,name,msgs FROM members WHERE chat_id=? AND msgs>0 "
        "ORDER BY msgs DESC LIMIT 10", (m.chat.id,))
    rows = await cur.fetchall()
    if not rows:
        return await m.reply("Hali statistika yo'q.")
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    lines = [f"{medals[i]} {mention(r['user_id'], r['name'])} — <b>{r['msgs']}</b>"
             for i, r in enumerate(rows)]
    await m.reply(f"{pe('fire')} <b>Eng faol a'zolar</b>\n\n<blockquote>"
                  + "\n".join(lines) + "</blockquote>")


@dp.message(Command("notag"), GROUP)
async def c_notag(m: Message):
    if not m.from_user or (m.sender_chat and m.sender_chat.id == m.chat.id):
        return
    await touch_member(m.chat.id, m.from_user.id, m.from_user.full_name)
    await db.execute("UPDATE members SET optout=1 WHERE chat_id=? AND user_id=?", (m.chat.id, m.from_user.id))
    await m.reply("🔕 Endi sizni tag qilmayman. Qaytarish uchun: /yestag")


@dp.message(Command("yestag"), GROUP)
async def c_yestag(m: Message):
    if not m.from_user or (m.sender_chat and m.sender_chat.id == m.chat.id):
        return
    await touch_member(m.chat.id, m.from_user.id, m.from_user.full_name)
    await db.execute("UPDATE members SET optout=0 WHERE chat_id=? AND user_id=?", (m.chat.id, m.from_user.id))
    await m.reply("🔔 Yana tag qilinadigan ro'yxatdasiz.")


@dp.message(Command("premium"), GROUP)
async def c_premium(m: Message):
    g = await get_group(m.chat.id, m.chat.title)
    if is_prem(g):
        await m.reply(f"{pe('gem')} <b>Bu guruh Premium!</b>\n⏳ Qolgan muddat: ~<b>{prem_days(g)}</b> kun\n\n"
                      "VIP imkoniyatlar: /utagvip, 10 talik tag, qisqa pauza.")
    else:
        await m.reply(premium_offer())


@dp.message(Command("id"))
async def c_id(m: Message):
    lines = []
    if m.from_user:
        lines.append(f"👤 Sizning ID: <code>{m.from_user.id}</code>")
    if m.chat.type in GROUPS:
        lines.append(f"💬 Chat ID: <code>{m.chat.id}</code>")
    r = m.reply_to_message
    if r and r.from_user:
        lines.append(f"↩️ Reply qilingan odam ID: <code>{r.from_user.id}</code>")
    await m.reply("\n".join(lines) or "ID topilmadi")


GROUP_HELP = (
    f"{pe('star')} <b>UTAG BOT — buyruqlar</b>\n\n"
    "<blockquote>"
    "/utag [matn] — oddiy tag\n"
    "/utagrd [matn] — random so'zlar bilan tag\n"
    "/utagemoji [matn] — emoji tag\n"
    "/utagsavol [matn] — savol bilan tag\n"
    "/utagvip [matn] — VIP tag 💎 (premium)\n"
    "/uadmin [matn] — adminlarni tag qilish\n"
    "/stop — tagni to'xtatish\n"
    "/top — eng faol a'zolar\n"
    "/count — bazadagi odamlar\n"
    "/notag · /yestag — tag ro'yxatidan chiqish/qaytish\n"
    "/premium — premium holati\n"
    "/settings — sozlamalar (adminlar)\n"
    "/id — ID ni bilish"
    "</blockquote>\n\n"
    "💡 Biror xabarga <b>reply</b> qilib yozsangiz, tag o'sha xabarga javob bo'ladi."
)


@dp.message(Command("help"), GROUP)
async def c_help_group(m: Message):
    await m.reply(GROUP_HELP)


@dp.message(Command("start"), GROUP)
async def c_start_group(m: Message):
    await m.reply(f"{pe('check')} Men tayyorman! Buyruqlar: /help")


# ---------- GURUH SOZLAMALARI ----------
def settings_text(g: dict) -> str:
    who = "Faqat adminlar" if g["only_admins"] else "Hamma"
    wel = "Yoqilgan" if g["welcome"] else "O'chiq"
    prem = f"{pe('gem')} Premium (~{prem_days(g)} kun)" if is_prem(g) else "Oddiy"
    max_batch, min_delay, _, _ = limits(is_prem(g))
    return (f"⚙️ <b>Guruh sozlamalari</b>\n\n"
            f"💎 Tarif: <b>{prem}</b>\n"
            f"👥 Bir xabarda: <b>{min(g['batch'], max_batch)}</b> ta odam (maks {max_batch})\n"
            f"⏱ Pauza: <b>{max(g['delay'], min_delay):g}</b> soniya (min {min_delay:g})\n"
            f"🔐 Tag qila oladi: <b>{who}</b>\n"
            f"👋 Salomlashish: <b>{wel}</b>\n\n"
            "<i>Pauzani juda kamaytirmang, Telegram limiti tufayli bot vaqtincha bloklanishi mumkin.</i>")


def settings_kb(g: dict) -> InlineKeyboardMarkup:
    b = InlineKeyboardButton
    max_batch, min_delay, _, _ = limits(is_prem(g))
    batch, delay = min(g["batch"], max_batch), max(g["delay"], min_delay)
    return InlineKeyboardMarkup(inline_keyboard=[
        [b(text="➖", callback_data="st:batch:-"), b(text=f"👥 {batch} ta", callback_data="st:noop"),
         b(text="➕", callback_data="st:batch:+")],
        [b(text="➖", callback_data="st:delay:-"), b(text=f"⏱ {delay:g} s", callback_data="st:noop"),
         b(text="➕", callback_data="st:delay:+")],
        [b(text="🔐 " + ("Faqat adminlar" if g["only_admins"] else "Hamma"), callback_data="st:who")],
        [b(text="👋 Salomlashish: " + ("Yoqiq ✅" if g["welcome"] else "O'chiq ❌"), callback_data="st:welcome")],
        [b(text="❌ Yopish", callback_data="st:close")],
    ])


@dp.message(Command("settings"), GROUP)
async def c_settings(m: Message):
    if not await is_admin_msg(m):
        return await m.reply(f"{pe('cross')} Faqat adminlar uchun.")
    g = await get_group(m.chat.id, m.chat.title)
    await m.answer(settings_text(g), reply_markup=settings_kb(g))


@dp.callback_query(F.data.startswith("st:"))
async def cb_settings(cb: CallbackQuery):
    if not cb.message or cb.message.chat.type not in GROUPS:
        return await cb.answer()
    chat_id = cb.message.chat.id
    if not await is_admin_id(chat_id, cb.from_user.id):
        return await cb.answer("Faqat adminlar!", show_alert=True)
    parts = cb.data.split(":")
    action = parts[1]
    g = await get_group(chat_id)
    max_batch, min_delay, _, _ = limits(is_prem(g))
    if action == "noop":
        return await cb.answer()
    if action == "close":
        with suppress(Exception):
            await cb.message.delete()
        return await cb.answer()
    if action == "batch":
        v = min(g["batch"], max_batch) + (1 if parts[2] == "+" else -1)
        if v > max_batch:
            return await cb.answer(f"Maksimum {max_batch}. Ko'proq uchun /premium", show_alert=True)
        await update_group(chat_id, batch=max(1, v))
    elif action == "delay":
        v = max(g["delay"], min_delay) + (1 if parts[2] == "+" else -1)
        if v < min_delay:
            return await cb.answer(f"Minimum {min_delay:g} soniya. Kamroq uchun /premium", show_alert=True)
        await update_group(chat_id, delay=float(min(10, v)))
    elif action == "who":
        await update_group(chat_id, only_admins=0 if g["only_admins"] else 1)
    elif action == "welcome":
        await update_group(chat_id, welcome=0 if g["welcome"] else 1)
    g = await get_group(chat_id)
    with suppress(TelegramBadRequest):
        await cb.message.edit_text(settings_text(g), reply_markup=settings_kb(g))
    await cb.answer("Saqlandi ✅")


# ======================= BOT GURUHGA QO'SHILGANDA =======================
@dp.my_chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION), F.chat.type.in_(GROUPS))
async def bot_added(e: ChatMemberUpdated):
    g = await get_group(e.chat.id, e.chat.title)
    if g["banned"]:
        with suppress(Exception):
            await bot.leave_chat(e.chat.id)
        return
    with suppress(Exception):
        await bot.send_message(
            e.chat.id,
            f"{pe('star')} <b>Salom! Men UTAG botman.</b>\n\n"
            "Guruh a'zolarini chiroyli va tez tag qilaman.\n\n"
            f"{pe('bell')} <b>Ishlashim uchun meni admin qiling</b>, shunda barcha a'zolarni ko'ra olaman.\n"
            "Buyruqlar ro'yxati: /help")


# ======================= A'ZOLARNI KUZATISH =======================
@dp.chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def member_joined(e: ChatMemberUpdated):
    u = e.new_chat_member.user
    if not u.is_bot:
        await touch_member(e.chat.id, u.id, u.full_name)


@dp.chat_member(ChatMemberUpdatedFilter(LEAVE_TRANSITION))
async def member_left(e: ChatMemberUpdated):
    await remove_member(e.chat.id, e.new_chat_member.user.id)


# ======================= PRIVATE: START / MENYU =======================
PRIVATE = F.chat.type == ChatType.PRIVATE


def home_kb(user_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardButton
    rows = [
        [b(text="➕ Guruhga qo'shish",
           url=f"https://t.me/{BOT_USERNAME}?startgroup=true&admin=delete_messages+invite_users")],
        [b(text="📖 Buyruqlar", callback_data="menu:help"), b(text="ℹ️ Bot haqida", callback_data="menu:about")],
        [b(text="💎 Premium", callback_data="menu:premium")],
    ]
    if user_id in OWNERS:   # faqat egasiga ko'rinadi
        rows.append([b(text="⚙️ Admin panel", callback_data="adm:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu:home")]])


def welcome_text(name: str) -> str:
    return (f"{pe('star')} <b>Salom, {html.escape(name)}!</b>\n\n"
            f"Men <b>UTAG BOT</b> — guruhingiz a'zolarini tez va chiroyli tag qiluvchi botman.\n\n"
            f"{pe('fire')} <b>Imkoniyatlar:</b>\n"
            "<blockquote>• Oddiy, random, emoji, savol va VIP tag\n• Adminlarni tag qilish\n"
            "• Faol a'zolar reytingi\n• Tag qilinmaslikni tanlash\n"
            "• Har guruh uchun alohida sozlamalar</blockquote>\n\n"
            "Boshlash uchun meni guruhga qo'shing va <b>admin</b> qiling 👇")


PRIVATE_HELP = (
    f"📖 <b>Buyruqlar (guruhda ishlaydi)</b>\n\n<blockquote>"
    "/utag [matn] — oddiy tag\n/utagrd [matn] — random tag\n/utagemoji [matn] — emoji tag\n"
    "/utagsavol [matn] — savol bilan tag\n/utagvip [matn] — VIP tag 💎\n"
    "/uadmin [matn] — adminlarni tag qilish\n/stop — to'xtatish\n/top — faol a'zolar\n"
    "/count — bazadagi odamlar\n/notag · /yestag — tagdan chiqish/qaytish\n"
    "/settings — sozlamalar\n/premium — premium holati\n/id — ID</blockquote>\n\n"
    "<b>Qanday ishlaydi?</b>\n"
    "1) Meni guruhga qo'shing va admin qiling.\n2) Guruhda /utag yozing.\n"
    "Bot guruhda yozgan va qo'shilgan odamlarni yodda saqlaydi va ularni tag qiladi."
)

ABOUT = ("ℹ️ <b>Bot haqida</b>\n\nUTAG BOT — Telegram guruhlar uchun premium tag vositasi.\n"
         "Tezkor, xavfsiz va sozlanuvchan.\n\n"
         "<i>Telegram qoidasi: bot guruhdagi barcha a'zolar ro'yxatini ola olmaydi, shuning uchun "
         "u o'zi ko'rgan odamlarni tag qiladi.</i>")


@dp.message(Command("start"), PRIVATE)
async def p_start(m: Message):
    await save_private_user(m.from_user)
    await m.answer(welcome_text(m.from_user.first_name), reply_markup=home_kb(m.from_user.id))


@dp.message(Command("help"), PRIVATE)
async def p_help(m: Message):
    await m.answer(PRIVATE_HELP, reply_markup=back_kb())


@dp.callback_query(F.data.startswith("menu:"))
async def cb_menu(cb: CallbackQuery):
    page = cb.data.split(":")[1]
    if page == "help":
        text, kb = PRIVATE_HELP, back_kb()
    elif page == "about":
        text, kb = ABOUT, back_kb()
    elif page == "premium":
        text, kb = premium_offer(), back_kb()
    else:
        text, kb = welcome_text(cb.from_user.first_name), home_kb(cb.from_user.id)
    with suppress(TelegramBadRequest):
        await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


# ======================= EGASI ADMIN PANELI (faqat OWNER_ID) =======================
OWNER_MSG = PRIVATE & F.from_user.id.in_(OWNERS)


class Bc(StatesGroup):
    wait = State()
    confirm = State()


def adm_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [b(text="📊 Statistika", callback_data="adm:stats"), b(text="🏘 Guruhlar", callback_data="adm:groups")],
        [b(text="💎 Premium", callback_data="adm:prem"), b(text="📣 Xabar yuborish", callback_data="adm:bc")],
        [b(text="🔄 Yangilash", callback_data="adm:home"), b(text="⬅️ Orqaga", callback_data="menu:home")],
    ])


def adm_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Panel", callback_data="adm:home")]])


async def stats_text() -> str:
    now = int(time.time())
    users = await scalar("SELECT COUNT(*) FROM users")
    groups = await scalar("SELECT COUNT(*) FROM groups WHERE banned=0")
    banned = await scalar("SELECT COUNT(*) FROM groups WHERE banned=1")
    prem = await scalar("SELECT COUNT(*) FROM groups WHERE premium_until>?", now)
    members = await scalar("SELECT COUNT(*) FROM members")
    optout = await scalar("SELECT COUNT(*) FROM members WHERE optout=1")
    return (f"📊 <b>Statistika</b>\n\n<blockquote>"
            f"👤 Botni ishga tushirganlar: <b>{users}</b>\n"
            f"🏘 Faol guruhlar: <b>{groups}</b>\n💎 Premium guruhlar: <b>{prem}</b>\n"
            f"🚫 Ban qilingan: <b>{banned}</b>\n"
            f"👥 Bazadagi odamlar: <b>{members}</b>\n🔕 Tag xohlamaganlar: <b>{optout}</b>\n"
            f"🏷 Jami tag qilingan: <b>{await kv_get('tags')}</b>\n"
            f"🔁 Jami tag ishga tushirilgan: <b>{await kv_get('runs')}</b>\n"
            f"⚡️ Hozir ketayotgan: <b>{len(running)}</b>\n"
            f"⏳ Ish vaqti: <b>{fmt_uptime()}</b></blockquote>")


ADMIN_HINT = ("\n\n<i>Buyruqlar:\n/addpremium [ID] kun — premium berish (guruhda ID shart emas)\n"
              "/delpremium [ID] — premiumni olish\n/banchat ID · /unbanchat ID</i>")


@dp.message(Command("admin"), OWNER_MSG)
async def o_admin(m: Message):
    await m.answer(await stats_text() + "\n\n⚙️ <b>Admin panel</b>" + ADMIN_HINT, reply_markup=adm_kb())


@dp.callback_query(F.data.startswith("adm:"), F.from_user.id.in_(OWNERS))
async def cb_admin(cb: CallbackQuery, state: FSMContext):
    action = cb.data.split(":")[1]

    if action == "home":
        await state.clear()
        with suppress(TelegramBadRequest):
            await cb.message.edit_text(await stats_text() + "\n\n⚙️ <b>Admin panel</b>" + ADMIN_HINT,
                                       reply_markup=adm_kb())

    elif action == "stats":
        with suppress(TelegramBadRequest):
            await cb.message.edit_text(await stats_text(), reply_markup=adm_back())

    elif action == "groups":
        cur = await db.execute(
            "SELECT g.chat_id, g.title, g.banned, g.premium_until, "
            "(SELECT COUNT(*) FROM members m WHERE m.chat_id=g.chat_id) AS c "
            "FROM groups g ORDER BY c DESC LIMIT 15")
        rows = await cur.fetchall()
        now = time.time()
        lines = [f"{i}. <b>{html.escape(r['title'] or 'Nomsiz')}</b> "
                 f"{'🚫' if r['banned'] else ''}{'💎' if r['premium_until'] > now else ''}\n"
                 f"    <code>{r['chat_id']}</code> · 👥 {r['c']}" for i, r in enumerate(rows, 1)]
        text = "🏘 <b>Guruhlar (top 15)</b>\n\n" + ("\n".join(lines) or "Hali guruh yo'q.") + \
               "\n\n<i>/banchat ID — ban\n/unbanchat ID — banni olish</i>"
        with suppress(TelegramBadRequest):
            await cb.message.edit_text(text, reply_markup=adm_back())

    elif action == "prem":
        cur = await db.execute(
            "SELECT chat_id, title, premium_until FROM groups WHERE premium_until>? "
            "ORDER BY premium_until DESC LIMIT 20", (int(time.time()),))
        rows = await cur.fetchall()
        lines = [f"{i}. <b>{html.escape(r['title'] or 'Nomsiz')}</b>\n    <code>{r['chat_id']}</code> · "
                 f"~{max(0, int((r['premium_until'] - time.time()) / 86400) + 1)} kun"
                 for i, r in enumerate(rows, 1)]
        text = ("💎 <b>Premium guruhlar</b>\n\n" + ("\n".join(lines) or "Hozircha premium guruh yo'q.") +
                "\n\n<i>Berish: guruhda <code>/addpremium 30</code>\n"
                "yoki shu yerda <code>/addpremium -100123 30</code>\n"
                "Olish: <code>/delpremium</code></i>")
        with suppress(TelegramBadRequest):
            await cb.message.edit_text(text, reply_markup=adm_back())

    elif action == "bc":
        await state.set_state(Bc.wait)
        with suppress(TelegramBadRequest):
            await cb.message.edit_text(
                "📣 <b>Hammaga xabar</b>\n\nYubormoqchi bo'lgan xabaringizni yuboring "
                "(matn, rasm, video — farqi yo'q).\nBekor qilish: /cancel")

    elif action == "go":
        data = await state.get_data()
        await state.clear()
        if not data:
            return await cb.answer("Xabar topilmadi", show_alert=True)
        t = asyncio.create_task(broadcast(cb.from_user.id, data["src_chat"], data["src_msg"]))
        tasks.add(t)
        t.add_done_callback(tasks.discard)
        with suppress(TelegramBadRequest):
            await cb.message.edit_text("🚀 Yuborish boshlandi. Tugagach hisobot keladi.")

    elif action == "no":
        await state.clear()
        with suppress(TelegramBadRequest):
            await cb.message.edit_text("❌ Bekor qilindi.", reply_markup=adm_back())

    await cb.answer()


# egasi bo'lmaganlar adm: tugmasini bossa, hech narsa bo'lmaydi
@dp.callback_query(F.data.startswith("adm:"))
async def cb_admin_denied(cb: CallbackQuery):
    await cb.answer()


async def broadcast(owner_id: int, src_chat: int, src_msg: int):
    cur = await db.execute("SELECT user_id FROM users")
    targets = [r[0] for r in await cur.fetchall()]
    cur = await db.execute("SELECT chat_id FROM groups WHERE banned=0")
    targets += [r[0] for r in await cur.fetchall()]
    ok = fail = 0
    for cid in targets:
        try:
            await bot.copy_message(cid, src_chat, src_msg)
            ok += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
            with suppress(Exception):
                await bot.copy_message(cid, src_chat, src_msg)
                ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.07)
    with suppress(Exception):
        await bot.send_message(owner_id, f"✅ <b>Yuborish tugadi</b>\n\nMuvaffaqiyatli: <b>{ok}</b>\nXato: <b>{fail}</b>")


@dp.message(Command("banchat"), OWNER_MSG)
async def o_ban(m: Message, command: CommandObject):
    try:
        cid = int((command.args or "").strip())
    except ValueError:
        return await m.answer("Ishlatish: <code>/banchat -100123456789</code>")
    await get_group(cid)
    await update_group(cid, banned=1)
    with suppress(Exception):
        await bot.leave_chat(cid)
    await m.answer(f"🚫 <code>{cid}</code> ban qilindi.")


@dp.message(Command("unbanchat"), OWNER_MSG)
async def o_unban(m: Message, command: CommandObject):
    try:
        cid = int((command.args or "").strip())
    except ValueError:
        return await m.answer("Ishlatish: <code>/unbanchat -100123456789</code>")
    await update_group(cid, banned=0)
    await m.answer(f"✅ <code>{cid}</code> bandan chiqarildi.")


def parse_prem_args(m: Message, command: CommandObject, need_days: bool):
    """Guruhda: /addpremium 30 | Shaxsiyda: /addpremium -100123 30"""
    args = (command.args or "").split()
    try:
        if m.chat.type in GROUPS:
            cid = m.chat.id
            days = int(args[0]) if need_days else 0
        else:
            cid = int(args[0])
            days = int(args[1]) if need_days else 0
    except (ValueError, IndexError):
        return None
    if need_days and not 1 <= days <= 3650:
        return None
    return cid, days


@dp.message(Command("addpremium"), F.from_user.id.in_(OWNERS))
async def o_addprem(m: Message, command: CommandObject):
    res = parse_prem_args(m, command, True)
    if not res:
        return await m.answer("Ishlatish:\nGuruhda: <code>/addpremium 30</code>\n"
                              "Shaxsiyda: <code>/addpremium -100123456789 30</code>")
    cid, days = res
    g = await get_group(cid)
    until = int(max(time.time(), g["premium_until"]) + days * 86400)
    await update_group(cid, premium_until=until)
    await m.answer(f"{pe('gem')} <code>{cid}</code> guruhiga <b>{days}</b> kun premium berildi.")
    with suppress(Exception):
        await bot.send_message(cid, f"{pe('gem')} <b>Bu guruh Premium bo'ldi!</b> ({days} kun)\n"
                                    "Endi /utagvip va kengaytirilgan limitlar ishlaydi.")


@dp.message(Command("delpremium"), F.from_user.id.in_(OWNERS))
async def o_delprem(m: Message, command: CommandObject):
    res = parse_prem_args(m, command, False)
    if not res:
        return await m.answer("Ishlatish:\nGuruhda: <code>/delpremium</code>\n"
                              "Shaxsiyda: <code>/delpremium -100123456789</code>")
    cid, _ = res
    await get_group(cid)
    await update_group(cid, premium_until=0)
    await m.answer(f"✅ <code>{cid}</code> premiumi olib tashlandi.")


# Egasi bo'lmaganlar uchun yashirin buyruqlar: bot indamaydi
@dp.message(Command("admin", "banchat", "unbanchat", "addpremium", "delpremium"))
async def hidden_cmds(m: Message):
    return


@dp.message(Command("cancel"), OWNER_MSG, StateFilter(Bc.wait, Bc.confirm))
async def o_cancel(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("❌ Bekor qilindi.", reply_markup=adm_back())


@dp.message(OWNER_MSG, StateFilter(Bc.wait))
async def o_bc_message(m: Message, state: FSMContext):
    await state.update_data(src_chat=m.chat.id, src_msg=m.message_id)
    await state.set_state(Bc.confirm)
    b = InlineKeyboardButton
    await m.reply("👆 Mana shu xabar hamma foydalanuvchi va guruhlarga yuboriladi. Tasdiqlaysizmi?",
                  reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                      b(text="✅ Yuborish", callback_data="adm:go"),
                      b(text="❌ Bekor", callback_data="adm:no")]]))


# ---------- Premium emoji ID aniqlagich (private) ----------
def has_custom_emoji(m: Message) -> bool:
    return bool(m.entities) and any(e.type == "custom_emoji" for e in m.entities)


@dp.message(PRIVATE, has_custom_emoji)
async def p_emoji_id(m: Message):
    ids = [e.custom_emoji_id for e in m.entities if e.type == "custom_emoji"]
    await m.reply("🆔 <b>Premium emoji ID:</b>\n" + "\n".join(f"<code>{i}</code>" for i in ids))


@dp.message(PRIVATE)
async def p_any(m: Message):
    await save_private_user(m.from_user)
    await m.answer("Buyruqlar uchun /help yoki /start ni bosing 🙂")


# ---------- Eng oxirida: guruhdagi har bir xabar ----------
@dp.message(GROUP)
async def track(m: Message):
    if m.new_chat_members:
        joined = []
        for u in m.new_chat_members:
            if not u.is_bot:
                await touch_member(m.chat.id, u.id, u.full_name)
                joined.append(u)
        if joined:
            g = await get_group(m.chat.id, m.chat.title)
            if g["welcome"] and not g["banned"]:
                names = ", ".join(mention(u.id, u.full_name) for u in joined[:3])
                with suppress(Exception):
                    await m.answer(random.choice(WELCOMES).format(m=names))
    if m.left_chat_member:
        await remove_member(m.chat.id, m.left_chat_member.id)
    u = m.from_user
    if u and not u.is_bot and not (m.sender_chat and m.sender_chat.id == m.chat.id):
        await touch_member(m.chat.id, u.id, u.full_name, 1)


# ======================= ISHGA TUSHIRISH =======================
async def setup_bot():
    c = BotCommand
    private_cmds = [c(command="start", description="🚀 Botni ishga tushirish"),
                    c(command="help", description="📖 Yordam"),
                    c(command="id", description="🆔 ID ni bilish")]
    group_cmds = [
        c(command="utag", description="📢 Oddiy tag"),
        c(command="utagrd", description="🎲 Random tag"),
        c(command="utagemoji", description="😎 Emoji tag"),
        c(command="utagsavol", description="❓ Savol bilan tag"),
        c(command="utagvip", description="💎 VIP tag (premium)"),
        c(command="uadmin", description="👑 Adminlarni tag qilish"),
        c(command="stop", description="🛑 Tagni to'xtatish"),
        c(command="top", description="🏆 Faol a'zolar"),
        c(command="count", description="👥 Odamlar soni"),
        c(command="notag", description="🔕 Tag qilinmaslik"),
        c(command="yestag", description="🔔 Tag qilinishni qaytarish"),
        c(command="premium", description="💎 Premium holati"),
        c(command="id", description="🆔 ID ni bilish"),
        c(command="help", description="📖 Yordam"),
    ]
    await bot.set_my_commands(private_cmds, scope=BotCommandScopeDefault())
    await bot.set_my_commands(private_cmds, scope=BotCommandScopeAllPrivateChats())
    await bot.set_my_commands(group_cmds, scope=BotCommandScopeAllGroupChats())
    await bot.set_my_commands(group_cmds + [c(command="settings", description="⚙️ Sozlamalar")],
                              scope=BotCommandScopeAllChatAdministrators())
    # /admin menyuda faqat egasiga ko'rinadi
    for oid in OWNERS:
        with suppress(Exception):
            await bot.set_my_commands(
                private_cmds + [c(command="admin", description="⚙️ Admin panel"),
                                c(command="addpremium", description="💎 Premium berish"),
                                c(command="delpremium", description="💎 Premiumni olish")],
                scope=BotCommandScopeChat(chat_id=oid))
    with suppress(Exception):
        await bot.set_my_short_description("Premium tag bot: guruh a'zolarini tez va chiroyli tag qiladi 📢")
        await bot.set_my_description(
            "UTAG BOT — oddiy, random, emoji, savol va VIP tag, adminlarni tag qilish, "
            "faol a'zolar reytingi. Meni guruhga qo'shing va admin qiling!")


async def start_web():
    port = int(os.getenv("PORT", "0"))
    if not port:
        return
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()


async def main():
    global BOT_USERNAME
    logging.basicConfig(level=logging.INFO)
    await init_db()
    BOT_USERNAME = (await bot.get_me()).username
    await setup_bot()
    await start_web()
    asyncio.create_task(flusher())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())