"""실제 페이지 형식을 흉내 낸 HTML로 파서를 확인한다.  python -m pytest tests"""

import datetime as dt

from menu.formatter import format_message
from menu.scraper import Menu, parse_lunch

EAST_HTML = """
<p>중식(5,500원) / 외부인(6,300원)</p>
<table class="table">
  <tr><th>조식 8:00~9:00</th><th>중식 11:30~13:30</th><th>석식 17:00~19:00</th></tr>
  <tr>
    <td>토스트</td>
    <td>(한식)<br>치즈불닭볶음2,6,16,15,5,1,13,18<br>쌀밥<br>사골파국5,6,15,16</td>
    <td>-</td>
  </tr>
</table>
"""

WEST_HTML = """
<table>
  <tr><th>조식</th><th>중식 11:30~13:30</th><th>석식</th></tr>
  <tr><td></td><td>[일품: 6500원]  백미밥  쑥갓어묵국 (5,6,7)  깻잎닭갈비 (5,15)</td><td></td></tr>
</table>
"""


def test_east():
    hours, items, price, outside = parse_lunch(EAST_HTML)
    assert hours == "11:30~13:30"
    assert items == ["(한식)", "치즈불닭볶음", "쌀밥", "사골파국"]
    assert (price, outside) == ("5,500원", "6,300원")


def test_west():
    _, items, price, _ = parse_lunch(WEST_HTML)
    assert items == ["[일품: 6,500원]", "백미밥", "쑥갓어묵국", "깻잎닭갈비"]
    assert price is None


def test_format():
    d = dt.date(2026, 11, 11)
    msg = format_message([Menu("east1", "동측", d, "11:30~13:30", ["쌀밥"], "5,500원")], d)
    assert "11/11(수)" in msg and "가격: 5,500원" in msg and "- 쌀밥" in msg


def test_rule_based_summary():
    from menu.formatter import format_compact
    from menu.summarizer import summarize

    d = dt.date(2026, 11, 11)
    m = Menu("east1", "동측 학생식당", d, "", ["(한식)", "치즈불닭볶음", "쌀밥", "사골파국", "유부냉채", "깍두기", "그린샐러드*드레싱"], "5,500원")
    lines = summarize([m])
    msg = format_compact([m], lines, {"east1": "동측"}, d)
    assert msg.splitlines()[1:] == ["동측", " - 한식 5,500원 | 치즈불닭볶음 · 쌀밥 · 사골파국"]


def test_summary_corners():
    from menu.summarizer import summarize_items

    assert summarize_items(["[일품: 6,500원]", "백미밥", "쑥갓어묵국", "깻잎닭갈비", "배추김치"]) == \
        "깻잎닭갈비 · 백미밥 · 쑥갓어묵국 (6,500원)"
    assert summarize_items(["(한식)", "제육볶음", "쌀밥", "된장국", "콩나물무침", "(일품)", "돈까스", "양배추샐러드"]) == \
        "제육볶음 · 쌀밥 · 된장국 / 돈까스"
    assert summarize_items(["김치볶음밥", "계란국", "단무지"]) == "김치볶음밥 · 계란국"


def test_main_keywords_keep_late_mains():
    import config
    from menu.summarizer import summarize_items

    items = ["(자율코너)", "쌀밥", "미역국", "닭찜", "봉골레파스타", "콩나물무침", "깍두기"]
    assert summarize_items(items, config.MAIN_KEYWORDS) == "닭찜 · 봉골레파스타 · 쌀밥 · 미역국"


def test_calorie_removed_and_corner_lines():
    import config
    from menu.formatter import format_compact
    from menu.summarizer import summarize

    d = dt.date(2026, 11, 11)
    m = Menu("fclt", "북측", d, "", [
        "[일품: 6,500원]", "돈까스*소스", "양배추샐러드",
        "<A코너>", "제육볶음", "쌀밥", "된장국", "총 칼로리 850kcal",
        "B코너", "닭찜", "잡곡밥", "깍두기", "총칼로리: 720 Kcal",
    ], "5,000원")
    msg = format_compact([m], summarize([m], config.MAIN_KEYWORDS), {"fclt": "북측"}, d)
    assert msg.splitlines()[1:] == [
        "북측",
        " - 일품 6,500원 | 돈까스",
        " - A코너 5,000원 | 제육볶음 · 쌀밥 · 된장국",
        " - B코너 5,000원 | 닭찜 · 잡곡밥",
    ]
    assert "칼로리" not in msg


def test_round3_rules():
    import config
    from menu.summarizer import summarize_items

    kw = (config.MAIN_KEYWORDS, config.DESSERT_KEYWORDS, getattr(config, "AFTER_RICE_KEYWORDS", ["차완무시"]))
    items = ["돈육김치찌개", "쌀밥", "어묵볶음", "소떡소떡", "추가밥", "배추김치", "빼빼로"]
    assert summarize_items(items, *kw) == "어묵볶음 · 소떡소떡 · 쌀밥 · 돈육김치찌개 · 빼빼로"
    items = ["(일식)", "가츠동", "공기밥", "미소국", "차완무시", "단무지", "꽈배기"]
    assert summarize_items(items, *kw) == "가츠동 · 공기밥 · 차완무시 · 미소국 · 꽈배기"


def test_prices_per_corner():
    import config
    from menu.formatter import format_compact
    from menu.scraper import parse_price_table
    from menu.summarizer import summarize

    d = dt.date(2026, 11, 11)
    notice = "[금액 ]\n조식(5,500원)\n1층 味퍼레이드한식 (5,500원)\n고메가든(일품) (6,500원)\n2층 味퍼레이드한식 (중식.석식) (6,500원)"
    east = Menu("east1", "동측", d, "", ["(한식)", "치즈불닭볶음", "쌀밥", "(일품)", "제주고기국수"],
                price_table=parse_price_table(notice))
    west = Menu("west", "서측", d, "", ["콘마요닭갈비", "백미밥", "[일품: 6,500원]", "해물짬뽕파스타"], "5,500원")
    north = Menu("fclt", "북측", d, "", ["<B코너 6,000원>", "공기밥", "직화]돈사태김치찌개"])
    menus = [east, west, north]
    msg = format_compact(menus, summarize(menus, config.MAIN_KEYWORDS), config.SHORT_NAMES, d, True)
    assert msg.splitlines()[1:] == [
        "동측",
        " - 한식 5,500원 | 치즈불닭볶음 · 쌀밥",
        " - 일품 6,500원 | 제주고기국수",
        "서측",
        " - 코너1 5,500원 | 콘마요닭갈비 · 백미밥",
        " - 일품 6,500원 | 해물짬뽕파스타",
        "북측",
        " - B코너 6,000원 | 공기밥 · 직화 돈사태김치찌개",
    ]

    from menu.summarizer import summarize_items
    assert summarize_items(["쌀밥/흑미밥", "묵은지순살닭찜", "콩나물국"], config.MAIN_KEYWORDS) == "묵은지순살닭찜 · 쌀밥/흑미밥 · 콩나물국"
