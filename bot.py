import logging
import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery

# --- ASOSIY SOZLAMALAR ---
API_TOKEN = '8492225421:AAFBLHMTnezmkHDQlQlrGIvHum-0ewHM-6k' 
ADMIN_ID = 7868761814 
MOVIE_CHANNEL_ID = -1003863470774  

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- MA'LUMOTLAR BAZASINI SOZLASH ---
def setup_db():
    db = sqlite3.connect("kino_pro.db")
    cursor = db.cursor()
    # Jadvallarni yaratish
    cursor.execute("CREATE TABLE IF NOT EXISTS kinolar (kod TEXT UNIQUE, file_id TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS channels (id TEXT UNIQUE, link TEXT, name TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER UNIQUE)")
    
    # "Aqlli" qism: Agar caption ustuni bo'lmasa, uni qo'shadi
    try:
        cursor.execute("ALTER TABLE kinolar ADD COLUMN caption TEXT")
    except sqlite3.OperationalError:
        # Ustun allaqachon mavjud bo'lsa, xatoni o'tkazib yuboradi
        pass
    
    db.commit()
    return db, cursor

db, cursor = setup_db()

async def check_subscription(user_id):
    cursor.execute("SELECT id FROM channels")
    channels = cursor.fetchall()
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch[0], user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            continue 
    return True

# --- KANALGA YUKLANGAN KINONI TUTIB OLISH ---
@dp.channel_post(F.video)
async def auto_save_movie(message: Message):
    if message.chat.id == MOVIE_CHANNEL_ID:
        full_text = message.caption
        if full_text:
            parts = full_text.split('\n', 1)
            kino_kodi = parts[0].strip()
            kino_izohi = parts[1].strip() if len(parts) > 1 else ""
            try:
                cursor.execute("INSERT OR REPLACE INTO kinolar (kod, file_id, caption) VALUES (?, ?, ?)", 
                               (kino_kodi, message.video.file_id, kino_izohi))
                db.commit()
                await bot.send_message(ADMIN_ID, f"✅ Yangi kino bazaga qo'shildi!\n🔢 Kod: {kino_kodi}")
            except Exception as e:
                logging.error(f"Xato: {e}")

# --- START KOMANDASI ---
@dp.message(Command("start"))
async def start_cmd(message: Message):
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?)", (message.from_user.id,))
    db.commit()
    
    if await check_subscription(message.from_user.id):
        await message.answer("✅ Xush kelibsiz! Kino kodini yuboring:")
    else:
        cursor.execute("SELECT name, link FROM channels")
        channels = cursor.fetchall()
        if not channels:
            await message.answer("✅ Xush kelibsiz! Kino kodini yuboring:")
            return
        
        keyboard = [[InlineKeyboardButton(text=name, url=link)] for name, link in channels]
        keyboard.append([InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_sub")])
        await message.answer("❌ Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:", 
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@dp.callback_query(F.data == "check_sub")
async def check_callback(call: CallbackQuery):
    if await check_subscription(call.from_user.id):
        await call.message.delete()
        await call.message.answer("✅ Rahmat! Obuna tasdiqlandi. Kino kodini yuboring:")
    else:
        await call.answer("❗️ Hali hamma kanallarga a'zo bo'lmadingiz!", show_alert=True)

# --- ADMIN KOMANDALARI ---
@dp.message(Command("stat"), F.from_user.id == ADMIN_ID)
async def get_stat(message: Message):
    cursor.execute("SELECT COUNT(*) FROM users")
    u_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM kinolar")
    k_count = cursor.fetchone()[0]
    await message.answer(f"📊 Statistikalar:\n👤 Foydalanuvchilar: {u_count}\n🎬 Kinolar: {k_count}")

@dp.message(Command("add_channel"), F.from_user.id == ADMIN_ID)
async def add_channel(message: Message):
    args = message.text.split(maxsplit=3)
    if len(args) == 4:
        _, ch_id, link, name = args
        cursor.execute("INSERT OR REPLACE INTO channels VALUES (?, ?, ?)", (ch_id, link, name))
        db.commit()
        await message.answer(f"✅ Kanal qo'shildi: {name}")
    else:
        await message.answer("❌ Format: /add_channel ID link Nomi")

@dp.callback_query(F.data.startswith("del_"), F.from_user.id == ADMIN_ID)
async def inline_delete(call: CallbackQuery):
    kod = call.data.replace("del_", "")
    cursor.execute("DELETE FROM kinolar WHERE kod=?", (kod,))
    db.commit()
    await call.message.delete()
    await call.answer("🗑 Kino o'chirildi!", show_alert=True)

# --- KINO QIDIRISH ---
@dp.message(F.text)
async def search_movie(message: Message):
    if message.text.startswith('/'): return
    
    if await check_subscription(message.from_user.id):
        cursor.execute("SELECT file_id, caption FROM kinolar WHERE kod=?", (message.text.strip(),))
        res = cursor.fetchone()
        if res:
            f_id, izoh = res
            caption_text = f"🎬 **Kod: {message.text}**\n\n{izoh if izoh else ''}"
            
            kb = None
            if message.from_user.id == ADMIN_ID:
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🗑 O'chirish (Admin)", callback_data=f"del_{message.text}")]
                ])
            
            await bot.send_video(message.chat.id, f_id, caption=caption_text, reply_markup=kb, parse_mode="Markdown")
        else:
            await message.answer("😔 Kechirasiz, bu kod bilan kino topilmadi.")
    else:
        await start_cmd(message)

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass