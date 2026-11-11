"""메뉴 목록을 카카오톡 메시지 문자열로 만든다."""

from __future__ import annotations

import datetime as dt

from .scraper import Menu

WEEKDAYS = "월화수목금토일"


def corner_price(m: Menu, label: str | None, own_price: str | None) -> str | None:
    """코너 가격: 코너 이름에 적힌 가격 → 안내문 가격표에서 코너 이름으로 찾기 → 식당 기본 중식 가격"""
    if own_price:
        return own_price
    if label:
        for name, price in m.price_table:
            if label in name and "조식" not in name and "석식)" not in name:
                return price
    return m.price


def _header(date: dt.date) -> str:
    return f"[KAIST 점심] {date:%m/%d}({WEEKDAYS[date.weekday()]})"


def format_compact(menus: list[Menu], corners: dict[str, list], short_names: dict[str, str], date: dt.date, show_price: bool = True) -> str:
    """코너가 하나면 한 줄, 여러 개면 코너마다 줄바꿈.

    동측 5,500원 | 치즈불닭볶음 · 쌀밥 · 사골파국
    북측
     - 일품 6,500원 | 돈까스
     - A코너 | 제육볶음 · 쌀밥 · 된장국
    """
    out = [_header(date)]
    for m in menus:
        name = short_names.get(m.code, m.name)
        items = corners.get(m.code) or []

        if m.error:
            out.append(f"{name} | 메뉴를 불러오지 못했어요")
        elif not items:
            out.append(f"{name} | 메뉴 없음")
        elif len(items) == 1 and not items[0][0]:
            label, price, text = items[0]
            p = corner_price(m, label, price)
            head = f"{name} {p}" if (show_price and p) else name
            out.append(f"{head} | {text}")
        else:
            out.append(name)
            for i, (label, price, text) in enumerate(items, 1):
                tag = label or f"코너{i}"
                p = corner_price(m, label, price)
                if show_price and p:
                    tag += f" {p}"
                out.append(f" - {tag} | {text}")
    return "\n".join(out)


def format_message(menus: list[Menu], date: dt.date) -> str:
    """전체 메뉴 (요약 전 원본 확인용)"""
    lines = [_header(date)]
    for m in menus:
        lines.append("")
        title = f"■ {m.name}"
        if m.hours:
            title += f"  {m.hours}"
        lines.append(title)
        if m.price:
            price = f"가격: {m.price}"
            if m.outside_price:
                price += f" (외부인 {m.outside_price})"
            lines.append(price)
        if m.error:
            lines.append("메뉴를 불러오지 못했어요.")
        elif m.empty:
            lines.append("오늘은 메뉴 정보가 없어요.")
        else:
            lines.extend(f"- {item}" for item in m.items)
    return "\n".join(lines)
