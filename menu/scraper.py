"""KAIST 학식 페이지에서 점심(중식) 메뉴와 가격을 가져온다."""

from __future__ import annotations

import datetime as dt
import re
import time
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) kaist-lunch-bot"}

# 알레르기 표기 제거: "치즈불닭볶음2,6,16" / "쑥갓어묵국 (5,6,7)"
ALLERGEN_RE = re.compile(r"\s*\(?\d{1,2}(?:\s*,\s*\d{1,2})*\)?(?=\s|$)")
# 가격: "5,500원", "6500원"
PRICE_RE = re.compile(r"(\d{1,3}(?:,\d{3})+|\d{4,6})\s*원")
# 페이지 안의 기본 가격 안내: "중식(5,500원) / 외부인(6,300원)"
BASE_PRICE_RE = re.compile(
    r"중식\s*\(\s*([\d,]+\s*원)\s*\)(?:\s*/?\s*외부인\s*\(\s*([\d,]+\s*원)\s*\))?"
)


@dataclass
class Menu:
    code: str
    name: str
    date: dt.date
    hours: str = ""
    items: list[str] = field(default_factory=list)
    price: str | None = None  # 기본 가격 (학내)
    outside_price: str | None = None  # 외부인 가격
    # 페이지 안내문의 가격표: [("1층 味퍼레이드한식", "5,500원"), ("고메가든(일품)", "6,500원"), ...]
    price_table: list[tuple[str, str]] = field(default_factory=list)
    url: str = ""
    error: str | None = None

    @property
    def empty(self) -> bool:
        return not self.items


def fetch_html(url: str, params: dict, retries: int = 3) -> str:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or "utf-8"
            return resp.text
        except requests.RequestException as exc:
            last_exc = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"페이지를 가져오지 못했습니다: {last_exc}")


def _normalize_price(text: str) -> str:
    """'6500원' -> '6,500원'"""
    def repl(m: re.Match) -> str:
        return f"{int(m.group(1).replace(',', '')):,}원"
    return PRICE_RE.sub(repl, text)


def _clean_line(line: str) -> str:
    line = ALLERGEN_RE.sub("", line)
    line = re.sub(r"\s+", " ", line).strip(" -·*")
    return _normalize_price(line)


def _find_lunch_cell(soup: BeautifulSoup):
    """헤더에 '중식'이 있는 표에서 해당 열의 첫 데이터 칸을 찾는다."""
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        headers = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])]
        idx = next((i for i, h in enumerate(headers) if "중식" in h), None)
        if idx is None:
            continue
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) > idx:
                return headers[idx], cells[idx]
    return None, None


PRICE_LINE_RE = re.compile(r"([^\n]*?)\s*\(\s*([\d,]+)\s*원\s*\)")


def parse_price_table(text: str) -> list[tuple[str, str]]:
    """'고메가든(일품) (6,500원)' 같은 줄에서 (이름, 가격) 목록을 뽑는다."""
    table = []
    for line in text.splitlines():
        line = line.strip()
        for m in PRICE_LINE_RE.finditer(line):
            name = m.group(1).strip(" /:-")
            if name:
                table.append((name, _normalize_price(m.group(2) + "원")))
    return table


def parse_lunch(html: str) -> tuple[str, list[str], str | None, str | None]:
    """(운영시간, 메뉴 줄 목록, 기본가격, 외부인가격)"""
    soup = BeautifulSoup(html, "html.parser")
    header, cell = _find_lunch_cell(soup)

    hours = ""
    if header:
        m = re.search(r"\d{1,2}:\d{2}\s*~\s*\d{1,2}:\d{2}", header)
        hours = m.group(0).replace(" ", "") if m else ""

    items: list[str] = []
    if cell is not None:
        for br in cell.find_all("br"):
            br.replace_with("\n")
        raw = cell.get_text("\n")
        for chunk in raw.split("\n"):
            # 서맛골처럼 <br> 없이 공백 2칸 이상으로 구분된 경우
            for part in re.split(r"\s{2,}", chunk):
                cleaned = _clean_line(part)
                if cleaned and not re.search(r"칼로리|kcal", cleaned, re.I):
                    items.append(cleaned)

    price = outside = None
    m = BASE_PRICE_RE.search(soup.get_text(" "))
    if m:
        price = _normalize_price(m.group(1).replace(" ", ""))
        outside = _normalize_price(m.group(2).replace(" ", "")) if m.group(2) else None

    return hours, items, price, outside


def get_lunch_menu(base_url: str, code: str, name: str, date: dt.date) -> Menu:
    params = {"dvs_cd": code, "stt_dt": date.isoformat()}
    menu = Menu(code=code, name=name, date=date, url=f"{base_url}?dvs_cd={code}&stt_dt={date}")
    try:
        html = fetch_html(base_url, params)
        menu.hours, menu.items, menu.price, menu.outside_price = parse_lunch(html)
        menu.price_table = parse_price_table(BeautifulSoup(html, "html.parser").get_text("\n"))
    except Exception as exc:  # 한 식당이 실패해도 나머지는 보냄
        menu.error = str(exc)
    return menu
