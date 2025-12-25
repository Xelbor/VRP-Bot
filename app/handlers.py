from aiogram import types, F, Router, Bot
from aiogram.filters import CommandStart, Command
from datetime import datetime, timedelta
import datetime
from app.large_texts import *
import app.utils as utils
import asyncio

router = Router()

# -------------------- START --------------------
@router.message(CommandStart())
async def main(message: types.Message):
    args = message.text.split()
    ref_code = args[1] if len(args) > 1 else None

    with utils.sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, created_at) VALUES (?, ?)",
            (message.from_user.id, datetime.datetime.now(datetime.UTC))
        )
        
        if ref_code and ref_code.startswith("ref_"):
            code = ref_code.replace("ref_", "")

            cursor.execute(
                "SELECT referrer_id FROM users WHERE user_id = ?",
                (message.from_user.id,)
            )
            if cursor.fetchone()[0] is None:
                cursor.execute(
                    "SELECT user_id FROM users WHERE referrer_id = ?",
                    (code,)
                )
                ref_owner = cursor.fetchone()

                if ref_owner and ref_owner[0] != message.from_user.id:
                    cursor.execute(
                        "UPDATE users SET referrer_id = ? WHERE user_id = ?",
                        (ref_owner[0], message.from_user.id)
                    )

                    cursor.execute(
                        """INSERT INTO refs (referrer_id, invited_id, bonus, created_at)
                           VALUES (?, ?, ?, ?)""",
                        (ref_owner[0], message.from_user.id, 0, datetime.datetime.now(datetime.UTC))
                    )

                    conn.commit()
                    utils.add_balance(ref_owner[0], 50)

    markup = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🔑 Мои ключи"), types.KeyboardButton(text="💳 Пополнить баланс")],
            [types.KeyboardButton(text="🎁 Бесплатный период"), types.KeyboardButton(text="💰 Баланс")],
            [types.KeyboardButton(text="📲 Установка"), types.KeyboardButton(text="💸 Скидка")]
        ],
        resize_keyboard=True
    )

    refs_inline = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text='Как получить скидку 70%?', callback_data="refs_call"),
            ],
        ]
    )

    await message.answer(welcome_text, reply_markup=markup, parse_mode='HTML')
    await message.answer("ℹ️ Узнай, как получить скидку:", reply_markup=refs_inline)

@router.callback_query(F.data.startswith("refs_"))
async def refs_callback(call: types.CallbackQuery):
    await referal_system(call.message)

# -------------------- BUY MENU --------------------
@router.message(Command('buy'))
async def buy(message: types.Message):
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text='💳 7 дней — 75₽', callback_data="buy_7"),
                types.InlineKeyboardButton(text='💳 30 дней — 99₽', callback_data="buy_30")
            ],
            [
                types.InlineKeyboardButton(text='💳 90 дней — 249₽', callback_data="buy_90"),
                types.InlineKeyboardButton(text='💳 180 дней — 449₽', callback_data="buy_180")
            ],
            [
                types.InlineKeyboardButton(text='💳 Своя сумма', callback_data="buy_own"),
            ]
        ]
    )

    await message.answer(buy_text, parse_mode='html', reply_markup=markup)

@router.callback_query(F.data.startswith("buy_"))
async def callback_buy(call: types.CallbackQuery):
    if (call.data == "buy_own"):
        await call.message.answer("💰 Введите сумму на которую хотите пополнить баланс:")
    else:
        prices = {
            "buy_7": ("Баланс на 7 дней подписки", 7500),
            "buy_30": ("Баланс на 30 дней подписки", 9900),
            "buy_90": ("Баланс на 90 дней подписки", 24900),
            "buy_180": ("Баланс на 180 дней подписки", 44900)
        }

        title, amount = prices[call.data]

        markup = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="Оплатить 💳", callback_data=f"pay_{call.data}")],
                [types.InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_buy")]
            ]
        )

        await call.message.edit_text(
            f"Вы выбрали: <b>{title}</b>\nНажмите 'Оплатить' чтобы продолжить.",
            parse_mode="HTML",
            reply_markup=markup
        )


@router.callback_query(F.data == "back_to_buy")
async def buy_back(call: types.CallbackQuery):
    await buy(call.message)

# -------------------- PAYMENT --------------------
@router.callback_query(F.data.startswith("pay_"))
async def callback_pay(call: types.CallbackQuery):
    bot = call.bot
    tariff = call.data.replace("pay_", "")

    prices = {
        "buy_7": ("Баланс на 7 дней подписки", 7500),
        "buy_30": ("Баланс на 30 дней подписки", 9900),
        "buy_90": ("Баланс на 90 дней подписки", 24900),
        "buy_180": ("Баланс на 180 дней подписки", 44900)
    }

    title, amount = prices[tariff]

    await send_invoice(bot, call.message.from_user.id, amount, title, tariff)

async def send_invoice(bot, chat_id, amount, title, tariff):
    prices = [types.LabeledPrice(label=title, amount=amount)]

    await bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=f"Оформление пополнения баланса: {title}\n" + "Оплата проводится через официальную площадку Юкасса",
        payload=tariff,
        provider_token=utils.PAYMENT_TOKEN,
        currency="RUB",
        prices=prices,
        start_parameter="subscription"
    )

@router.pre_checkout_query()
async def handle_successful_payment(pre_checkout_q: types.PreCheckoutQuery):
    await pre_checkout_q.answer(ok=True)

# --------------- SUCCESSFUL PAYMENT --------------------
@router.message(F.successful_payment)
async def successful_payment(message: types.Message):
    payment_info = message.successful_payment

    total_amount = payment_info.total_amount
    title = payment_info.invoice_payload
        
    match title:
        case "buy_7":
            time_remain = int(timedelta(days=7).total_seconds())
        case "buy_30":
            time_remain = int(timedelta(days=30).total_seconds())
        case "buy_90":
            time_remain = int(timedelta(days=90).total_seconds())
        case "buy_180":
            time_remain = int(timedelta(days=180).total_seconds())
        
    utils.add_balance(message.from_user.id, total_amount/100)
    user_balance = utils.get_balance(message.from_user.id)

    await message.answer(
        "🎉 Баланс пополнен успешно!\n"
        f"💰 Ваш текущий баланс: {user_balance}")

# -------------------- MANUAL --------------------
@router.message(Command('manual'))
async def manual(message: types.Message):
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="💻 Windows / Linux", callback_data="windows_linux_call"), types.InlineKeyboardButton(text="📱 Android", callback_data="android_call")],
            [types.InlineKeyboardButton(text="🍎 IOS", callback_data="ios_call")]
        ]
    )
    await message.answer(manual_text, parse_mode='HTML', reply_markup=markup)

@router.callback_query(F.data.endswith("_call"))
async def device_instruction(call: types.CallbackQuery):
    markup1 = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="◀️ Назад", callback_data="back_call")]
        ]
    )

    markup2 = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="💻 Windows / Linux", callback_data="windows_linux_call"), types.InlineKeyboardButton(text="📱 Android", callback_data="android_call")],
            [types.InlineKeyboardButton(text="🍎 IOS", callback_data="ios_call")]
        ]
    )

    match call.data:
        case "windows_linux_call":
            await call.message.edit_text(pc_manual_text, parse_mode='HTML', reply_markup=markup1)
        case "android_call":
            await call.message.edit_text(android_manual_text, parse_mode='HTML', reply_markup=markup1)
        case "ios_call":
            await call.message.edit_text(ios_manual_text, parse_mode='HTML', reply_markup=markup1)
        case "back_call":
            await call.message.edit_text(manual_text, parse_mode='HTML', reply_markup=markup2)

# -------------------- CHECK KEY --------------------
@router.message(Command('key'))
async def check_key(message: types.Message):
    if utils.check_users_gift(message.from_user.id):
        with utils.sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT vpn_subscribe FROM trials WHERE user_id = ?", (message.from_user.id,))
            row = cursor.fetchone()

        if row:
            vpn_subscribe = row[0]
            await message.answer(key_text + f"<tg-spoiler>{vpn_subscribe}</tg-spoiler>", parse_mode='HTML')
        else:
            await message.answer("Ошибка поиска ключа. Код: 0xER1")
    else:
        await message.answer(
            "У вас пока нет ключа.\n\n"
            "Нажмите кнопку 🎁 Бесплатный период, или пополните баланс, нажав кнопку 💳 Пополнить баланс"
        )

# -------------------- FREE GIFT --------------------
async def give_gift(message: types.Message):
    subscribe_link = utils.create_a_subscribe_link(-864000000)

    with utils.sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO trials (user_id, vpn_subscribe, start_date) VALUES (?, ?, date('now'))",
                       (message.from_user.id, subscribe_link))

    await message.answer(gift_text, parse_mode="HTML")
    await message.answer(f"<tg-spoiler>{subscribe_link}</tg-spoiler>", parse_mode='HTML')

# ---------------------- GIFT --------------------
@router.message(Command('gift'))
async def gift(message: types.Message):
    if utils.check_users_gift(message.from_user.id):
        await message.answer("<b>Вы уже использовали бесплатный период</b> 👀 \n\nДля просмотра ключа нажмите кнопку 🔑 Мои ключи", parse_mode='HTML')
    else:
        await give_gift(message)

# ---------------------- Broadcast ----------------------
@router.message(Command('broadcast'))
async def broadcast_handler(message: types.Message):
    if(message.from_user.id == int(utils.SERVICE_ID)):
        text = message.text.replace("/broadcast", "", 1).strip()
        if not text:
            await message.answer("Текст рассылки пуст")
            return
        if (text == "tech_works"):
            await broadcast(message.bot, "test tech works")
        else:
            await broadcast(message.bot, text)
    else:
        await message.answer("Нет прав на выполнение команды")
        return

async def broadcast(bot: Bot, text: str):
    with utils.sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()

        for (user_id,) in users:
            try:
                await bot.send_message(user_id, text)
                await asyncio.sleep(0.05)  # защита от FloodWait
            except Exception:
                pass

# ----------------------- Balance ------------------------
@router.message(Command('balance'))
async def balance(message: types.Message):
    user_balance = utils.get_balance(message.from_user.id)
    await message.answer(f"💰 <b>Ваш текущий баланс:</b> {str(user_balance)}₽", parse_mode='HTML')
    
# -------------------- Referal System --------------------
@router.message(Command('referal'))
async def referal_system(message: types.Message):
    if utils.user_has_invites(message.from_user.id):
        await message.answer("<b>Вы уже использовали свою реферальную ссылку.</b> 👀 По ней уже был зарегистрирован человек", parse_mode='HTML')
    else:
        await message.answer(ref_text, parse_mode='HTML')
        random_id = utils.random_email(6)
        with utils.sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (message.chat.id,))

            if cursor.fetchone()[0] is None:
                cursor.execute("UPDATE users SET referrer_id = ? WHERE user_id = ?", (random_id, message.chat.id))
                link = f"{utils.BOT_LINK}?start=ref_{random_id}"
                await message.answer("🎁 <b>Вот ваша ссылка для друга:</b> \n" + link, parse_mode='HTML')

# -------------------- MARKUP BUTTONS --------------------
@router.message()
async def handle_markup_keyboard(message: types.Message):
    if message.text == "🔑 Мои ключи":
        await check_key(message)
    elif message.text == "💳 Пополнить баланс":
        await buy(message)
    elif message.text == "🎁 Бесплатный период":
        await gift(message)
    elif message.text == "💰 Баланс":
        await balance(message)
    elif message.text == "📲 Установка":
        await manual(message)
    elif message.text == "💸 Скидка":
        await referal_system(message)