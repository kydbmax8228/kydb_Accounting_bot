import os
import logging
from datetime import datetime
import sqlite3
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from aiohttp import web

# 加載環境變數
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
PORT = int(os.getenv("PORT", 8000))

# 環境變數檢查
assert BOT_TOKEN, "❌ 請設定 BOT_TOKEN 環境變數"
assert RENDER_EXTERNAL_URL, "❌ 請設定 RENDER_EXTERNAL_URL 環境變數"

# 設置日誌
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 初始化應用
app = Application.builder().token(BOT_TOKEN).build()
bot = app.bot

# 資料庫設置
DB_PATH = "accounting.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount INTEGER,
        timestamp TEXT,
        date TEXT
    )
    ''')
    conn.commit()
    conn.close()

def add_record(amount, timestamp, date):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO records (amount, timestamp, date) VALUES (?, ?, ?)",
        (amount, timestamp, date)
    )
    conn.commit()
    conn.close()

def get_today_records(date):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM records WHERE date = ? ORDER BY timestamp",
        (date,)
    )
    records = [{"amount": r[1], "timestamp": r[2], "date": r[3]} for r in cursor.fetchall()]
    conn.close()
    return records

# 命令處理器
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! 傳送 + 或 - 加數字 就可以記帳喔～")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("+") or text.startswith("-"):
        try:
            amount = int(text)
        except ValueError:
            await update.message.reply_text("格式錯誤，請輸入 + 或 - 開頭的整數金額")
            return

        now = datetime.now()
        timestamp = now.strftime("%H:%M")
        date = now.strftime("%Y-%m-%d")
        
        # 添加記錄到資料庫
        add_record(amount, timestamp, date)
        
        # 獲取今日記錄
        today_records = get_today_records(date)
        deposits = [r for r in today_records if r["amount"] > 0]
        withdrawals = [r for r in today_records if r["amount"] < 0]

        lines = [f"自定-PHP-PHP {date}"]
        lines.append(f"入款：{len(deposits)}  修正：0")
        for r in deposits:
            lines.append(f"{r['timestamp']} +{r['amount']}/1={r['amount']:.4f}")
        lines.append("-" * 26)
        lines.append(f"下发：{len(withdrawals)}  修正：0")
        for r in withdrawals:
            amt = abs(r['amount'])
            lines.append(f"{r['timestamp']} +{amt:.4f}")
        lines.append("-" * 26)
        total_in = sum(r["amount"] for r in deposits)
        total_out = sum(abs(r["amount"]) for r in withdrawals)
        diff = total_in - total_out
        lines += [f"已入款(PHP)：{total_in:.4f}", f"应下发(PHP)：{total_in:.4f}", f"已下发(PHP)：{total_out:.4f}", f"未下发(PHP)：{diff:.4f}", "-" * 26]
        if diff != 0:
            lines.append(f"⚠️ 差額異常！你可能漏記入一筆：+{abs(diff):.0f}")
        lines.append("操作：")
        await update.message.reply_text("\n".join(lines))
    else:
        await update.message.reply_text("請輸入正確格式，例如：+123456 或 -50000")

# Webhook 處理
async def telegram_webhook(request):
    if request.method == "POST":
        try:
            data = await request.json()
            update = Update.de_json(data, bot)
            await app.update_queue.put(update)
            return web.Response(text="ok")
        except Exception as e:
            logger.error(f"處理webhook時出錯: {e}")
            return web.Response(status=500, text="Error processing update")
    return web.Response(text="Running")

async def setup_webhook():
    webhook_path = f"/webhook/{BOT_TOKEN}"
    full_webhook_url = f"{RENDER_EXTERNAL_URL}{webhook_path}"
    
    # 刪除任何現有webhook
    await bot.delete_webhook()
    
    # 設置新webhook
    await bot.set_webhook(full_webhook_url)
    logger.info(f"✅ Webhook設置成功: {full_webhook_url}")
    
    # 設置web應用
    aio_app = web.Application()
    aio_app.router.add_post(webhook_path, telegram_webhook)
    aio_app.router.add_get("/", lambda _: web.Response(text="👋 Webhook running"))
    
    # 啟動web服務器
    runner = web.AppRunner(aio_app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
    await site.start()
    logger.info(f"🚀 服務器正在運行，端口: {PORT}")

# 主函數
async def main():
    # 初始化資料庫
    init_db()
    
    # 設置命令處理器
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # 初始化應用
    await app.initialize()
    await app.start()
    
    # 設置webhook
    await setup_webhook()
    
    # 保持程序運行
    import asyncio
    try:
        await asyncio.Future()
    finally:
        await app.stop()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())