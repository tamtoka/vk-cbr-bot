"""Курсы Банка России в личных сообщениях сообщества ВКонтакте."""

import asyncio
from decimal import Decimal, ROUND_HALF_UP
import logging
import os
from pathlib import Path
import re

from dotenv import load_dotenv
from vkbottle import Keyboard, Text
from vkbottle.bot import Bot, Message

from cbr_api import RatesUnavailable, fetch_daily_rates


KEYBOARD = (
    Keyboard(one_time=False, inline=False)
    .add(Text("Курсы"))
    .add(Text("Курс валюты"))
    .row()
    .add(Text("Конвертер"))
    .get_json()
)
MAIN_CODES = ("USD", "EUR", "CNY")
HELP = (
    "Показываю официальные курсы Банка России. Выберите действие:\n"
    "• Курсы — доллар, евро и юань.\n"
    "• Курс валюты — курс по коду, например JPY.\n"
    "• Конвертер — пересчёт в рубли, например 1000 JPY."
)
AMOUNT_AND_CODE = re.compile(r"([0-9]{1,12}(?:[.,][0-9]{1,4})?) +([A-Z]{3})")


def format_number(value: Decimal) -> str:
    return f"{value:,f}".replace(",", " ").replace(".", ",")


async def reply_to(text: str) -> str:
    command = " ".join(text.split())
    match command.casefold():
        case "курсы" | "/rates":
            codes = MAIN_CODES
            amount = None
        case "курс валюты" | "/rate":
            return "Отправьте трёхбуквенный код валюты, например JPY или KZT."
        case "конвертер" | "/convert":
            return "Отправьте сумму и код валюты через пробел, например 1000 JPY или 15,50 USD."
        case "" | "начать" | "/start" | "помощь" | "/help":
            return HELP
        case _:
            upper = command.upper()
            if re.fullmatch(r"[A-Z]{3}", upper):
                codes = (upper,)
                amount = None
            elif conversion := AMOUNT_AND_CODE.fullmatch(upper):
                amount = Decimal(conversion[1].replace(",", "."))
                codes = (conversion[2],)
            else:
                return "Введите код валюты, например JPY, или сумму с кодом, например 1000 JPY."

    try:
        daily = await asyncio.to_thread(fetch_daily_rates)
    except RatesUnavailable:
        logging.warning("Не удалось получить таблицу курсов Банка России")
        return "Курсы Банка России сейчас недоступны. Попробуйте чуть позже."

    lines = [f"Официальный курс Банка России на {daily.effective_date:%d.%m.%Y}"]
    for code in codes:
        rate = daily.by_code.get(code)
        if rate is None:
            lines.append(f"{code} — в таблице Банка России нет такого кода.")
        elif amount is None:
            lines.append(f"{rate.nominal} {code} — {format_number(rate.rubles)} ₽ ({rate.name})")
        else:
            rubles = rate.convert(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            lines.append(f"{format_number(amount)} {code} ≈ {format_number(rubles)} ₽")
    return "\n".join(lines)


def create_bot(token: str) -> Bot:
    bot = Bot(token)

    @bot.on.private_message()
    async def handle(message: Message) -> None:
        await message.answer(await reply_to(message.text), keyboard=KEYBOARD)

    return bot


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    load_dotenv(Path(__file__).with_name(".env"))
    token = os.getenv("VK_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("Заполните VK_BOT_TOKEN в файле .env по образцу .env.example.")
    create_bot(token).run()


if __name__ == "__main__":
    main()
