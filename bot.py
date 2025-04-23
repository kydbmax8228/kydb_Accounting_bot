import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)
from aiohttp import web

# --- 環境設定 ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
assert BOT_TOKEN, "❌ 請設定 BOT_TOKEN 環境變數"
assert RENDER_EXTERNAL_URL, "❌ 請設定 RENDER_EXTERNAL_URL 環境變數"

# --- 紀錄記帳資料 ---
records = []

# --- Logging ---
logging.basicConfig(level=logging.INFO)

# --- 初始化 Telegram Bot ---
app = Application.builder().token(BOT_TOKEN).build()
bot = app.bot

# --- 指令與訊息處理 ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! 傳送 + 或 - 加數字 就可以記帳喔～")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global records
    text = update.message.text.strip()

    if text.startswith("+") or text.startswith("-"):
        try:
            amount = int(text)
        except ValueError:
            await update.message.reply_text("格式錯誤，請輸入 + 或 - 開頭的整數金額")
            return

        now = datetime.now()
        record = {
            "amount": amount,
            "timestamp": now.strftime("%H:%M"),
            "date": now.strftime("%Y-%m-%d"),
        }
        records.append(record)

        today_str = now.strftime("%Y-%m-%d")
        today_records = [r for r in records if r["date"] == today_str]
        deposits = [r for r in today_records if r["amount"] > 0]
        withdrawals = [r for r in today_records if r["amount"] < 0]

        lines = [f"自定-PHP-PHP {today_str}"]
        lines.append(f"入款：{len(deposits)}  修正：0")
        for r in deposits:
            amt = r['amount']
            lines.append(f"{r['timestamp']} +{amt}/1={amt:.4f}")
        lines.append("-" * 26)
        lines.append(f"下發：{len(withdrawals)}  修正：0")
        for r in withdrawals:
            amt = abs(r['amount'])
            lines.append(f"{r['timestamp']} +{amt:.4f}")
        lines.append("-" * 26)
        lines += [
            "預設匯率：1.0000",
            "上筆匯率：1.0000",
            "此筆匯率：1.0000",
            "手續費率：0.0000 %",
            "-" * 26,
        ]
        total_in = sum(r["amount"] for r in deposits)
        total_out = sum(abs(r["amount"]) for r in withdrawals)
        diff = total_in - total_out
        lines += [
            f"已入款(PHP)：{total_in:.4f}",
            f"應下發(PHP)：{total_in:.4f}",
            f"已下發(PHP)：{total_out:.4f}",
            f"未下發(PHP)：{diff:.4f}",
            "-" * 26,
        ]
        if diff != 0:
            lines.append(f"⚠️ 差額異常！你可能漏記入一筆：+{abs(diff):.0f}")
        lines.append("操作：")

        await update.message.reply_text("\n".join(lines))
    else:
        await update.message.reply_text("請輸入正確格式，例如：+123456 或 -50000")

# --- Webhook 處理器 ---
async def telegram_webhook(request):
    if request.method == "POST":
        data = await request.json()
        update = Update.de_json(data, bot)
        await app.update_queue.put(update)
        return web.Response(text="ok")
    return web.Response(text="Running")

# --- 啟動 aiohttp server ---
async def start_web_app():
    webhook_path = f"/webhook/{BOT_TOKEN}"
    full_webhook_url = f"{RENDER_EXTERNAL_URL}{webhook_path}"
    await bot.set_webhook(full_webhook_url)
    logging.info(f"✅ Webhook set: {full_webhook_url}")

    aio_app = web.Application()
    aio_app.router.add_post(webhook_path, telegram_webhook)
    aio_app.router.add_get("/", lambda _: web.Response(text="👋 Webhook running"))
    runner = web.AppRunner(aio_app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
    await site.start()
    logging.info("🚀 Server is ready and listening.")

# --- 主程式 ---
if __name__ == "__main__":
    import asyncio

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    async def run():
        await start_web_app()
        await app.initialize()
        await app.start()
        await app.updater.start_polling()  # webhook 模式也需要這行以處理內部位列

    asyncio.run(run())
