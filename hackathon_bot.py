"""
Hackathon Tracker - Telegram Bot (v3, sab kuch buttons se)
Setup:  pip install "python-telegram-bot[job-queue]"
Run:    python hackathon_bot.py
"""

import calendar
import json
import os
import asyncio
from datetime import date, datetime
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ---------- SETTINGS ----------
TOKEN = os.getenv("BOT_TOKEN", "8949949794:AAFGaqX-whXjt3VkZxLu6eZjI7tZT8HV0ys")
IST = ZoneInfo("Asia/Kolkata")
DATA_FILE = "hackathons.json"
DEFAULT_REMINDERS = [7, 3, 1, 0]  # kitne din pehle yaad dilana hai (0 = usi din)
DEFAULT_HOUR = 9  # roz subah 9 baje

DAY_OPTIONS = [(14, "14 din"), (7, "7 din"), (3, "3 din"), (1, "1 din"), (0, "Usi din")]
HOUR_OPTIONS = [8, 9, 12, 18, 21]

STATUS_LABEL = {"todo": "📝 To-do", "applied": "✅ Applied", "done": "🏁 Done"}
STATUS_ICON = {"todo": "📝", "applied": "✅", "done": "🏁"}

VIEW_TITLE = {
    "all": "📋 Sab upcoming",
    "online": "🌐 Online",
    "offline": "📍 Offline",
    "week": "📅 Agle 7 din",
    "month": "🗓 Agle 30 din",
    "done": "🏁 Done",
}


# ---------- DATA (JSON file) ----------
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_user(data, chat_id):
    key = str(chat_id)
    if key not in data:
        data[key] = {"reminders": DEFAULT_REMINDERS, "hackathons": [], "next_id": 1}
    return data[key]


def find_item(user, hid):
    for h in user["hackathons"]:
        if h["id"] == hid:
            return h
    return None


def set_status(chat_id, hid, status):
    data = load_data()
    user = get_user(data, chat_id)
    item = find_item(user, hid)
    if item:
        item["status"] = status
        save_data(data)


def delete_item(chat_id, hid):
    data = load_data()
    user = get_user(data, chat_id)
    user["hackathons"] = [h for h in user["hackathons"] if h["id"] != hid]
    save_data(data)


def toggle_reminder(chat_id, scope, n):
    """scope = 'g' (default for all) ya hackathon ki id."""
    data = load_data()
    user = get_user(data, chat_id)
    if scope == "g":
        target = user
    else:
        target = find_item(user, int(scope))
        if not target:
            return
    current = list(target.get("reminders", user["reminders"]))
    if n in current:
        current.remove(n)
    else:
        current.append(n)
    target["reminders"] = sorted(current, reverse=True)
    save_data(data)


def reset_reminder(chat_id, hid):
    data = load_data()
    user = get_user(data, chat_id)
    item = find_item(user, hid)
    if item and "reminders" in item:
        del item["reminders"]
        save_data(data)


def set_hour(chat_id, hour):
    data = load_data()
    user = get_user(data, chat_id)
    user["hour"] = hour
    save_data(data)


# ---------- HELPERS ----------
def days_left(date_str):
    d = datetime.strptime(date_str, "%d-%m-%Y").date()
    return (d - datetime.now(IST).date()).days


def when_text(left):
    if left < 0:
        return "nikal gaya"
    if left == 0:
        return "AAJ hai!"
    if left == 1:
        return "kal hai"
    return f"{left} din baaki"


def hour_label(h):
    if h == 12:
        return "12 PM"
    return f"{h} AM" if h < 12 else f"{h - 12} PM"


def get_items(user, view):
    items = []
    for h in user["hackathons"]:
        status = h.get("status", "todo")
        left = days_left(h["date"])
        if view == "done":
            if status == "done":
                items.append(h)
            continue
        if status == "done" or left < 0:
            continue
        if view == "online" and h["mode"] != "online":
            continue
        if view == "offline" and h["mode"] != "offline":
            continue
        if view == "week" and left > 7:
            continue
        if view == "month" and left > 30:
            continue
        items.append(h)
    items.sort(key=lambda h: datetime.strptime(h["date"], "%d-%m-%Y"))
    return items


def btn(text, data):
    return InlineKeyboardButton(text, callback_data=data)


def nav_rows():
    """Neeche wale buttons (har list ke saath dikhte hain)."""
    return [
        [btn("➕ Add Hackathon", "add"), btn("⏰ Reminders", "rem:g")],
        [btn("📋 Sab", "view:all"), btn("🌐 Online", "view:online"), btn("📍 Offline", "view:offline")],
        [btn("📅 Week", "view:week"), btn("🗓 Month", "view:month"), btn("🏁 Done", "view:done")],
    ]


# ---------- SCREENS (text + buttons banane wale functions) ----------
def render_view(chat_id, view):
    data = load_data()
    user = get_user(data, chat_id)
    items = get_items(user, view)
    title = VIEW_TITLE[view]

    if items:
        text = f"{title} ({len(items)})\n\nKisi bhi hackathon par tap karo 👇"
    else:
        text = f"{title}\n\nAbhi kuch nahi hai. Neeche ➕ Add Hackathon dabao."

    rows = []
    for h in items:
        left = days_left(h["date"])
        icon = STATUS_ICON[h.get("status", "todo")]
        mode_icon = "🌐" if h["mode"] == "online" else "📍"
        left_short = f"{left}d" if left >= 0 else "past"
        label = f"{icon}{mode_icon} {h['name'][:24]} · {h['date'][:5]} · {left_short}"
        rows.append([btn(label, f"open:{h['id']}:{view}")])
    rows += nav_rows()
    return text, InlineKeyboardMarkup(rows)


def render_detail(chat_id, hid, view, note=""):
    data = load_data()
    user = get_user(data, chat_id)
    h = find_item(user, hid)
    if not h:
        return render_view(chat_id, view)

    status = h.get("status", "todo")
    mode = "Online" if h["mode"] == "online" else "Offline"
    lines = [
        f"🎯 {h['name']}",
        f"📅 {h['date']} ({when_text(days_left(h['date']))})",
        f"🧭 {mode}",
        f"📌 Status: {STATUS_LABEL[status]}",
    ]
    if h.get("link"):
        lines.append(f"🔗 {h['link']}")
    text = "\n".join(lines)
    if note:
        text = note + "\n\n" + text

    status_row = []
    for key, label in STATUS_LABEL.items():
        shown = f"✔ {label}" if key == status else label
        status_row.append(btn(shown, f"set:{hid}:{key}:{view}"))

    rows = [
        status_row,
        [btn("⏰ Reminder", f"rem:{hid}"), btn("🗑 Delete", f"ask:{hid}:{view}")],
        [btn("⬅️ Back", f"view:{view}")],
    ]
    return text, InlineKeyboardMarkup(rows)


def render_confirm(chat_id, hid, view):
    data = load_data()
    user = get_user(data, chat_id)
    h = find_item(user, hid)
    if not h:
        return render_view(chat_id, view)
    text = f"Pakka delete karna hai?\n\n🎯 {h['name']} ({h['date']})"
    rows = [[btn("🗑 Haan, delete", f"delyes:{hid}:{view}"), btn("❌ Nahi", f"open:{hid}:{view}")]]
    return text, InlineKeyboardMarkup(rows)


def render_reminders(chat_id, scope):
    data = load_data()
    user = get_user(data, chat_id)

    if scope == "g":
        days = user["reminders"]
        hour = user.get("hour", DEFAULT_HOUR)
        text = (
            "⏰ Default reminders\n\n"
            "Hackathon se kitne din pehle yaad dilana hai? Tap karke ON/OFF karo.\n\n"
            f"Roz reminder aayega: {hour_label(hour)}"
        )
    else:
        h = find_item(user, int(scope))
        if not h:
            return render_view(chat_id, "all")
        custom = "reminders" in h
        days = h["reminders"] if custom else user["reminders"]
        which = "Is hackathon ka custom reminder set hai." if custom else "Abhi default reminder chal raha hai."
        text = f"⏰ Reminder: {h['name']}\n\n{which}\nTap karke ON/OFF karo 👇"

    day_buttons = [
        btn(("✔ " if n in days else "") + label, f"rt:{scope}:{n}") for n, label in DAY_OPTIONS
    ]
    rows = [day_buttons[:3], day_buttons[3:]]

    if scope == "g":
        hour_buttons = [
            btn(("✔ " if hr == hour else "") + hour_label(hr), f"hr:{hr}") for hr in HOUR_OPTIONS
        ]
        rows += [hour_buttons[:3], hour_buttons[3:]]
        rows.append([btn("⬅️ Back", "view:all")])
    else:
        rows.append([btn("🔄 Default use karo", f"rr:{scope}")])
        rows.append([btn("⬅️ Back", f"open:{scope}:all")])
    return text, InlineKeyboardMarkup(rows)


def render_calendar(year, month):
    today = datetime.now(IST).date()
    prev_y, prev_m = (year, month - 1) if month > 1 else (year - 1, 12)
    next_y, next_m = (year, month + 1) if month < 12 else (year + 1, 1)
    can_prev = (year, month) > (today.year, today.month)

    rows = [
        [
            btn("‹" if can_prev else "·", f"cal:{prev_y}-{prev_m:02d}" if can_prev else "noop"),
            btn(f"{calendar.month_name[month]} {year}", "noop"),
            btn("›", f"cal:{next_y}-{next_m:02d}"),
        ],
        [btn(d, "noop") for d in ["M", "T", "W", "T", "F", "S", "S"]],
    ]
    for week in calendar.monthcalendar(year, month):
        row = []
        for day in week:
            if day == 0 or date(year, month, day) < today:
                row.append(btn("·", "noop"))
            else:
                row.append(btn(str(day), f"day:{year}-{month:02d}-{day:02d}"))
        rows.append(row)
    rows.append([btn("❌ Cancel", "cancel")])
    return InlineKeyboardMarkup(rows)


# ---------- ADD FLOW ----------
def finish_add(chat_id, user_data, link=""):
    draft = user_data.get("draft")
    if not draft or "date" not in draft or "mode" not in draft:
        return None
    data = load_data()
    user = get_user(data, chat_id)
    item = {
        "id": user["next_id"],
        "name": draft["name"],
        "date": draft["date"],
        "mode": draft["mode"],
        "link": link,
        "status": "todo",
    }
    user["next_id"] += 1
    user["hackathons"].append(item)
    save_data(data)
    user_data.pop("draft", None)
    user_data["state"] = None
    return render_detail(chat_id, item["id"], "all", note="Add ho gaya! ✅")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sirf naam (aur optional link) type karna padta hai, baaki sab buttons."""
    state = context.user_data.get("state")
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    if state == "name":
        context.user_data["draft"] = {"name": text[:80]}
        context.user_data["state"] = None
        today = datetime.now(IST).date()
        await update.message.reply_text(
            f"📅 '{text[:80]}' ki date chuno:",
            reply_markup=render_calendar(today.year, today.month),
        )
    elif state == "link":
        result = finish_add(chat_id, context.user_data, link=text)
        if result is None:
            screen = render_view(chat_id, "all")
            await update.message.reply_text("Session expire ho gaya, dubara ➕ Add dabao.", reply_markup=screen[1])
            return
        await update.message.reply_text(result[0], reply_markup=result[1], disable_web_page_preview=True)
    else:
        text_, markup = render_view(chat_id, "all")
        await update.message.reply_text(text_, reply_markup=markup)


# ---------- COMMANDS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = None
    await update.message.reply_text(
        "Hackathon Tracker Bot 🚀\n\n"
        "Sab kuch neeche ke buttons se hoga. Naya hackathon add karne ke liye ➕ dabao."
    )
    text, markup = render_view(update.effective_chat.id, "all")
    await update.message.reply_text(text, reply_markup=markup)


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = None
    text, markup = render_view(update.effective_chat.id, "all")
    await update.message.reply_text(text, reply_markup=markup)


# ---------- BUTTON CLICKS ----------
async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    action = parts[0]
    chat_id = query.message.chat_id

    if action == "noop":
        return

    if action == "view":
        text, markup = render_view(chat_id, parts[1])
    elif action == "open":
        text, markup = render_detail(chat_id, int(parts[1]), parts[2])
    elif action == "set":
        hid, status, view = int(parts[1]), parts[2], parts[3]
        set_status(chat_id, hid, status)
        text, markup = render_detail(chat_id, hid, view, note="Status update ho gaya ✅")
    elif action == "ask":
        text, markup = render_confirm(chat_id, int(parts[1]), parts[2])
    elif action == "delyes":
        delete_item(chat_id, int(parts[1]))
        text, markup = render_view(chat_id, parts[2])

    # --- reminders ---
    elif action == "rem":
        text, markup = render_reminders(chat_id, parts[1])
    elif action == "rt":
        toggle_reminder(chat_id, parts[1], int(parts[2]))
        text, markup = render_reminders(chat_id, parts[1])
    elif action == "rr":
        reset_reminder(chat_id, int(parts[1]))
        text, markup = render_reminders(chat_id, parts[1])
    elif action == "hr":
        set_hour(chat_id, int(parts[1]))
        text, markup = render_reminders(chat_id, "g")

    # --- add flow ---
    elif action == "add":
        context.user_data["state"] = "name"
        context.user_data["draft"] = {}
        text = "✏️ Hackathon ka naam bhejo (bas normal message type karo)."
        markup = InlineKeyboardMarkup([[btn("❌ Cancel", "cancel")]])
    elif action == "cal":
        year, month = parts[1].split("-")
        text = "📅 Date chuno:"
        markup = render_calendar(int(year), int(month))
    elif action == "day":
        draft = context.user_data.get("draft")
        if not draft or "name" not in draft:
            text, markup = render_view(chat_id, "all")
            text = "Session expire ho gaya, dubara ➕ Add dabao.\n\n" + text
        else:
            d = datetime.strptime(parts[1], "%Y-%m-%d")
            draft["date"] = d.strftime("%d-%m-%Y")
            text = f"🎯 {draft['name']}\n📅 {draft['date']}\n\nOnline hai ya offline?"
            markup = InlineKeyboardMarkup(
                [[btn("🌐 Online", "mode:online"), btn("📍 Offline", "mode:offline")],
                 [btn("❌ Cancel", "cancel")]]
            )
    elif action == "mode":
        draft = context.user_data.get("draft")
        if not draft or "date" not in draft:
            text, markup = render_view(chat_id, "all")
            text = "Session expire ho gaya, dubara ➕ Add dabao.\n\n" + text
        else:
            draft["mode"] = parts[1]
            context.user_data["state"] = "link"
            text = "🔗 Registration/website ka link bhejo, ya Skip dabao."
            markup = InlineKeyboardMarkup([[btn("⏭ Skip", "skiplink"), btn("❌ Cancel", "cancel")]])
    elif action == "skiplink":
        result = finish_add(chat_id, context.user_data)
        if result is None:
            text, markup = render_view(chat_id, "all")
            text = "Session expire ho gaya, dubara ➕ Add dabao.\n\n" + text
        else:
            text, markup = result
    elif action == "cancel":
        context.user_data["state"] = None
        context.user_data.pop("draft", None)
        text, markup = render_view(chat_id, "all")
    else:
        return

    try:
        await query.edit_message_text(text, reply_markup=markup, disable_web_page_preview=True)
    except BadRequest:
        pass  # message same hi tha, koi dikkat nahi


# ---------- HOURLY REMINDER JOB ----------
async def hourly_check(context: ContextTypes.DEFAULT_TYPE):
    """Har ghante chalta hai; sirf us user ko bhejta hai jiska chuna hua time ho."""
    now = datetime.now(IST)
    data = load_data()
    for chat_id, user in data.items():
        if user.get("hour", DEFAULT_HOUR) != now.hour:
            continue
        for h in user["hackathons"]:
            if h.get("status", "todo") == "done":
                continue
            days = h.get("reminders", user["reminders"])
            if days_left(h["date"]) in days:
                text, markup = render_detail(int(chat_id), h["id"], "all", note="⏰ REMINDER! Prepare kar lo!")
                await context.bot.send_message(
                    chat_id=int(chat_id),
                    text=text,
                    reply_markup=markup,
                    disable_web_page_preview=True,
                )


# ---------- MAIN ----------
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler(["start", "help"], start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    # agle ghante ke shuru se har ghante check
    now = datetime.now(IST)
    seconds_to_next_hour = 3600 - (now.minute * 60 + now.second)
    app.job_queue.run_repeating(hourly_check, interval=3600, first=seconds_to_next_hour + 5)

    print("Bot chal raha hai... (band karne ke liye Ctrl+C)")
    app.run_polling()


if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())
    main()
