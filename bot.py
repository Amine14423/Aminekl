import os
import re
import asyncio
import random
import logging
from io import BytesIO
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
from playwright.async_api import async_playwright, Page

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


# ─── Screenshot Helper ───────────────────────────────────────────────────────

async def send_screenshot(page: Page, bot, chat_id: int, caption: str = ""):
    """Take screenshot and send to user."""
    try:
        screenshot = await page.screenshot(full_page=False)
        await bot.send_photo(
            chat_id=chat_id,
            photo=BytesIO(screenshot),
            caption=f"📸 {caption}" if caption else "📸 لقطة حية"
        )
    except Exception as e:
        logger.error(f"Screenshot error: {e}")


async def screenshot_loop(page: Page, bot, chat_id: int, stop_event: asyncio.Event):
    """Send screenshot every 2 seconds until stop_event is set."""
    while not stop_event.is_set():
        await send_screenshot(page, bot, chat_id)
        await asyncio.sleep(2)


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

async def deploy_with_browser(
    info: dict,
    region_code: str,
    region_name: str,
    bot,
    chat_id: int,
) -> str:
    """Open browser, login via Qwiklabs SSO, open Cloud Shell, run gcloud deploy."""

    gcloud_cmd = (
        f"gcloud run deploy cloudx "
        f"--image {CONTAINER_IMAGE} "
        f"--region {region_code} "
        f"--memory 4Gi "
        f"--cpu 2 "
        f"--max-instances 6 "
        f"--timeout 3600 "
        f"--project {info['project_id']} "
        f"--allow-unauthenticated "
        f"--port 8080"
    )

    stop_event = asyncio.Event()
    service_url = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        )
        page = await context.new_page()

        # Start screenshot loop in background
        screenshot_task = asyncio.create_task(
            screenshot_loop(page, bot, chat_id, stop_event)
        )

        try:
            # Step 1: Open Qwiklabs SSO URL
            await send_screenshot(page, bot, chat_id, "🔐 فتح رابط Qwiklabs...")
            await page.goto(info["original_url"], wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)
            await send_screenshot(page, bot, chat_id, "✅ تم فتح رابط Qwiklabs")

            # Step 2: Check if logged in or need sign in
            current_url = page.url
            if "accounts.google.com" in current_url or "signin" in current_url:
                await send_screenshot(page, bot, chat_id, "🔑 تسجيل الدخول...")
                # Fill email
                await page.fill('input[type="email"]', info["email"])
                await page.click('button:has-text("Next")')
                await asyncio.sleep(2)
                await send_screenshot(page, bot, chat_id, "📧 تم إدخال الإيميل")

            # Step 3: Wait for Google Console
            await page.wait_for_url("**/console.cloud.google.com/**", timeout=20000)
            await asyncio.sleep(2)
            await send_screenshot(page, bot, chat_id, "✅ تم الدخول لـ Google Console")

            # Step 4: Open Cloud Shell
            shell_url = (
                f"https://shell.cloud.google.com/"
                f"?project={info['project_id']}&show=terminal"
            )
            await page.goto(shell_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(5)
            await send_screenshot(page, bot, chat_id, "🖥️ فتح Cloud Shell...")

            # Step 5: Handle Authorize dialog
            try:
                authorize_btn = page.locator('button:has-text("Authorize")')
                if await authorize_btn.is_visible(timeout=8000):
                    await authorize_btn.click()
                    await asyncio.sleep(3)
                    await send_screenshot(page, bot, chat_id, "✅ تم الضغط على Authorize")
            except Exception:
                await send_screenshot(page, bot, chat_id, "ℹ️ لا يوجد Authorize dialog")

            # Step 6: Wait for terminal to be ready
            await asyncio.sleep(8)
            await send_screenshot(page, bot, chat_id, "⏳ انتظار جهوزية Terminal...")

            # Step 7: Find terminal and type command
            # Try clicking on terminal area
            try:
                terminal = page.locator(".terminal, .xterm, [class*='terminal']").first
                await terminal.click()
            except Exception:
                await page.keyboard.press("Escape")

            await asyncio.sleep(2)

            # Type the gcloud command
            await page.keyboard.type(gcloud_cmd)
            await send_screenshot(page, bot, chat_id, "⌨️ تم كتابة الأمر...")
            await page.keyboard.press("Enter")
            await send_screenshot(page, bot, chat_id, "🚀 بدأ النشر...")

            # Step 8: Wait for deployment (up to 3 minutes)
            await asyncio.sleep(10)

            for i in range(17):  # ~3 minutes total
                await asyncio.sleep(10)
                # Check terminal output for service URL
                try:
                    content = await page.content()
                    url_match = re.search(
                        r"Service URL:\s*(https://[a-z0-9\-\.run\.app]+)",
                        content
                    )
                    if url_match:
                        service_url = url_match.group(1)
                        await send_screenshot(page, bot, chat_id, f"🎉 تم النشر! {service_url}")
                        break

                    # Check for errors
                    if "ERROR" in content and i > 2:
                        await send_screenshot(page, bot, chat_id, "❌ يبدو وجود خطأ!")
                        break
                except Exception:
                    pass

            if not service_url:
                await send_screenshot(page, bot, chat_id, "⏳ انتهى الوقت، جاري التحقق...")

        except Exception as e:
            logger.error(f"Browser error: {e}")
            await send_screenshot(page, bot, chat_id, f"❌ خطأ: {str(e)[:100]}")

        finally:
            stop_event.set()
            await screenshot_task
            await browser.close()

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
        f"📸 سيتم إرسال صور مباشرة كل ثانيتين"
    )

    bot = context.bot
    chat_id = query.message.chat_id

    service_url = await deploy_with_browser(info, region_code, region_name, bot, chat_id)

    if service_url:
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"🎉 تم النشر بنجاح!\n\n"
                f"🚀 رابط خدمة Cloud Run:\n{service_url}\n\n"
                f"📍 المنطقة: {region_name}"
            )
        )
    else:
        await bot.send_message(
            chat_id=chat_id,
            text="❌ لم يتم الحصول على الرابط، تحقق من الصور أعلاه."
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
