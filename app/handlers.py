from aiogram import types, F, Router
from aiogram.filters import CommandStart, Command
from datetime import datetime, timedelta
from app.large_texts import *
import app.utils as utils

router = Router()


# -------------------- FREE GIFT --------------------
async def give_gift(message: types.Message):
    subscribe_link = utils.create_a_subscribe_link(-864000000)

    with utils.sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO trials (user_id, vpn_subscribe, start_date) VALUES (?, ?, date('now'))",
                       (message.from_user.id, subscribe_link))
        conn.commit()

    await message.answer(gift_text, parse_mode="HTML")
    await message.answer(f"<tg-spoiler>{subscribe_link}</tg-spoiler>", parse_mode='HTML')


# -------------------- START --------------------
@router.message(CommandStart())
async def main(message: types.Message):
    markup = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="❗️ Помощь"), types.KeyboardButton(text="📖 Инструкция")],
            [types.KeyboardButton(text="🚀 Пробный период"), types.KeyboardButton(text="💰 Купить ключ")],
            [types.KeyboardButton(text="🔑 Мои ключи")]
        ],
        resize_keyboard=True
    )

    await message.answer(welcome_text, reply_markup=markup, parse_mode='HTML')


# -------------------- HELP --------------------
@router.message(Command('help'))
async def help_cmd(message: types.Message):
    await message.answer(help_text, parse_mode="HTML")


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
            ]
        ]
    )

    await message.answer(buy_text, parse_mode='html', reply_markup=markup)


@router.callback_query(F.data.startswith("buy_"))
async def callback_buy(call: types.CallbackQuery):
    prices = {
        "buy_7": ("Подписка на 7 дней", 7500),
        "buy_30": ("Подписка на 30 дней", 9900),
        "buy_90": ("Подписка на 90 дней", 24900),
        "buy_180": ("Подписка на 180 дней", 44900)
    }

    title, amount = prices[call.data]

    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Оплатить 💳", callback_data=f"pay_{call.data}")],
            [types.InlineKeyboardButton(text="⬅ Назад", callback_data="back_to_buy")]
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
        "buy_7": ("Подписка на 7 дней", 7500),
        "buy_30": ("Подписка на 30 дней", 9900),
        "buy_90": ("Подписка на 90 дней", 24900),
        "buy_180": ("Подписка на 180 дней", 44900)
    }

    title, amount = prices[tariff]

    await send_invoice(bot, call.message.chat.id, amount, title, tariff)

async def send_invoice(bot, chat_id, amount, title, tariff):
    prices = [types.LabeledPrice(label=title, amount=amount)]

    await bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=f"Оформление подписки: {title}\n" + "Оплата проводится через офиуаильную площадку Юкасса",
        payload=tariff,
        provider_token=utils.PAYMENT_TOKEN,
        currency="RUB",
        prices=prices,
        start_parameter="subscription"
    )

@router.pre_checkout_query()
async def handle_successful_payment(pre_checkout_q: types.PreCheckoutQuery):
    await pre_checkout_q.answer(ok=True)

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

    new_subscribe_link = utils.create_a_subscribe_link(-time_remain * 1000)

    await message.answer(
        "🎉 Оплата прошла успешно!\n"
        f"Сумма: {total_amount/100} ₽\n\n"
        "Ваш ключ:\n"
        f"<tg-spoiler>{new_subscribe_link}</tg-spoiler>",
        parse_mode="HTML"
    )    

# -------------------- MANUAL --------------------
@router.message(Command('manual'))
async def manual(message: types.Message):
    await message.answer(manual_text, parse_mode='HTML')


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
            "Используйте /buy или получите бесплатный период /gift"
        )


# -------------------- GIFT --------------------
@router.message(Command('gift'))
async def gift(message: types.Message):
    if utils.check_users_gift(message.from_user.id):
        await message.answer("Вы уже использовали бесплатный период 👀 \n\nДля просмотра ключа используйте /key")
    else:
        await give_gift(message)


# -------------------- MARKUP BUTTONS --------------------
@router.message()
async def handle_markup_keyboard(message: types.Message):
    if message.text == "❗️ Помощь":
        await help_cmd(message)
    elif message.text == "📖 Инструкция":
        await manual(message)
    elif message.text == "🚀 Пробный период":
        await gift(message)
    elif message.text == "💰 Купить ключ":
        await buy(message)
    elif message.text == "🔑 Мои ключи":
        await check_key(message)