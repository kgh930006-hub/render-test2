"""Advanced Telegram memory-storage bot (Arabic-first).

The user sends anything — text, photo, video, file, voice, audio,
animation or sticker — and the bot saves it as a "memory" with an
automatic type, date, caption and optional #tags parsed from the
caption/text. Memories can later be listed, searched, viewed and
deleted, all from Telegram.

Run with ``TELEGRAM_BOT_TOKEN`` set in the environment or in ``.env``::

    pip install -r requirements.txt
    python bot.py

The token is never stored in code.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import DB_PATH, LOG_LEVEL, PAGE_SIZE, TELEGRAM_BOT_TOKEN
from storage import (
    MEMORY_TYPES,
    Memory,
    add_memory,
    count_memories,
    delete_all,
    delete_memory,
    get_memory,
    get_stats,
    init_db,
    list_memories,
    search_memories,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
)
logger = logging.getLogger(__name__)

# Arabic labels per memory type, with an English word for clarity.
TYPE_LABELS: dict[str, str] = {
    "text": "📝 نص",
    "photo": "🖼️ صورة",
    "video": "🎬 فيديو",
    "document": "📄 ملف",
    "voice": "🎙️ بصمة صوتية",
    "audio": "🎵 صوت",
    "animation": "✨ صورة متحركة",
    "sticker": "😀 ملصق",
}

HELP_TEXT = """🗂️ **بوت تخزين الذكريات — دليل الاستخدام**

أرسل أي شيء وسأحفظه تلقائياً كذكرى: نص، صورة، فيديو، ملف،
بصمة صوتية، صوت، صورة متحركة أو ملصق.
أضف `#وسم` في النص أو التعليق لتصنيف الذكرى، مثل: `#سفر #عمل`.

**الأوامر:**
/start — ترحيب وطريقة الاستخدام
/help — هذا الدليل
/stats — إحصائيات ذكرياتك حسب النوع
/list [نوع] — عرض الذكريات مع أزرار للتصفح
/recent — أحدث 5 ذكريات
/search كلمة — بحث في النصوص والوسوم
/get رقم — عرض ذكرى برقمها، مثال: `/get 3`
/delete رقم — حذف ذكرى برقمها، مثال: `/delete 3`
/export — إرسال نسخة احتياطية من قاعدة البيانات
/clear — حذف كل الذكريات (بعد تأكيد)

أنواع `/list`: text, photo, video, document, voice, audio, animation, sticker
مثال: `/list photo`

---
Memory Bot — Help (English):
Send anything and I save it as a memory. Use #tags to organise.
Commands: /start /help /stats /list [type] /recent /search <word>
/get <id> /delete <id> /export /clear
"""


def _memory_line(memory: Memory) -> str:
    """One-line summary of a memory for list views."""
    label = TYPE_LABELS.get(memory.type, memory.type)
    preview = (memory.text or "").replace("\n", " ").strip()
    if len(preview) > 45:
        preview = preview[:45] + "…"
    tags = " ".join(f"#{t}" for t in memory.tags)
    date = memory.created_at[:10]
    line = f"#{memory.id} {label} • {date}"
    if preview:
        line += f"\n{preview}"
    if tags:
        line += f"\n{tags}"
    return line


def _list_keyboard(
    memories: list[Memory], memory_type: str, page: int, total: int
) -> InlineKeyboardMarkup:
    """Inline buttons: view / delete per item, plus pagination."""
    rows: list[list[InlineKeyboardButton]] = []
    for memory in memories:
        rows.append(
            [
                InlineKeyboardButton(
                    f"👁 عرض #{memory.id}", callback_data=f"view:{memory.id}"
                ),
                InlineKeyboardButton(
                    f"🗑 حذف #{memory.id}", callback_data=f"del:{memory.id}"
                ),
            ]
        )
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                "◀ السابق", callback_data=f"list:{memory_type}:{page - 1}"
            )
        )
    if (page + 1) * PAGE_SIZE < total:
        nav.append(
            InlineKeyboardButton(
                "التالي ▶", callback_data=f"list:{memory_type}:{page + 1}"
            )
        )
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(rows)


async def _send_memory(
    update: Update, context: ContextTypes.DEFAULT_TYPE, memory: Memory
) -> None:
    """Send a stored memory back to the user, by its type."""
    chat_id = update.effective_chat.id
    caption = memory.text or None
    tags = " ".join(f"#{t}" for t in memory.tags)
    footer = f"\n\n🆔 #{memory.id} • {memory.created_at[:16]}"
    if tags:
        footer += f"\n{tags}"
    if memory.type == "text":
        await context.bot.send_message(
            chat_id=chat_id, text=f"{memory.text}{footer}"
        )
    elif memory.type == "photo" and memory.file_id:
        await context.bot.send_photo(
            chat_id=chat_id, photo=memory.file_id, caption=(caption or "") + footer
        )
    elif memory.type == "video" and memory.file_id:
        await context.bot.send_video(
            chat_id=chat_id, video=memory.file_id, caption=(caption or "") + footer
        )
    elif memory.type == "document" and memory.file_id:
        await context.bot.send_document(
            chat_id=chat_id, document=memory.file_id, caption=(caption or "") + footer
        )
    elif memory.type == "voice" and memory.file_id:
        await context.bot.send_voice(chat_id=chat_id, voice=memory.file_id, caption=(caption or "") + footer)
    elif memory.type == "audio" and memory.file_id:
        await context.bot.send_audio(
            chat_id=chat_id, audio=memory.file_id, caption=(caption or "") + footer
        )
    elif memory.type == "animation" and memory.file_id:
        await context.bot.send_animation(
            chat_id=chat_id, animation=memory.file_id, caption=(caption or "") + footer
        )
    elif memory.type == "sticker" and memory.file_id:
        await context.bot.send_sticker(chat_id=chat_id, sticker=memory.file_id)
        if caption:
            await context.bot.send_message(chat_id=chat_id, text=caption + footer)
    else:
        await context.bot.send_message(
            chat_id=chat_id, text=f"{memory.text or '(بدون نص)'}{footer}"
        )


# ---------------------------------------------------------------- commands

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message + how to use the bot."""
    assert update.message is not None
    await update.message.reply_text(
        "👋 أهلاً بك في **بوت تخزين الذكريات**!\n\n"
        "أرسل لي أي شيء — نص، صورة، فيديو، ملف، بصمة صوتية، "
        "صوت، صورة متحركة أو ملصق — وسأحفظه لك كذكرى مع التاريخ "
        "والوسوم تلقائياً.\n\n"
        "استخدم `#وسم` في النص أو التعليق للتصنيف، مثل `#سفر`.\n\n"
        "جرّب: أرسل صورة أو نصاً الآن، أو اكتب /help لعرض كل الأوامر.\n\n"
        "Welcome! Send anything and I will save it as a memory. "
        "Use /help for all commands."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the help text."""
    assert update.message is not None
    await update.message.reply_text(HELP_TEXT)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show counts per type and the total."""
    assert update.message is not None and update.effective_user is not None
    stats = get_stats(DB_PATH, update.effective_user.id)
    lines = ["📊 **إحصائيات ذكرياتك**\n"]
    for memory_type in MEMORY_TYPES:
        label = TYPE_LABELS[memory_type]
        lines.append(f"{label}: {stats.get(memory_type, 0)}")
    lines.append(f"\n📌 المجموع: **{stats['total']}** ذكرى")
    await update.message.reply_text("\n".join(lines))


def _parse_list_type(args: list[str]) -> str:
    """Validate the optional type argument of /list; 'all' by default."""
    if not args:
        return "all"
    value = args[0].strip().lower()
    if value in MEMORY_TYPES:
        return value
    return "all"


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List memories with pagination buttons."""
    assert update.message is not None and update.effective_user is not None
    memory_type = _parse_list_type(context.args or [])
    await _show_list_page(update, context, memory_type, page=0)


async def _show_list_page(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    memory_type: str,
    page: int,
) -> None:
    user_id = update.effective_user.id  # type: ignore[union-attr]
    total = count_memories(
        DB_PATH, user_id, None if memory_type == "all" else memory_type
    )
    if total == 0:
        text = "📭 لا توجد ذكريات بعد. أرسل لي أي شيء لأحفظه لك!"
        if update.callback_query:
            await update.callback_query.edit_message_text(text)
        elif update.message:
            await update.message.reply_text(text)
        return
    max_page = max(0, (total - 1) // PAGE_SIZE)
    page = max(0, min(page, max_page))
    memories = list_memories(
        DB_PATH,
        user_id,
        None if memory_type == "all" else memory_type,
        limit=PAGE_SIZE,
        offset=page * PAGE_SIZE,
    )
    title = "🗂️ ذكرياتك" if memory_type == "all" else f"🗂️ ذكريات: {TYPE_LABELS[memory_type]}"
    text = f"{title} — صفحة {page + 1} من {max_page + 1} (المجموع {total})\n\n"
    text += "\n\n".join(_memory_line(m) for m in memories)
    keyboard = _list_keyboard(memories, memory_type, page, total)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    elif update.message:
        await update.message.reply_text(text, reply_markup=keyboard)


async def recent_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the 5 most recent memories."""
    assert update.message is not None and update.effective_user is not None
    memories = list_memories(DB_PATH, update.effective_user.id, limit=5, offset=0)
    if not memories:
        await update.message.reply_text("📭 لا توجد ذكريات بعد.")
        return
    text = "🕒 **أحدث الذكريات**\n\n" + "\n\n".join(_memory_line(m) for m in memories)
    await update.message.reply_text(
        text, reply_markup=_list_keyboard(memories, "all", 0, len(memories))
    )


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search text, caption and tags for a keyword."""
    assert update.message is not None and update.effective_user is not None
    keyword = " ".join(context.args or []).strip()
    if not keyword:
        await update.message.reply_text("🔎 الاستخدام: `/search كلمة` — مثال: `/search سفر`")
        return
    results = search_memories(DB_PATH, update.effective_user.id, keyword, limit=10)
    if not results:
        await update.message.reply_text(f"🔍 لا توجد نتائج لـ «{keyword}».")
        return
    text = f"🔍 نتائج البحث عن «{keyword}» ({len(results)}):\n\n"
    text += "\n\n".join(_memory_line(m) for m in results)
    await update.message.reply_text(
        text, reply_markup=_list_keyboard(results, "all", 0, len(results))
    )


async def get_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show one memory by id: /get <id>."""
    assert update.message is not None and update.effective_user is not None
    args = context.args or []
    if not args or not args[0].isdigit():
        await update.message.reply_text("الاستخدام: `/get رقم` — مثال: `/get 3`")
        return
    memory = get_memory(DB_PATH, int(args[0]), update.effective_user.id)
    if memory is None:
        await update.message.reply_text(f"❌ لا توجد ذكرى بالرقم {args[0]}.")
        return
    await _send_memory(update, context, memory)


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete one memory by id: /delete <id>."""
    assert update.message is not None and update.effective_user is not None
    args = context.args or []
    if not args or not args[0].isdigit():
        await update.message.reply_text("الاستخدام: `/delete رقم` — مثال: `/delete 3`")
        return
    memory_id = int(args[0])
    if delete_memory(DB_PATH, memory_id, update.effective_user.id):
        await update.message.reply_text(f"🗑 تم حذف الذكرى #{memory_id}.")
    else:
        await update.message.reply_text(f"❌ لا توجد ذكرى بالرقم {memory_id}.")


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the SQLite database file as a document (backup)."""
    assert update.message is not None
    db_file = Path(DB_PATH)
    if not db_file.is_file():
        await update.message.reply_text("📭 لا توجد قاعدة بيانات بعد — لا ذكريات محفوظة.")
        return
    await update.message.reply_document(
        document=db_file, caption="💾 نسخة احتياطية من ذكرياتك (memories.db)"
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ask for confirmation before deleting all memories."""
    assert update.message is not None
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ نعم، احذف الكل", callback_data="clear:yes"),
                InlineKeyboardButton("❌ إلغاء", callback_data="clear:no"),
            ]
        ]
    )
    await update.message.reply_text(
        "⚠️ هل أنت متأكد من حذف **كل** ذكرياتك؟ لا يمكن التراجع عن هذا الإجراء.",
        reply_markup=keyboard,
    )


# ------------------------------------------------------------ auto-saving

async def save_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Auto-save any non-command message as a memory."""
    message = update.message
    if message is None or update.effective_user is None or update.effective_chat is None:
        return
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    memory_type: str | None = None
    file_id: str | None = None
    text = ""

    if message.photo:
        memory_type, file_id = "photo", message.photo[-1].file_id
        text = message.caption or ""
    elif message.video:
        memory_type, file_id = "video", message.video.file_id
        text = message.caption or ""
    elif message.document:
        memory_type, file_id = "document", message.document.file_id
        text = message.caption or message.document.file_name or ""
    elif message.voice:
        memory_type, file_id = "voice", message.voice.file_id
        text = message.caption or ""
    elif message.audio:
        memory_type, file_id = "audio", message.audio.file_id
        text = message.caption or message.audio.title or ""
    elif message.animation:
        memory_type, file_id = "animation", message.animation.file_id
        text = message.caption or ""
    elif message.sticker:
        memory_type, file_id = "sticker", message.sticker.file_id
        text = message.sticker.emoji or ""
    elif message.text:
        memory_type, text = "text", message.text
    else:
        return  # unsupported message kind; ignore silently

    try:
        memory = add_memory(
            DB_PATH, user_id=user_id, chat_id=chat_id,
            type=memory_type, file_id=file_id, text=text,
        )
    except (sqlite3.Error, ValueError) as exc:
        logger.exception("Failed to save memory: %s", exc)
        await message.reply_text("❌ حدث خطأ أثناء حفظ الذكرى، حاول مرة أخرى.")
        return

    label = TYPE_LABELS.get(memory.type, memory.type)
    tags = " ".join(f"#{t}" for t in memory.tags)
    reply = f"✅ تم الحفظ! {label} • 🆔 #{memory.id}"
    if tags:
        reply += f"\n{tags}"
    reply += "\nلعرضها: `/get {}` — وللقائمة: `/list`".format(memory.id)
    await message.reply_text(reply)


# --------------------------------------------------------- callbacks

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline-button presses: view, delete, list pages, clear."""
    query = update.callback_query
    if query is None or update.effective_user is None:
        return
    await query.answer()
    data = query.data or ""
    user_id = update.effective_user.id

    if data.startswith("view:"):
        memory_id = int(data.split(":", 1)[1])
        memory = get_memory(DB_PATH, memory_id, user_id)
        if memory is None:
            await query.edit_message_text("❌ هذه الذكرى غير موجودة.")
            return
        await _send_memory(update, context, memory)
    elif data.startswith("del:"):
        memory_id = int(data.split(":", 1)[1])
        if delete_memory(DB_PATH, memory_id, user_id):
            await query.edit_message_text(f"🗑 تم حذف الذكرى #{memory_id}.")
        else:
            await query.edit_message_text(f"❌ لا توجد ذكرى بالرقم {memory_id}.")
    elif data.startswith("list:"):
        _, memory_type, page = data.split(":")
        await _show_list_page(update, context, memory_type, page=int(page))
    elif data == "clear:yes":
        count = delete_all(DB_PATH, user_id)
        await query.edit_message_text(f"🗑 تم حذف كل الذكريات ({count} ذكرى).")
    elif data == "clear:no":
        await query.edit_message_text("❌ تم إلغاء الحذف، ذكرياتك بأمان.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors without crashing the bot."""
    logger.exception("Error while handling update %s: %s", update, context.error)


def main() -> None:
    """Start the bot with polling."""
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN is not set. Put it in .env or the environment."
        )
    init_db(DB_PATH)
    logger.info("Database ready at %s", DB_PATH)

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("recent", recent_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("get", get_command))
    app.add_handler(CommandHandler("delete", delete_command))
    app.add_handler(CommandHandler("export", export_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    # Auto-save everything that is not a command.
    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL
             | filters.VOICE | filters.AUDIO | filters.ANIMATION | filters.Sticker.ALL)
            & ~filters.COMMAND,
            save_message,
        )
    )
    app.add_error_handler(error_handler)

    logger.info("Memory bot started (polling).")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
