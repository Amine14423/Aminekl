#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════╗
║   Cloud Run Fast Bot — aiogram + Colored Buttons         ║
╚══════════════════════════════════════════════════════════╝
"""

import asyncio
import logging
import re
import json
import os
import time
import random
from urllib.parse import unquote
from typing import Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardBuilder,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

# ╔══════════════════════════════════════════════════════════╗
# ║                    ⚙️  الإعدادات                        ║
# ╚══════════════════════════════════════════════════════════╝
TELEGRAM_TOKEN  = os.getenv("TELEGRAM_TOKEN", "8901983423:AAGEgDkiNTp0gGkMiOcKL-b3WKSLSpeenRU")
OWNER_ID        = int(os.getenv("OWNER_ID", "8372270954"))
OWNER_USERNAME  = "@a_mine_Kl"

CHANNEL_1_ID    = "@AmineKl7"
CHANNEL_1_LINK  = "https://t.me/AmineKl7"
CHANNEL_1_NAME  = "𝑳𝒊𝒈𝒉𝒕 𝑪𝒐𝒏𝒇𝒊𝒈"
CHANNEL_2_ID    = "@light_premium_vip"
CHANNEL_2_LINK  = "https://t.me/+JaxuxI8jPT05NmY0"
CHANNEL_2_NAME  = "𝑳𝒊𝒈𝒉𝒕_𝑷𝒓𝒆𝒎𝒊𝒖𝒎"

DOCKER_IMAGE    = "docker.io/aminekl2007/vless-premium:latest"
SERVICE_NAME    = "vless-premium"
COOLDOWN_SEC    = 600

REGIONS = {
    "🇳🇱 Netherlands": "europe-west4",
    "🇩🇪 Frankfurt":   "europe-west3",
    "🇧🇪 Belgium":     "europe-west1",
    "🇮🇹 Italy":       "europe-west8",
    "🇺🇸 Iowa":        "us-central1",
    "🇺🇸 S. Carolina": "us-east1",
}

WAIT_MSGS = [
    "💪 الفوز قريب، ثوانٍ فقط...",
    "🚀 نحن أسرع من المنافسين!",
    "⚡ الـ container يعمل الآن...",
    "🔥 لحظات وتحصل على رابطك...",
    "🏆 البوت الأسرع في المنافسة!",
]

# Custom Emoji IDs للأيقونات الملونة
EMOJI_SUCCESS = "5774022692642492953"   # ✅ أخضر
EMOJI_DANGER  = "5774077015388852135"   # ❌ أحمر
EMOJI_PRIMARY = "6028435952299413210"   # ℹ️ أزرق
EMOJI_DEFAULT = "5771449289972650710"   # ⚙️ رمادي
# ════════════════════════════════════════════════════════════

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

bot            = Bot(token=TELEGRAM_TOKEN)
dp             = Dispatcher()

bot_locked     = False
pending_data   = {}
last_service   = {}
active_task    = {}
cooldown_map   = {}
fastest_region = "europe-west4"
stats          = {"users": set(), "success": 0, "fail": 0, "regions": {}}


# ══════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════

def is_owner(uid: int) -> bool:
    return uid == OWNER_ID

def check_cooldown(uid: int) -> int:
    if is_owner(uid): return 0
    last = cooldown_map.get(uid, 0)
    return max(0, int(COOLDOWN_SEC - (time.time() - last)))

def set_cooldown(uid: int):
    cooldown_map[uid] = time.time()

def extract_from_url(url: str) -> dict:
    decoded = unquote(unquote(url))
    data    = {}
    m = re.search(r'qwiklabs-gcp-\d+-[a-z0-9]+', decoded)
    if m: data['project_id'] = m.group(0)
    m = re.search(r'student-\d+-[a-z0-9]+@qwiklabs\.net', decoded)
    if m: data['username'] = m.group(0)
    m = re.search(r'[?&]token=([A-Za-z0-9_\-]+)', url)
    if m: data['token'] = m.group(1)
    return data

async def check_membership(uid: int) -> bool:
    if is_owner(uid): return True
    try:
        m1 = await bot.get_chat_member(CHANNEL_1_ID, uid)
        m2 = await bot.get_chat_member(CHANNEL_2_ID, uid)
        ok1 = m1.status in ("member", "administrator", "creator")
        ok2 = m2.status in ("member", "administrator", "creator")
        return ok1 and ok2
    except:
        return False


# ══════════════════════════════════════════════════════════
#  لوحات الأزرار
# ══════════════════════════════════════════════════════════

def main_kb(uid: int) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📊 الحالة"),
        KeyboardButton(text="🌍 المناطق"),
    )
    builder.row(
        KeyboardButton(text="❓ مساعدة"),
        KeyboardButton(text="❌ إلغاء"),
    )
    if is_owner(uid):
        builder.row(KeyboardButton(text="👑 لوحة المالك"))
    return builder.as_markup(resize_keyboard=True, persistent=True)

def join_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"📢 {CHANNEL_2_NAME}",
            url=CHANNEL_2_LINK,
            style="primary",
            icon_custom_emoji_id=EMOJI_PRIMARY,
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"📢 {CHANNEL_1_NAME}",
            url=CHANNEL_1_LINK,
            style="primary",
            icon_custom_emoji_id=EMOJI_PRIMARY,
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✅ تحققت من الانضمام",
            callback_data="check_join",
            style="success",
            icon_custom_emoji_id=EMOJI_SUCCESS,
        )
    )
    return builder.as_markup()

def region_kb() -> InlineKeyboardMarkup:
    global fastest_region
    builder = InlineKeyboardBuilder()
    items   = list(REGIONS.items())
    # الأسرع أولاً
    items.sort(key=lambda x: 0 if x[1] == fastest_region else 1)
    for i in range(0, len(items), 2):
        row = []
        for name, code in items[i:i+2]:
            star = "⭐ " if code == fastest_region else ""
            row.append(InlineKeyboardButton(
                text=f"{star}{name}",
                callback_data=f"reg_{code}",
                style="primary",
                icon_custom_emoji_id=EMOJI_PRIMARY,
            ))
        builder.row(*row)
    builder.row(
        InlineKeyboardButton(
            text="🎲 عشوائي",
            callback_data="reg_random",
            style="default",
            icon_custom_emoji_id=EMOJI_DEFAULT,
        ),
        InlineKeyboardButton(
            text="⚡ كل المناطق",
            callback_data="reg_parallel",
            style="success",
            icon_custom_emoji_id=EMOJI_SUCCESS,
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="❌ إلغاء",
            callback_data="reg_cancel",
            style="danger",
            icon_custom_emoji_id=EMOJI_DANGER,
        )
    )
    return builder.as_markup()

def success_kb(uid: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_owner(uid):
        builder.row(
            InlineKeyboardButton(
                text="🔄 إعادة تشغيل",
                callback_data=f"restart_{uid}",
                style="primary",
                icon_custom_emoji_id=EMOJI_PRIMARY,
            ),
            InlineKeyboardButton(
                text="📊 الحالة",
                callback_data=f"status_{uid}",
                style="default",
                icon_custom_emoji_id=EMOJI_DEFAULT,
            ),
        )
    builder.row(
        InlineKeyboardButton(
            text=f"📢 {CHANNEL_2_NAME}",
            url=CHANNEL_2_LINK,
            style="success",
            icon_custom_emoji_id=EMOJI_SUCCESS,
        )
    )
    return builder.as_markup()

def owner_kb(uid: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🔄 إعادة تشغيل",
            callback_data=f"restart_{uid}",
            style="primary",
            icon_custom_emoji_id=EMOJI_PRIMARY,
        ),
        InlineKeyboardButton(
            text="📊 الحالة",
            callback_data=f"status_{uid}",
            style="default",
            icon_custom_emoji_id=EMOJI_DEFAULT,
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="🔒 قفل البوت",
            callback_data="lock_bot",
            style="danger",
            icon_custom_emoji_id=EMOJI_DANGER,
        ),
        InlineKeyboardButton(
            text="🟢 فتح البوت",
            callback_data="unlock_bot",
            style="success",
            icon_custom_emoji_id=EMOJI_SUCCESS,
        ),
    )
    return builder.as_markup()


# ══════════════════════════════════════════════════════════
#  gcloud
# ══════════════════════════════════════════════════════════

async def run_gcloud(cmd: list, env=None, timeout=300) -> tuple:
    try:
        e = env or os.environ.copy()
        e['CLOUDSDK_CORE_DISABLE_PROMPTS'] = '1'
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=e,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return (
            stdout.decode('utf-8', errors='replace').strip(),
            stderr.decode('utf-8', errors='replace').strip(),
            proc.returncode,
        )
    except asyncio.TimeoutError:
        return ("", "timeout", -1)
    except Exception as ex:
        return ("", str(ex), -1)

async def deploy_one(data: dict, region: str) -> Optional[str]:
    project_id = data.get('project_id', '')
    env = os.environ.copy()
    env['CLOUDSDK_CORE_PROJECT']         = project_id
    env['CLOUDSDK_CORE_DISABLE_PROMPTS'] = '1'

    out, err, code = await run_gcloud([
        "gcloud", "run", "deploy", SERVICE_NAME,
        f"--image={DOCKER_IMAGE}",
        "--port=8080", "--min-instances=0", "--max-instances=6",
        "--cpu=2", "--memory=4Gi", "--cpu-boost",
        "--timeout=3600", "--concurrency=1000",
        f"--region={region}", f"--project={project_id}",
        "--allow-unauthenticated", "--quiet", "--format=json",
    ], env=env, timeout=300)

    m = re.search(r'https://[\w\-]+\.run\.app', out + err)
    if m: return m.group(0)
    if code == 0:
        try:
            r = json.loads(out)
            return r.get('status', {}).get('url') or r.get('url')
        except: pass
    return None


# ══════════════════════════════════════════════════════════
#  إشعار المالك
# ══════════════════════════════════════════════════════════

async def notify_owner(uid: int, uname: str, project: str, region: str, url: str, elapsed: float):
    rname = next((k for k, v in REGIONS.items() if v == region), region)
    try:
        await bot.send_message(
            OWNER_ID,
            f"📩 <b>Deploy جديد!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <code>{uid}</code>{' (@'+uname+')' if uname else ''}\n"
            f"🏗️ <code>{project}</code>\n"
            f"🌍 {rname}\n"
            f"⏱️ {elapsed:.0f}s\n"
            f"🚀 <code>{url}</code>",
            parse_mode="HTML",
        )
    except: pass


# ══════════════════════════════════════════════════════════
#  شريط تقدم
# ══════════════════════════════════════════════════════════

async def progress_loop(msg: types.Message, region_name: str, stop_ev: asyncio.Event):
    bars = [
        ("▓▓░░░░░░░░", "20%", "يجهّز الـ container..."),
        ("▓▓▓▓░░░░░░", "40%", "يُحمّل الـ image..."),
        ("▓▓▓▓▓▓░░░░", "60%", "يُشغّل الخدمة..."),
        ("▓▓▓▓▓▓▓▓░░", "80%", "يُعدّ الـ traffic..."),
        ("▓▓▓▓▓▓▓▓▓░", "90%", "لحظات أخيرة..."),
    ]
    for bar, pct, step in bars:
        if stop_ev.is_set(): return
        try:
            await msg.edit_text(
                f"🚀 <b>Deploy في {region_name}</b>\n\n"
                f"<code>{bar} {pct}</code>\n"
                f"📌 {step}\n\n"
                f"💬 {random.choice(WAIT_MSGS)}\n\n"
                f"⏳ عادةً 45-90 ثانية ☕",
                parse_mode="HTML",
            )
        except: pass
        for _ in range(15):
            if stop_ev.is_set(): return
            await asyncio.sleep(1)


# ══════════════════════════════════════════════════════════
#  Deploy منطقة واحدة
# ══════════════════════════════════════════════════════════

async def do_deploy_single(data: dict, region_code: str, region_name: str,
                            chat_id: int, uid: int, uname: str):
    global fastest_region
    t    = time.time()
    sent = await bot.send_message(
        chat_id,
        f"🚀 <b>Deploy في {region_name}</b>\n\n"
        f"<code>▓░░░░░░░░░  0%  يبدأ...</code>\n\n"
        f"⏳ عادةً 45-90 ثانية ☕",
        parse_mode="HTML",
    )
    stop_ev = asyncio.Event()
    prog    = asyncio.create_task(progress_loop(sent, region_name, stop_ev))
    url     = await deploy_one(data, region_code)
    stop_ev.set(); prog.cancel()
    elapsed = time.time() - t

    if url:
        stats["success"] += 1
        stats["regions"][region_code] = stats["regions"].get(region_code, 0) + 1
        fastest_region = max(stats["regions"], key=stats["regions"].get)
        last_service[uid] = {"url": url, "region": region_code, "data": data}
        try:
            await sent.edit_text(
                f"✅ <b>تم! {elapsed:.0f}s</b>\n\n<code>▓▓▓▓▓▓▓▓▓▓ 100%</code>",
                parse_mode="HTML",
            )
        except: pass
        await _send_success(chat_id, uid, url, region_name, elapsed, data)
        await notify_owner(uid, uname, data.get('project_id',''), region_code, url, elapsed)
        set_cooldown(uid)
    else:
        stats["fail"] += 1
        try:
            await sent.edit_text(f"❌ <b>فشل في {region_name} ({elapsed:.0f}s)</b>", parse_mode="HTML")
        except: pass
        await bot.send_message(chat_id,
            f"جرّب ⚡ كل المناطق أو منطقة أخرى\nللمساعدة: {OWNER_USERNAME}")
    active_task.pop(uid, None)


# ══════════════════════════════════════════════════════════
#  Deploy متوازي
# ══════════════════════════════════════════════════════════

async def do_deploy_parallel(data: dict, chat_id: int, uid: int, uname: str):
    global fastest_region
    t    = time.time()
    sent = await bot.send_message(
        chat_id,
        "⚡ <b>نشر متوازي في كل المناطق!</b>\n\n" +
        "\n".join(f"⏳ {n}" for n in REGIONS) +
        "\n\n⏳ عادةً 45-90 ثانية ☕",
        parse_mode="HTML",
    )
    tasks   = {r: asyncio.create_task(deploy_one(data, r)) for r in REGIONS.values()}
    rev     = {v: k for k, v in tasks.items()}
    name_by = {v: k for k, v in REGIONS.items()}
    results = {}
    first_url = first_reg = None

    pending = set(tasks.values())
    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            url = task.result()
            reg = rev[task]
            results[reg] = url
            if url and not first_url:
                first_url = url; first_reg = reg
                for pt in pending: pt.cancel()
                pending = set(); break

        lines = []
        for n, c in REGIONS.items():
            if c == first_reg:      lines.append(f"✅ {n} 🏆")
            elif c in results:      lines.append(f"{'✅' if results[c] else '❌'} {n}")
            else:                   lines.append(f"⏳ {n}")
        try:
            await sent.edit_text("⚡ <b>نشر متوازي</b>\n\n" + "\n".join(lines), parse_mode="HTML")
        except: pass

    elapsed = time.time() - t
    if first_url:
        stats["success"] += 1
        stats["regions"][first_reg] = stats["regions"].get(first_reg, 0) + 1
        fastest_region = max(stats["regions"], key=stats["regions"].get)
        rname = name_by.get(first_reg, first_reg)
        last_service[uid] = {"url": first_url, "region": first_reg, "data": data}
        try:
            await sent.edit_text(
                "⚡ <b>نشر متوازي — اكتمل!</b>\n\n" +
                "\n".join(
                    f"{'🏆' if c==first_reg else ('✅' if results.get(c) else ('❌' if c in results else '⏩'))} {n}"
                    for n, c in REGIONS.items()
                ),
                parse_mode="HTML",
            )
        except: pass
        await _send_success(chat_id, uid, first_url, rname, elapsed, data)
        await notify_owner(uid, uname, data.get('project_id',''), first_reg, first_url, elapsed)
        set_cooldown(uid)
    else:
        stats["fail"] += 1
        await bot.send_message(chat_id,
            f"❌ <b>فشل في كل المناطق ({elapsed:.0f}s)</b>\n"
            f"للمساعدة: {OWNER_USERNAME}", parse_mode="HTML")
    active_task.pop(uid, None)


# ══════════════════════════════════════════════════════════
#  رسالة النجاح
# ══════════════════════════════════════════════════════════

async def _send_success(chat_id: int, uid: int, url: str,
                         region: str, elapsed: float, data: dict):
    await bot.send_message(
        chat_id,
        f"🎉 <b>تم Deploy بنجاح!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🚀 <b>الرابط:</b>\n<code>{url}</code>\n\n"
        f"🌍 <b>المنطقة:</b> {region}\n"
        f"⏱️ <b>الوقت:</b> {elapsed:.0f}s\n"
        f"🏗️ <b>Project:</b> <code>{data.get('project_id','—')}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 للمساعدة: {OWNER_USERNAME}",
        parse_mode="HTML",
        reply_markup=success_kb(uid),
    )


# ══════════════════════════════════════════════════════════
#  إعادة تشغيل
# ══════════════════════════════════════════════════════════

async def restart_service(chat_id: int, uid: int):
    info = last_service.get(uid)
    if not info:
        await bot.send_message(chat_id, "⚠️ لا توجد خدمة سابقة")
        return
    data, region = info['data'], info['region']
    project_id   = data.get('project_id', '')
    env = os.environ.copy()
    env['CLOUDSDK_CORE_PROJECT']         = project_id
    env['CLOUDSDK_CORE_DISABLE_PROMPTS'] = '1'
    await bot.send_message(chat_id, "🔄 <b>إعادة تشغيل...</b>", parse_mode="HTML")
    out, err, code = await run_gcloud([
        "gcloud", "run", "services", "update-traffic", SERVICE_NAME,
        f"--region={region}", f"--project={project_id}", "--to-latest", "--quiet",
    ], env=env, timeout=120)
    rname = next((k for k, v in REGIONS.items() if v == region), region)
    if code == 0:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(
            text="🔄 إعادة تشغيل", callback_data=f"restart_{uid}",
            style="primary", icon_custom_emoji_id=EMOJI_PRIMARY,
        ))
        await bot.send_message(chat_id,
            f"✅ <b>تمت إعادة التشغيل!</b>\n\n🚀 <code>{info['url']}</code>",
            parse_mode="HTML", reply_markup=builder.as_markup())
    else:
        url = await deploy_one(data, region)
        if url:
            last_service[uid]['url'] = url
            await _send_success(chat_id, uid, url, rname, 0, data)
        else:
            await bot.send_message(chat_id,
                f"❌ فشلت إعادة التشغيل\n<code>{err[:200]}</code>", parse_mode="HTML")


# ══════════════════════════════════════════════════════════
#  الأوامر
# ══════════════════════════════════════════════════════════

@dp.message(Command("start"))
async def cmd_start(msg: types.Message):
    uid   = msg.from_user.id
    name  = msg.from_user.first_name or "مستخدم"
    stats["users"].add(uid)
    badge = "👑 " if is_owner(uid) else ""
    await msg.answer(
        f"👋 <b>أهلاً {badge}{name}!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <b>Cloud Run Fast Bot</b>\n\n"
        f"📎 أرسل رابط <code>google_sso</code>\n"
        f"من صفحة Lab في skills.google\n\n"
        f"<b>✅ الميزات:</b>\n"
        f"• استخراج فوري من الرابط\n"
        f"• أزرار ملونة 🎨\n"
        f"• نشر متوازي في كل المناطق\n"
        f"• run.app في أقل وقت ممكن 🚀\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 الدعم: {OWNER_USERNAME}",
        parse_mode="HTML",
        reply_markup=main_kb(uid),
    )

@dp.message(Command("help"))
async def cmd_help(msg: types.Message):
    await msg.answer(
        f"❓ <b>طريقة الاستخدام:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>1️⃣</b> افتح skills.google وابدأ Lab\n\n"
        f"<b>2️⃣</b> اضغط <b>Open Google Cloud Console</b>\n\n"
        f"<b>3️⃣</b> انسخ رابط google_sso الطويل\n\n"
        f"<b>4️⃣</b> أرسله هنا\n\n"
        f"<b>5️⃣</b> اختر المنطقة أو ⚡ كل المناطق\n\n"
        f"<b>6️⃣</b> استلم رابط run.app 🎉\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 اختر ⚡ كل المناطق للأسرع!\n"
        f"💬 الدعم: {OWNER_USERNAME}",
        parse_mode="HTML",
    )

@dp.message(Command("status"))
async def cmd_status(msg: types.Message):
    uid  = msg.from_user.id
    info = last_service.get(uid)
    if not info:
        await msg.answer("📊 <b>لا توجد خدمة نشطة</b>\n\nأرسل رابط google_sso", parse_mode="HTML")
        return
    rname = next((k for k, v in REGIONS.items() if v == info['region']), info['region'])
    kb = None
    if is_owner(uid):
        b = InlineKeyboardBuilder()
        b.row(InlineKeyboardButton(
            text="🔄 إعادة تشغيل", callback_data=f"restart_{uid}",
            style="primary", icon_custom_emoji_id=EMOJI_PRIMARY,
        ))
        kb = b.as_markup()
    await msg.answer(
        f"📊 <b>الخدمة النشطة:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🚀 <code>{info['url']}</code>\n\n"
        f"🌍 {rname}\n"
        f"🏗️ <code>{info['data'].get('project_id','—')}</code>",
        parse_mode="HTML", reply_markup=kb,
    )

@dp.message(Command("regions"))
async def cmd_regions(msg: types.Message):
    lines = "\n".join(
        f"{'⭐ ' if c == fastest_region else ''}{n} → <code>{c}</code>"
        for n, c in REGIONS.items()
    )
    await msg.answer(
        f"🌍 <b>المناطق المتاحة:</b>\n━━━━━━━━━━━━━━━━━━━━━━\n{lines}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n⭐ = الأسرع تاريخياً",
        parse_mode="HTML",
    )

@dp.message(Command("cancel"))
async def cmd_cancel(msg: types.Message):
    uid  = msg.from_user.id
    task = active_task.pop(uid, None)
    if task: task.cancel()
    await msg.answer("❌ <b>تم الإلغاء</b>", parse_mode="HTML")

@dp.message(Command("stats"))
async def cmd_stats(msg: types.Message):
    if not is_owner(msg.from_user.id): return
    best = max(stats["regions"], key=stats["regions"].get) if stats["regions"] else "—"
    bn   = next((k for k, v in REGIONS.items() if v == best), best)
    await msg.answer(
        f"📊 <b>إحصائيات:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 المستخدمون: {len(stats['users'])}\n"
        f"✅ ناجح: {stats['success']}\n"
        f"❌ فاشل: {stats['fail']}\n"
        f"🌍 أسرع منطقة: {bn}\n"
        f"🔒 الحالة: {'مقفل 🔒' if bot_locked else '🟢 مفتوح'}",
        parse_mode="HTML",
    )

@dp.message(Command("lock"))
async def cmd_lock(msg: types.Message):
    global bot_locked
    if not is_owner(msg.from_user.id): return
    bot_locked = True
    await msg.answer("🔒 <b>البوت مقفل</b>", parse_mode="HTML")

@dp.message(Command("unlock"))
async def cmd_unlock(msg: types.Message):
    global bot_locked
    if not is_owner(msg.from_user.id): return
    bot_locked = False
    await msg.answer("🟢 <b>البوت مفتوح</b>", parse_mode="HTML")


# ══════════════════════════════════════════════════════════
#  معالج الرسائل
# ══════════════════════════════════════════════════════════

@dp.message(F.text)
async def handle_message(msg: types.Message):
    uid     = msg.from_user.id
    uname   = msg.from_user.username or ""
    chat_id = msg.chat.id
    text    = msg.text.strip()
    stats["users"].add(uid)

    if text == "📊 الحالة":   return await cmd_status(msg)
    if text == "🌍 المناطق":  return await cmd_regions(msg)
    if text == "❓ مساعدة":   return await cmd_help(msg)
    if text == "❌ إلغاء":    return await cmd_cancel(msg)

    if text == "👑 لوحة المالك" and is_owner(uid):
        info = last_service.get(uid)
        await msg.answer(
            f"👑 <b>لوحة المالك</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 المستخدمون: {len(stats['users'])}\n"
            f"✅ ناجح: {stats['success']} | ❌ فاشل: {stats['fail']}\n"
            f"🔒 {'مقفل' if bot_locked else '🟢 مفتوح'}\n"
            f"🚀 <code>{info['url'] if info else '—'}</code>",
            parse_mode="HTML",
            reply_markup=owner_kb(uid),
        )
        return

    if "google_sso" in text or "skills.google" in text or "qwiklabs" in text:
        if bot_locked and not is_owner(uid):
            await msg.answer(f"🔒 <b>البوت في الصيانة</b>\n{OWNER_USERNAME}", parse_mode="HTML")
            return
        if not await check_membership(uid):
            await msg.answer(
                "⛔ <b>يجب الانضمام للقناتين أولاً!</b>\n\n"
                f"1️⃣ {CHANNEL_2_NAME}\n2️⃣ {CHANNEL_1_NAME}",
                parse_mode="HTML", reply_markup=join_kb(),
            )
            return
        rem = check_cooldown(uid)
        if rem > 0:
            await msg.answer(f"⏳ <b>انتظر {rem//60}د {rem%60}ث</b>", parse_mode="HTML")
            return
        data = extract_from_url(text)
        if not data.get('project_id'):
            await msg.answer(
                f"❌ <b>لم أجد Project ID!</b>\n{OWNER_USERNAME}", parse_mode="HTML")
            return
        pending_data[uid] = data
        await msg.answer(
            f"✅ <b>تم استخراج البيانات!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏗️ <code>{data['project_id']}</code>\n"
            f"👤 <code>{data.get('username','—')}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🌍 <b>اختر المنطقة:</b>\n<i>⭐ = الأسرع تاريخياً</i>",
            parse_mode="HTML",
            reply_markup=region_kb(),
        )
    else:
        await msg.answer(
            f"⚠️ أرسل رابط <code>google_sso</code>\n{OWNER_USERNAME}",
            parse_mode="HTML",
        )


# ══════════════════════════════════════════════════════════
#  معالج الأزرار
# ══════════════════════════════════════════════════════════

@dp.callback_query()
async def handle_callback(cb: types.CallbackQuery):
    uid     = cb.from_user.id
    uname   = cb.from_user.username or ""
    chat_id = cb.message.chat.id
    d       = cb.data
    await cb.answer()

    if d == "check_join":
        if await check_membership(uid):
            await cb.message.edit_text("✅ <b>تم! أرسل الرابط الآن</b>", parse_mode="HTML")
        else:
            await cb.answer("❌ لم تنضم بعد!", show_alert=True)
        return

    if d.startswith("restart_"):
        if not is_owner(uid):
            await cb.answer("⛔ للمالك فقط!", show_alert=True)
            return
        await cb.message.edit_reply_markup(reply_markup=None)
        asyncio.create_task(restart_service(chat_id, uid))
        return

    if d.startswith("status_"):
        if not is_owner(uid):
            await cb.answer("⛔ للمالك فقط!", show_alert=True)
            return
        info = last_service.get(uid)
        await cb.answer(f"🚀 {info['url'][:50] if info else '—'}", show_alert=True)
        return

    if d == "lock_bot":
        if not is_owner(uid):
            await cb.answer("⛔ للمالك فقط!", show_alert=True)
            return
        global bot_locked
        bot_locked = True
        await cb.answer("🔒 تم القفل", show_alert=True)
        return

    if d == "unlock_bot":
        if not is_owner(uid):
            await cb.answer("⛔ للمالك فقط!", show_alert=True)
            return
        bot_locked = False
        await cb.answer("🟢 تم الفتح", show_alert=True)
        return

    if d.startswith("reg_"):
        data = pending_data.get(uid)
        if not data:
            await cb.message.edit_text("⚠️ انتهت الجلسة، أرسل الرابط مجدداً")
            return
        choice = d[4:]
        if choice == "cancel":
            await cb.message.edit_text("❌ <b>تم الإلغاء</b>", parse_mode="HTML")
            return
        if choice == "parallel":
            await cb.message.edit_text(
                f"⚡ <b>نشر متوازي!</b>\n🏗️ <code>{data['project_id']}</code>",
                parse_mode="HTML",
            )
            t = asyncio.create_task(do_deploy_parallel(data, chat_id, uid, uname))
            active_task[uid] = t
            return
        if choice == "random":
            rc = random.choice(list(REGIONS.values()))
            rn = next(k for k, v in REGIONS.items() if v == rc)
        else:
            rc = choice
            rn = next((k for k, v in REGIONS.items() if v == rc), rc)
        await cb.message.edit_text(
            f"🌍 <b>{rn}</b>\n🏗️ <code>{data['project_id']}</code>\n\n⏳ جاري...",
            parse_mode="HTML",
        )
        t = asyncio.create_task(do_deploy_single(data, rc, rn, chat_id, uid, uname))
        active_task[uid] = t


# ══════════════════════════════════════════════════════════
#  تشغيل
# ══════════════════════════════════════════════════════════

async def main():
    log.info("⚡ Cloud Run Fast Bot — aiogram + Colored Buttons")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
