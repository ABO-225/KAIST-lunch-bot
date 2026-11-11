"""식당별 메인 메뉴(메인·밥·국)만 골라 한 줄로 요약한다. (규칙 기반, 무료)

코너 구분: "(한식)", "[일품: 6,500원]" 같은 줄이 나오면 새 코너로 본다.
코너마다:
  - 반찬(김치·나물·샐러드 등)은 버림
  - 밥: 쌀밥·백미밥·잡곡밥처럼 짧은 '~밥' (볶음밥·덮밥·비빔밥은 메인)
  - 국: ~국/탕/찌개/전골/스프
  - 메인: 밥·국보다 앞에 나온 나머지 메뉴 (없으면 첫 번째 나머지 메뉴)
결과: "메인 · 밥 · 국", 코너가 여러 개면 " / "로 구분
"""

from __future__ import annotations

import re

from .scraper import Menu

SIDE_KEYWORDS = (
    "김치", "깍두기", "석박지", "섞박지", "나물", "무침", "샐러드", "드레싱", "장아찌",
    "단무지", "피클", "요구르트", "요거트", "음료", "주스", "쥬스", "우유", "과일",
    "소스", "김구이", "젓갈", "숭늉", "누룽지", "후리가케", "양념장", "냉채", "쌈채소", "쌈무",
    "깻잎지", "콩자반", "멸치", "생채", "겉절이", "식혜",
)
MAIN_RICE_PREFIX = ("볶음", "덮", "비빔", "김", "초", "주먹", "솥", "카레", "오므", "국")
SOUP_SUFFIX = ("국", "국물", "탕", "찌개", "전골", "개장", "스프", "수프", "짬뽕")
CORNER_RE = re.compile(r"^[\(\[].*[\)\]]$")
PRICE_RE = re.compile(r"[\d,]+원")


MAIN_SUFFIX = ("밥", "면", "국수", "우동", "파스타", "까스", "카츠", "버거") + SOUP_SUFFIX


def _is_side(item: str) -> bool:
    # 김치볶음밥·김치찌개·나물비빔밥처럼 반찬 단어가 들어간 메인은 남김
    # "돈까스*소스"처럼 곁들임이 붙은 경우 앞부분으로 판단
    name = re.split(r"[*&+]", item)[0].replace(" ", "")
    if name.endswith(MAIN_SUFFIX):
        return False
    return any(k in name for k in SIDE_KEYWORDS)


def _is_rice(item: str) -> bool:
    name = item.replace(" ", "")
    if "/" in name:  # "쌀밥/흑미밥"
        return all(_is_rice(x) for x in name.split("/") if x)
    return name.endswith("밥") and len(name) <= 4 and not name.startswith(MAIN_RICE_PREFIX)


def _is_soup(item: str) -> bool:
    name = item.replace(" ", "")
    return name.endswith(SOUP_SUFFIX)


CALORIE_RE = re.compile(r"칼로리|kcal", re.I)
# 괄호/꺾쇠로 감싼 줄, 또는 "A코너", "일품" 으로 시작하는 짧은 줄을 코너 이름으로 봄
CORNER_LINE_RE = re.compile(r"^(?:[\(\[<【〈].*[\)\]>】〉]|[A-Za-z0-9가-힣]{0,4}\s*코너(?:\s*[:：(\[].{0,15})?|일품(?:\s*[:：(\[].{0,15})?)$")


def _corner_label(line: str) -> tuple[str, str | None]:
    """'[일품: 6,500원]' -> ('일품', '6,500원'),  '<A코너>' -> ('A코너', None)"""
    m = PRICE_RE.search(line)
    price = m.group(0) if m else None
    label = PRICE_RE.sub("", line)
    label = re.sub(r"[\(\)\[\]<>【】〈〉:：/]", " ", label)
    label = re.sub(r"\s+", " ", label).strip()
    return label, price


# 메뉴 칸 안에 섞여 있는 가격 안내 줄: "석식(5,500원)", "중식 5,500원", "(6,000원)"
PRICE_ONLY_RE = re.compile(r"^(?:조식|중식|석식|외부인)?\s*[\(\[]?\s*[\d,]+\s*원\s*[\)\]]?$")


def _split_corners(items: list[str]) -> list[tuple[str | None, str | None, list[str]]]:
    corners: list[tuple[str | None, str | None, list[str]]] = []
    current: list[str] = []
    label: str | None = None
    price: str | None = None
    for item in items:
        if CALORIE_RE.search(item):  # 총 칼로리 줄 제거
            continue
        pm = PRICE_ONLY_RE.match(item.strip())
        if pm:  # "석식(5,500원)" 같은 가격 안내 줄 → 메뉴가 아니라 이 코너의 가격
            if price is None:
                found = PRICE_RE.search(item)
                price = found.group(0) if found else None
            continue
        if CORNER_LINE_RE.match(item.strip()):
            if current:
                corners.append((label, price, current))
            current = []
            label, price = _corner_label(item)
        else:
            current.append(item)
    if current:
        corners.append((label, price, current))
    return corners


def _tidy(item: str) -> str:
    """짝이 안 맞는 괄호 제거: '직화]돈사태김치찌개' -> '직화 돈사태김치찌개'"""
    for o, c in (("[", "]"), ("(", ")")):
        if item.count(o) != item.count(c):
            item = item.replace(o, " ").replace(c, " ")
    return re.sub(r"\s+", " ", item).strip()


# 항상 빼는 메뉴 (하드코딩)
ALWAYS_SKIP = ("추가밥", "밥추가", "밥 추가")


def _has_main_keyword(item: str, keywords) -> bool:
    return any(k in item for k in keywords)


Corner = tuple  # (코너 이름 | None, 가격 | None, 요약 문자열)


def summarize_corners(items: list[str], main_keywords=(), dessert_keywords=(), after_rice_keywords=(), must_keywords=()) -> list[Corner]:
    parts: list[Corner] = []
    for label, price, corner in _split_corners(items):
        mains, rice, after_rice, soup, dessert = [], [], [], [], []
        seen_staple = False
        others = []
        for item in corner:
            if any(k in item for k in ALWAYS_SKIP):
                continue
            # 반드시 표시(로제·마라 등): 반찬 판별 없이 메인으로
            if _has_main_keyword(item, must_keywords):
                mains.append(item)
                continue
            # 디저트·밥 뒤 메뉴는 반찬 판별보다 먼저 확인
            if _has_main_keyword(item, dessert_keywords):
                dessert.append(item)
                continue
            if _has_main_keyword(item, after_rice_keywords):
                after_rice.append(item)
                continue
            if _is_side(item):
                continue
            if _is_rice(item):
                rice.append(item)
                seen_staple = True
            elif _is_soup(item):
                soup.append(item)
                seen_staple = True
            elif not seen_staple or _has_main_keyword(item, main_keywords):
                # 밥·국보다 앞에 나왔거나, 메인 키워드(닭·돼지·생선 등)가 들어간 메뉴
                mains.append(item)
            else:
                others.append(item)
        if not mains and others:
            mains = others[:1]
        must = [x for x in mains if _has_main_keyword(x, must_keywords)]
        mains = must + [x for x in mains if x not in must][: max(0, 5 - len(must))]
        picked = mains + rice[:1] + after_rice + soup[:1] + dessert
        if not picked:
            continue
        text = " · ".join(_tidy(re.split(r"\s*[*&+]", x)[0]) for x in picked)
        parts.append((label or None, price, text))
    return parts


def summarize_items(items: list[str], main_keywords=(), dessert_keywords=(), after_rice_keywords=(), must_keywords=()) -> str:
    """한 줄 문자열 (테스트·간단 확인용)"""
    out = []
    for label, price, text in summarize_corners(items, main_keywords, dessert_keywords, after_rice_keywords, must_keywords):
        out.append(text + (f" ({price})" if price else ""))
    return " / ".join(out)


def summarize(menus: list[Menu], main_keywords=(), dessert_keywords=(), after_rice_keywords=(), must_keywords=()) -> dict[str, list[Corner]]:
    """{식당 코드: [(코너, 가격, 요약), ...]}"""
    return {
        m.code: summarize_corners(m.items, main_keywords, dessert_keywords, after_rice_keywords, must_keywords)
        for m in menus
    }
