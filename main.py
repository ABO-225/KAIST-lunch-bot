"""KAIST 점심 메뉴를 가져와 카카오톡 채팅방에 보낸다.

사용법:
  python main.py --dry-run          # 보내지 않고 메시지만 출력
  python main.py                    # 오늘 메뉴 전송
  python main.py --date 2026-11-12  # 특정 날짜
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from pathlib import Path

import config
from menu.formatter import format_compact, format_message
from menu.summarizer import summarize
from menu.scraper import MEALS, get_lunch_menu

LOG_DIR = Path(__file__).parent / "logs"


def setup_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_DIR / "bot.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


FAIL_MARK = "불러오지 못했어요"


def _write_out(path: str, text: str, date: dt.date | None = None, failed: int = 0) -> None:
    """파일 저장. 단, 오늘 이미 더 잘 만든 파일이 있으면 덮어쓰지 않음.

    GitHub 서버에서 KAIST 접속이 가끔 시간 초과되므로 하루에 여러 번 실행하는데,
    나중 실행이 실패했다고 앞서 성공한 오늘 메뉴를 지우면 안 되기 때문.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if date is not None and out.exists():
        old = out.read_text(encoding="utf-8")
        old_today = bool(old) and f"{date:%m/%d}" in old.splitlines()[0]
        old_failed = old.count(FAIL_MARK)
        if old_today and failed > old_failed:
            logging.info("오늘 이미 더 나은 메뉴 파일이 있어 유지합니다 (실패 %d → %d)", old_failed, failed)
            return
    out.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="전송하지 않고 출력만")
    parser.add_argument("--date", help="YYYY-MM-DD (기본: 오늘)")
    parser.add_argument("--force", action="store_true", help="메뉴가 비어도 전송")
    parser.add_argument("--full", action="store_true", help="요약 없이 전체 메뉴")
    parser.add_argument("--meal", choices=["lunch", "dinner"], default="lunch", help="점심(lunch) / 저녁(dinner)")
    parser.add_argument("--out", help="카톡으로 보내지 않고 이 파일에 저장 (iPhone 단축어용)")
    parser.add_argument("--list-rooms", action="store_true", help="열려 있는 카톡 채팅방 이름 출력")
    args = parser.parse_args()

    if args.list_rooms:
        from sender.kakao_pc import list_chat_windows

        rooms = list_chat_windows()
        print("\n".join(f"'{r}'" for r in rooms) or "열려 있는 채팅창이 없습니다.")
        return 0

    setup_logging()
    date = dt.date.fromisoformat(args.date) if args.date else dt.date.today()

    meal = MEALS[args.meal]
    menus = [get_lunch_menu(config.MENU_URL, code, name, date, meal) for code, name in config.CAFETERIAS]
    failed = 0
    for m in menus:
        if m.error:
            failed += 1
            logging.warning("%s 실패: %s", m.name, m.error)

    if failed == len(menus):
        logging.error("모든 식당 접속 실패")
        if args.out:  # 빈 파일 (오늘 이미 성공한 파일이 있으면 유지)
            _write_out(args.out, "", date, failed)
        return 0

    if config.SKIP_IF_EMPTY and not args.force and all(m.empty for m in menus):
        logging.info("%s: 메뉴가 없어 전송하지 않습니다.", date)
        if args.out:  # 빈 파일 → 단축어가 보내지 않음 (어제 메뉴가 다시 가는 것 방지)
            _write_out(args.out, "", date, failed)
        return 0

    if args.full:
        text = format_message(menus, date)
    else:
        lines = summarize(
            menus,
            config.MAIN_KEYWORDS,
            config.DESSERT_KEYWORDS,
            getattr(config, "AFTER_RICE_KEYWORDS", ()),
            getattr(config, "MUST_SHOW_KEYWORDS", ()),
        )
        text = format_compact(menus, lines, config.SHORT_NAMES, date, config.SHOW_PRICE)

    if args.dry_run:
        print(text)
        return 0

    if args.out:
        _write_out(args.out, text, date, failed)
        logging.info("%s 처리 완료 (실패 식당 %d곳)", args.out, failed)
        return 0

    from sender.kakao_pc import send_message

    send_message(config.ROOM_NAME, text)
    logging.info("'%s' 방에 전송 완료", config.ROOM_NAME)
    return 0


if __name__ == "__main__":
    sys.exit(main())
