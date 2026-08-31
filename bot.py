from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import threading
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


# --- 1. خادم ويب وهمي لإرضاء منصة Render ومنع مشكلة No open ports ---
class SimpleHandler(BaseHTTPRequestHandler):

  def do_GET(self):
    self.send_response(200)
    self.end_headers()
    self.wfile.write(b"Telegram AI Bot is running 24/7 successfully!")


def run_web_server():
  port = int(os.getenv("PORT", 10000))
  server = HTTPServer(("0.0.0.0", port), SimpleHandler)
  server.serve_forever()


# تشغيل خادم الويب في الخلفية فوراً
threading.Thread(target=run_web_server, daemon=True).start()
# -----------------------------------------------------------------


# قراءة البيانات بأمان من المتغيرات البيئية في Render
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@Everything_your_mind_needs")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

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


def generate_text_with_gemini(prompt):
  url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
  headers = {"Content-Type": "application/json"}
  data = {"contents": [{"parts": [{"text": prompt}]}]}

  response = requests.post(url, headers=headers, json=data)
  if response.status_code == 200:
    result = response.json()
    try:
      return result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
      raise Exception(f"Unexpected API response structure: {result}")
  else:
    raise Exception(f"Gemini API Error ({response.status_code}): {response.text}")


async def generate_and_send_post():
  day_of_week = datetime.datetime.today().weekday()
  theme = daily_themes.get(day_of_week, "تطوير ذات ومعلومات عامة")

  prompt = f"""
    قم بتأليف منشور قصير، مبتكر، وجذاب جداً لقناة على تلجرام حول الموضوع التالي: '{theme}'.
    الشروط الصارمة:
    1. أن يكون المنشور ثنائي اللغة (النص العربي أولاً، يليه فاصل '---', ثم الترجمة باللغة الإنجليزية).
    2. استخدم رموز تعبيرية (Emojis) جذابة بصرياً.
    3. اجعل الأسلوب مشوقاً ومناسباً لزيادة التفاعل والمشاركة.
    4. لا تضع أي مقدمات أو تعقيبات خارج النص، اكتب المحتوى مباشرة جاهزاً للنشر.
    """

  try:
    print(f"[{datetime.datetime.now()}] Generating post with Gemini...")
    loop = asyncio.get_running_loop()
    message_text = await loop.run_in_executor(
        None, generate_text_with_gemini, prompt
    )

    footer = "\n\n─────────────────\n💡 @Everything_your_mind_needs"
    final_message = message_text + footer

    seed_value = f"{datetime.date.today()}-{datetime.datetime.now().hour}-{datetime.datetime.now().minute}-{datetime.datetime.now().second}"
    image_url = f"https://picsum.photos/seed/{seed_value}/1080/1080"

    print(f"[{datetime.datetime.now()}] Sending post to Telegram channel...")
    async with Bot(token=TELEGRAM_TOKEN) as bot:
      await bot.send_photo(
          chat_id=CHANNEL_ID, photo=image_url, caption=final_message
      )

    print(f"[{datetime.datetime.now()}] ✅ AI Photo Post sent successfully!")

  except Exception as e:
    print(f"❌ Error generating or sending photo post: {e}")


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
  await query.answer()

  if query.data == "force_post":
    await query.edit_message_text(text="⏳ جاري توليد ونشر المنشور في القناة الآن...")
    try:
      await generate_and_send_post()
      await query.edit_message_text(
          text="✅ تم نشر المنشور بنجاح في القناة! يمكنك الضغط على /start للعودة للقائمة."
      )
    except Exception as e:
      await query.edit_message_text(text=f"❌ حدث خطأ أثناء النشر: {e}")

  elif query.data == "status":
    day_of_week = datetime.datetime.today().weekday()
    theme = daily_themes.get(day_of_week, "تطوير ذات")
    status_text = (
        f"🤖 حالة البوت: يعمل بنجاح 24/7\n\n📌 موضوع اليوم: {theme}\n⏰ أوقات النشر"
        " اليومية: 9:00 صباحاً، 3:00 عصراً، و9:00 مساءً (بتوقيت سوريا)\n\nاضغط"
        " على /start للعودة للقائمة الرئيسية."
    )
    await query.edit_message_text(text=status_text)


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
  application = (
      Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
  )

  application.add_handler(CommandHandler("start", start))
  application.add_handler(CallbackQueryHandler(button_handler))

  application.run_polling()


if __name__ == "__main__":
  main()
