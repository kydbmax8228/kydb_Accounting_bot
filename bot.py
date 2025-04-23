import os
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Load .env if running locally (Render 上用環境變數設定)
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # 記得在 Render 上設定這個！

records = []

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

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
        lines.append(f"下发：{len(withdrawals)}  修正：0")
        for r in withdrawals:
            amt = abs(r['amount'])
            lines.append(f"{r['timestamp']} +{amt:.4f}")
        lines.append("-" * 26)
        lines += [
            "预设汇率：1.0000",
            "上笔汇率：1.0000",
            "此笔汇率：1.0000",
            "手续费率：0.0000 %",
            "-" * 26,
        ]
        total_in = sum(r["amount"] for r in deposits)
        total_out = sum(abs(r["amount"]) for r in withdrawals)
        diff = total_in - total_out
        lines += [
            f"已入款(PHP)：{total_in:.4f}",
            f"应下发(PHP)：{total_in:.4f}",
            f"已下发(PHP)：{total_out:.4f}",
            f"未下发(PHP)：{diff:.4f}",
            "-" * 26,
        ]
        if diff != 0:
            lines.append(f"⚠️ 差額異常！你可能漏記入一筆：+{abs(diff):.0f}")
        lines.append("操作：")

        await update.message.reply_text("\n".join(lines))
    else:
        await update.message.reply_text("請輸入正確格式，例如：+123456 或 -50000")

async def webhook(request):
    if request.method == "POST":
        payload = await request.json()
        update = Update.de_json(payload, bot.bot)
        await bot.process_update(update)
        return web.Response(text="OK")
    return web.Response(text="Webhook running!")

from aiohttp import web

app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

bot = app.bot

async def main():
    await bot.set_webhook(url=WEBHOOK_URL)
    logging.info(f"Webhook set to {WEBHOOK_URL}")

    web_app = web.Application()
    web_app.router.add_post("/", webhook)
    web_app.router.add_get("/", webhook)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8000)))
    await site.start()
    logging.info("🚀 Webhook server is running")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
