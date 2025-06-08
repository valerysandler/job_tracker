import os
from dotenv import load_dotenv
load_dotenv()
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
import sqlite3
import datetime

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

COMPANY, LINK, STATUS = range(3)

def init_db():
    conn = sqlite3.connect("applications.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS applications (
                 id INTEGER PRIMARY KEY,
                 user_id INTEGER,
                 company TEXT,
                 link TEXT,
                 date TEXT,
                 status TEXT)''')
    conn.commit()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_menu(update.message, context)

async def show_menu(message, context):
    keyboard = [
        [
            InlineKeyboardButton("➕ Add", callback_data="add"),
            InlineKeyboardButton("📄 All Applications", callback_data="list")
        ],
        [InlineKeyboardButton("📊 Statistics", callback_data="stats")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text("📋 Main Menu:", reply_markup=reply_markup)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_menu(update.message, context)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "list":
        await list_entries_query(query, context)
    elif query.data == "stats":
        await show_stats(query, context)

async def handle_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await add(query, context)

async def list_entries_query(query, context):
    user_id = query.from_user.id
    conn = sqlite3.connect("applications.db")
    c = conn.cursor()
    c.execute("SELECT company, link, date, status FROM applications WHERE user_id=?", (user_id,))
    rows = c.fetchall()
    conn.close()

    if not rows:
        await query.message.reply_text("No records yet.")
        return

    message = "📄 Your Applications:\n"
    for company, link, date, status in rows:
        message += f"\n<b>{company}</b> ({date})\n{link}\n<i>Status:</i> <i>{status}</i>\n"
    await query.message.reply_text(message, parse_mode="HTML")

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("Enter the company name:")
    else:
        await update.reply_text("Enter the company name:")
    return COMPANY

async def add_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['company'] = update.message.text
    await update.message.reply_text("Paste the job link:")
    return LINK

async def add_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['link'] = update.message.text
    keyboard = [
        [
            InlineKeyboardButton("Waiting", callback_data="status_waiting"),
            InlineKeyboardButton("Interview", callback_data="status_interview")
        ],
        [
            InlineKeyboardButton("Rejected", callback_data="status_rejected"),
            InlineKeyboardButton("Offer", callback_data="status_offer")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select the status:", reply_markup=reply_markup)
    return STATUS

async def add_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        status = query.data.replace("status_", "")
        user_id = query.from_user.id
        message = query.message
    else:
        status = update.message.text.lower()
        user_id = update.effective_user.id
        message = update.message

    company = context.user_data.get('company')
    link = context.user_data.get('link')
    date = datetime.date.today().isoformat()

    conn = sqlite3.connect("applications.db")
    c = conn.cursor()
    c.execute("INSERT INTO applications (user_id, company, link, date, status) VALUES (?, ?, ?, ?, ?)",
              (user_id, company, link, date, status))
    conn.commit()
    conn.close()

    await message.reply_text(f"✅ Added: {company} — status: {status}")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Cancelled.")
    return ConversationHandler.END

async def list_entries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await list_entries_query(update.message, context)

async def show_stats(query, context):
    user_id = query.from_user.id
    conn = sqlite3.connect("applications.db")
    c = conn.cursor()
    c.execute("SELECT status, COUNT(*) FROM applications WHERE user_id=? GROUP BY status", (user_id,))
    stats = c.fetchall()
    conn.close()

    if not stats:
        await query.message.reply_text("No data available.")
        return

    message = "📊 Stats by Status:\n"
    for status, count in stats:
        message += f"- {status}: {count}\n"
    await query.message.reply_text(message)

def main():
    init_db()
    application = Application.builder().token(os.getenv("BOT_TOKEN")).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("add", add),
            CallbackQueryHandler(handle_add, pattern="^add$")
        ],
        states={
            COMPANY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_company)],
            LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_link)],
            STATUS: [CallbackQueryHandler(add_status, pattern="^status_"), MessageHandler(filters.TEXT & ~filters.COMMAND, add_status)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CommandHandler("list", list_entries))
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^(list|stats)$"))
    application.add_handler(conv_handler)

    application.run_polling()

if __name__ == "__main__":
    main()
