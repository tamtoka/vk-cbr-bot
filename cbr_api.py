"""Клиент XML API официальных курсов Банка России."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from urllib.request import urlopen
from xml.etree.ElementTree import ParseError

from defusedxml.ElementTree import fromstring
from defusedxml.common import DefusedXmlException


DAILY_RATES_URL = "https://www.cbr.ru/scripts/XML_daily.asp"
MAX_RESPONSE_BYTES = 256 * 1024


class RatesUnavailable(Exception):
    """Банк России недоступен или вернул некорректную таблицу."""


@dataclass(frozen=True)
class ExchangeRate:
    code: str
    name: str
    nominal: int
    rubles: Decimal

    def convert(self, amount: Decimal) -> Decimal:
        return amount * self.rubles / self.nominal


@dataclass(frozen=True)
class DailyRates:
    effective_date: date
    by_code: dict[str, ExchangeRate]


def fetch_daily_rates() -> DailyRates:
    """Получить курсы, сохраняя дату и номинал из ответа ЦБ."""
    try:
        with urlopen(DAILY_RATES_URL, timeout=8) as response:
            data = response.read(MAX_RESPONSE_BYTES + 1)
        if len(data) > MAX_RESPONSE_BYTES:
            raise ValueError("Ответ превышает допустимый размер")

        document = fromstring(data)
        if document.tag != "ValCurs":
            raise ValueError("Ожидалась таблица ValCurs")
        effective_date = datetime.strptime(document.attrib["Date"], "%d.%m.%Y").date()
        rates = {}
        for entry in document.findall("Valute"):
            code = entry.findtext("CharCode", "").strip()
            name = entry.findtext("Name", "").strip()
            nominal = int(entry.findtext("Nominal", ""))
            rubles = Decimal(entry.findtext("Value", "").replace(",", "."))
            if not code or not name or nominal <= 0 or not rubles.is_finite() or rubles <= 0:
                raise ValueError("Некорректная строка курса")
            rates[code] = ExchangeRate(code, name, nominal, rubles)
        if not rates:
            raise ValueError("Таблица курсов пуста")
    except (OSError, ParseError, DefusedXmlException, ValueError, KeyError, InvalidOperation) as exc:
        raise RatesUnavailable("Не удалось получить курсы Банка России") from exc

    return DailyRates(effective_date, rates)
