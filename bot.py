import os
import asyncio
import datetime
from datetime import timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)
import requests

# قراءة المتغيرات البيئية من Render
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@Everything_your_mind_needs")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# جدول المواضيع اليومية
daily_themes = {
    0: "حقيقة علمية أو نفسية مدهشة وغريبة",
    1: "حيلة تقنية أو اختصار ذكي للهواتف أو الحواسيب",
    2: "نصيحة سريعة حول المال، العمل الحر، وعقلية الثراء",
    3: "لغز ذكي وبصري شيق يتفاعل معه المتابعون",
    4: "اقتباس عميق وراقي حول التطوير الذاتي وتحقيق النجاح",
    5: "أداة أو أمر ذكاء اصطناعي (AI Prompt) مفيد جداً",
    6: "قصة تاريخية قصيرة، غامضة ومشوّقة",
}


async def generate_and_send_post():
  day_of_week = datetime.datetime.today().weekday()
  theme = daily_themes.get(day_of_week, "تطوير ذات ومعلومات عامة")

  prompt = f"""
    قم بتأليف منشور قصير جداً، مبتكر، وجذاب جداً لقناة على تلجرام حول الموضوع التالي: '{theme}'.
    الشروط الصارمة:
    1. أن يكون المنشور ثنائي اللغة (النص العربي أولاً، يليه فاصل '---', ثم الترجمة باللغة الإنجليزية).
    2. ألا يتجاوز طول النص بالكامل 600 حرف لكي يناسب وصف الصورة في تيليجرام بدقة.
    3. استخدم رموز تعبيرية (Emojis) جذابة.
    4. لا تضع أي مقدمات، اكتب المحتوى مباشرة.
    """

  try:
    print(f"[{datetime.datetime.now()}] Generating post with Gemini...")
    loop = asyncio.get_running_loop()
    message_text = await loop.run_in_executor(
        None, generate_text_with_gemini, prompt
    )

    # تقصير النص بقوة لضمان عدم تجاوز حد تيليجرام
    if len(message_text) > 650:
      message_text = message_text[:650] + "..."

    footer = "\n\n─────────────────\n💡 @Everything_your_mind_needs"
    final_message = message_text + footer

    seed_value = f"{datetime.date.today()}-{datetime.datetime.now().hour}-{datetime.datetime.now().minute}-{datetime.datetime.now().second}"
    image_url = f"https://picsum.photos/seed/{seed_value}/1080/1080"

    print(f"[{datetime.datetime.now()}] Downloading image...")
    # تحميل الصورة أولاً لتفادي خطأ تيليجرام مع الروابط
    image_response = requests.get(image_url, timeout=15)
    image_bytes = image_response.content

    print(f"[{datetime.datetime.now()}] Sending post to Telegram channel...")
    async with Bot(token=TELEGRAM_TOKEN) as bot:
      await bot.send_photo(
          chat_id=CHANNEL_ID, photo=image_bytes, caption=final_message
      )

    print(f"[{datetime.datetime.now()}] ✅ AI Photo Post sent successfully!")

  except Exception as e:
    print(f"❌ Error generating or sending photo post: {e}")
    raise e


# --- أوامر لوحة التحكم التفاعلية ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
  keyboard = [
      [InlineKeyboardButton("🚀 نشر منشور الآن في القناة", callback_data="force_post")],
      [InlineKeyboardButton("📊 حالة البوت وموضوع اليوم", callback_data="status")],
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)
  await update.message.reply_text(
      "أهلاً بك يا فادي في لوحة تحكم بوت قناتك! 🤖\nاختر الإجراء الذي تريده:",
      reply_markup=reply_markup,
  )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  try:
    await query.answer()
  except Exception:
    pass

  if query.data == "force_post":
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="⏳ جاري توليد ونشر المنشور في القناة الآن...",
    )
    try:
      await generate_and_send_post()
      await context.bot.send_message(
          chat_id=query.message.chat_id,
          text="✅ تم نشر المنشور بنجاح في القناة!",
      )
    except Exception as e:
      await context.bot.send_message(
          chat_id=query.message.chat_id, text=f"❌ حدث خطأ أثناء النشر: {e}"
      )

  elif query.data == "status":
    day_of_week = datetime.datetime.today().weekday()
    theme = daily_themes.get(day_of_week, "تطوير ذات")
    status_text = (
        f"🤖 حالة البوت: يعمل بنجاح 24/7\n\n📌 موضوع اليوم: {theme}\n⏰ أوقات النشر"
        " اليومية: 9:00 صباحاً، 3:00 عصراً، و9:00 مساءً (بتوقيت سوريا)"
    )
    await context.bot.send_message(
        chat_id=query.message.chat_id, text=status_text
    )


# بدء الجدولة عند تشغيل التطبيق
async def post_init(application: Application):
  syria_tz = timezone(timedelta(hours=3))
  scheduler = AsyncIOScheduler(timezone=syria_tz)
  scheduler.add_job(generate_and_send_post, "cron", hour="9,15,21", minute=0)
  scheduler.start()
  print(
      "🤖 AI Bot & Scheduler are running 24/7 for @Everything_your_mind_needs..."
  )


def main():
  if not TELEGRAM_TOKEN:
    print("Error: TELEGRAM_TOKEN is missing!")
    return

  port = int(os.getenv("PORT", 10000))
  application = (
      Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
  )

  application.add_handler(CommandHandler("start", start))
  application.add_handler(CallbackQueryHandler(button_handler))

  webhook_path = TELEGRAM_TOKEN
  full_webhook_url = (
      f"{WEBHOOK_URL.rstrip('/')}/{webhook_path}" if WEBHOOK_URL else None
  )

  print(f"🚀 Starting bot on port {port} using Webhook...")
  application.run_webhook(
      listen="0.0.0.0",
      port=port,
      url_path=webhook_path,
      webhook_url=full_webhook_url,
  )


if __name__ == "__main__":
  main()
