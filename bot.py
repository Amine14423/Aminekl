import os
import re
import asyncio
import random
import logging
import subprocess
from urllib.parse import unquote
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")

WAITING_LINK = 1
WAITING_REGION = 2

REGIONS = {
    "🇺🇸 Iowa": "us-central1",
    "🇺🇸 S. Carolina": "us-east1",
    "🇩🇪 Frankfurt": "europe-west3",
    "🇳🇱 Netherlands": "europe-west4",
    "🇮🇹 Italy": "europe-west8",
    "🇧🇪 Belgium": "europe-west1",
}

CONTAINER_IMAGE = "docker.io/amerdouidi/cloudx:latest"


# ─── URL Parser ──────────────────────────────────────────────────────────────

def extract_from_url(url: str) -> dict:
    decoded = unquote(url)
    token_match = re.search(r"[?&]token=([A-Za-z0-9_\-]+)", decoded)
    project_match = re.search(r"project[=%3D]+([a-z0-9\-]+)", decoded)
    email_match = re.search(r"Email[=%3D]+([a-zA-Z0-9@.\-]+)", decoded)
    return {
        "token": token_match.group(1) if token_match else None,
        "project_id": project_match.group(1) if project_match else None,
        "email": unquote(email_match.group(1)) if email_match else None,
        "original_url": url,
    }


# ─── Deploy Logic ────────────────────────────────────────────────────────────

async def run_command(cmd: str) -> tuple[int, str, str]:
    """Run shell command asynchronously and return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode(), stderr.decode()


async def deploy_with_gcloud(
    info: dict,
    region_code: str,
    region_name: str,
    bot,
    chat_id: int,
) -> str:
    """Authenticate with gcloud token and deploy to Cloud Run."""

    service_url = None

    # ── Step 1: Set access token ──────────────────────────────────────────────
    await bot.send_message(chat_id=chat_id, text="🔑 جاري تفعيل التوكن...")

    rc, out, err = await run_command(
    f"gcloud auth activate-refresh-token {info['email']} {info['token']}"
    )
    if rc != 0:
        await bot.send_message(chat_id=chat_id, text=f"❌ فشل تفعيل التوكن:\n{err[:300]}")
        return None

    await bot.send_message(chat_id=chat_id, text="✅ تم تفعيل التوكن")

    # ── Step 2: Set project ───────────────────────────────────────────────────
    rc, out, err = await run_command(
        f"gcloud config set project {info['project_id']}"
    )
    if rc != 0:
        await bot.send_message(chat_id=chat_id, text=f"❌ فشل تعيين المشروع:\n{err[:300]}")
        return None

    await bot.send_message(chat_id=chat_id, text=f"✅ تم تعيين المشروع: `{info['project_id']}`")

    # ── Step 3: Enable Cloud Run API ──────────────────────────────────────────
    await bot.send_message(chat_id=chat_id, text="⚙️ تفعيل Cloud Run API...")

    await run_command(
        f"gcloud services enable run.googleapis.com --project {info['project_id']}"
    )

    # ── Step 4: Deploy ────────────────────────────────────────────────────────
    await bot.send_message(
        chat_id=chat_id,
        text=(
            f"🚀 بدأ النشر على {region_name}...\n"
            f"⏳ قد يستغرق 2-3 دقائق"
        )
    )

    deploy_cmd = (
        f"gcloud run deploy cloudx "
        f"--image {CONTAINER_IMAGE} "
        f"--region {region_code} "
        f"--memory 4Gi "
        f"--cpu 2 "
        f"--max-instances 6 "
        f"--timeout 3600 "
        f"--project {info['project_id']} "
        f"--allow-unauthenticated "
        f"--port 8080 "
        f"--quiet"
    )

    rc, out, err = await run_command(deploy_cmd)

    combined = out + err

    # ── Step 5: Extract service URL ───────────────────────────────────────────
    url_match = re.search(
        r"Service URL:\s*(https://[a-z0-9\-\.run\.app/]+)",
        combined
    )

    if url_match:
        service_url = url_match.group(1).strip()
        await bot.send_message(
            chat_id=chat_id,
            text=f"🎉 تم النشر بنجاح!\n🔗 {service_url}"
        )
    else:
        # Show last part of output to help debug
        output_preview = combined[-800:] if len(combined) > 800 else combined
        await bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ انتهى النشر لكن لم يُعثر على الرابط.\n\n📄 المخرجات:\n```\n{output_preview}\n```",
            parse_mode="Markdown"
        )

    return service_url


# ─── Telegram Handlers ───────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "👋 أهلاً!\n\n"
        "📎 أرسل رابط Qwiklabs الخاص بك:"
    )
    return WAITING_LINK


async def receive_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    url = update.message.text.strip()
    info = extract_from_url(url)

    if not info.get("token") or not info.get("project_id"):
        await update.message.reply_text("❌ الرابط غير صحيح، أرسل رابط Qwiklabs صحيح.")
        return WAITING_LINK

    context.user_data["info"] = info
    await update.message.reply_text(
        f"✅ تم استخراج المعلومات!\n"
        f"📋 Project: `{info['project_id']}`\n"
        f"📧 Email: `{info['email']}`",
        parse_mode="Markdown",
    )

    # Build region keyboard
    keyboard = []
    row = []
    for name in REGIONS:
        row.append(InlineKeyboardButton(name, callback_data=name))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🎲 عشوائي", callback_data="random")])
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel")])

    await update.message.reply_text(
        "🌍 اختر المنطقة:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return WAITING_REGION


async def receive_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    choice = query.data
    if choice == "cancel":
        await query.edit_message_text("❌ تم الإلغاء.")
        return ConversationHandler.END

    if choice == "random":
        region_name = random.choice(list(REGIONS.keys()))
    else:
        region_name = choice

    region_code = REGIONS[region_name]
    info = context.user_data.get("info", {})

    await query.edit_message_text(
        f"⏳ جاري النشر على {region_name}...\n"
        f"📡 سيتم إرسال تحديثات نصية"
    )

    bot = context.bot
    chat_id = query.message.chat_id

    service_url = await deploy_with_gcloud(info, region_code, region_name, bot, chat_id)

    if service_url:
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"✅ *تم النشر بنجاح!*\n\n"
                f"🚀 رابط خدمة Cloud Run:\n{service_url}\n\n"
                f"📍 المنطقة: {region_name}"
            ),
            parse_mode="Markdown"
        )
    else:
        await bot.send_message(
            chat_id=chat_id,
            text="❌ لم يتم الحصول على الرابط، راجع الرسائل أعلاه."
        )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ تم الإلغاء.")
    return ConversationHandler.END


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_link)],
            WAITING_REGION: [CallbackQueryHandler(receive_region)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv)
    logger.info("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()
