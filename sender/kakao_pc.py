"""Windows PC 카카오톡에 메시지를 입력하고 전송한다.

전제:
- Windows에서 PC 카카오톡이 실행 중이고 로그인되어 있어야 함
- 화면 잠금 상태에서는 동작하지 않을 수 있음

카카오톡 PC 버전이 업데이트되면 창 구조(클래스 이름)가 바뀌어
수정이 필요할 수 있습니다.
"""

from __future__ import annotations

import logging
import time

log = logging.getLogger(__name__)


def _win32():
    try:
        import win32api
        import win32con
        import win32gui
    except ImportError as exc:  # Windows가 아니거나 pywin32 미설치
        raise RuntimeError("pywin32가 필요합니다: pip install pywin32") from exc
    return win32api, win32con, win32gui


def _press_enter(hwnd) -> None:
    win32api, win32con, _ = _win32()
    win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
    time.sleep(0.05)
    win32api.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_RETURN, 0)


def _open_chatroom(room_name: str) -> None:
    """카카오톡 메인 창의 검색창에 방 이름을 넣고 Enter로 채팅방을 연다."""
    win32api, win32con, win32gui = _win32()
    main = win32gui.FindWindow(None, "카카오톡")
    if not main:
        raise RuntimeError("카카오톡 창을 찾지 못했습니다. PC 카카오톡을 켜 주세요.")

    child = win32gui.FindWindowEx(main, None, "EVA_ChildWindow", None)
    win1 = win32gui.FindWindowEx(child, None, "EVA_Window", None)
    win2 = win32gui.FindWindowEx(child, win1, "EVA_Window", None)  # 채팅 탭
    search = win32gui.FindWindowEx(win2, None, "Edit", None)
    if not search:
        raise RuntimeError("카카오톡 검색창을 찾지 못했습니다. '채팅' 탭을 한 번 열어 두세요.")

    win32api.SendMessage(search, win32con.WM_SETTEXT, 0, room_name)
    time.sleep(1)
    _press_enter(search)
    time.sleep(1.5)
    # 검색어를 지워 채팅 목록 필터를 원래대로 되돌림
    win32api.SendMessage(search, win32con.WM_SETTEXT, 0, "")


def list_chat_windows() -> list[str]:
    """현재 열려 있는 카카오톡 채팅방 창 제목 목록 (입력창이 있는 창만)."""
    _, _, win32gui = _win32()
    titles: list[str] = []

    def cb(hwnd, _):
        title = win32gui.GetWindowText(hwnd)
        if title and win32gui.IsWindowVisible(hwnd) and win32gui.FindWindowEx(hwnd, None, "RichEdit50W", None):
            titles.append(title)
        return True

    win32gui.EnumWindows(cb, None)
    return titles


def _find_room(room_name: str):
    """제목이 정확히 같은 창 → 없으면 제목에 방 이름이 포함된 채팅창."""
    _, _, win32gui = _win32()
    hwnd = win32gui.FindWindow(None, room_name)
    if hwnd:
        return hwnd
    target = room_name.replace(" ", "")
    for title in list_chat_windows():
        if target in title.replace(" ", ""):
            return win32gui.FindWindow(None, title)
    return None


def send_message(room_name: str, text: str) -> None:
    win32api, win32con, win32gui = _win32()

    room = _find_room(room_name)
    if not room:
        _open_chatroom(room_name)
        for _ in range(10):  # 최대 5초 기다림
            room = _find_room(room_name)
            if room:
                break
            time.sleep(0.5)
    if not room:
        opened = list_chat_windows()
        raise RuntimeError(
            f"채팅방 '{room_name}'을(를) 열지 못했습니다.\n"
            f"지금 열려 있는 채팅창: {opened or '없음'}\n"
            "채팅방을 직접 열어 둔 상태에서 'python main.py --list-rooms'로 정확한 이름을 확인해 주세요."
        )

    edit = win32gui.FindWindowEx(room, None, "RichEdit50W", None)
    if not edit:
        raise RuntimeError("채팅 입력창을 찾지 못했습니다.")

    win32api.SendMessage(edit, win32con.WM_SETTEXT, 0, "")
    _set_clipboard(text.replace("\n", "\r\n"))

    # 카카오톡 창이 확실히 맨 앞에 왔을 때만 마우스·키보드 입력을 함.
    # (앞에 못 오면 클릭/Ctrl+V/Enter가 다른 프로그램(VS Code 등)으로 들어가기 때문)
    if not _bring_to_front(room):
        fg = win32gui.GetWindowText(win32gui.GetForegroundWindow())
        raise RuntimeError(
            f"카카오톡 창을 맨 앞으로 가져오지 못했습니다(현재 앞 창: '{fg}'). "
            "다른 프로그램에 입력하지 않도록 중단했어요."
        )

    _click_center(edit)
    _key_combo(win32con.VK_CONTROL, ord("V"))
    time.sleep(0.7)
    pasted = _edit_text_length(edit)
    log.info("Ctrl+V 후 입력창 글자 수: %s", pasted)
    if pasted == 0:
        raise RuntimeError("입력창에 메시지를 넣지 못했습니다.")

    # Enter 직전에 다시 한 번 앞 창 확인
    if win32gui.GetForegroundWindow() != room and not _bring_to_front(room):
        raise RuntimeError("Enter 직전에 카카오톡 창이 뒤로 갔습니다. 전송을 중단했어요.")
    _key_combo(win32con.VK_RETURN)
    time.sleep(1.5)

    left = _edit_text_length(edit)
    log.info("Enter 후 입력창 글자 수: %s", left)
    # 전송 후에도 카카오톡 입력창에 보이지 않는 글자가 몇 개(6자 정도) 남는 경우가 있어서,
    # '0자'가 아니라 '붙여넣은 양의 절반 이하로 줄었는지'로 성공을 판단
    if left > pasted // 2:
        raise RuntimeError("메시지를 입력했지만 전송되지 않았습니다.")


def _click_center(hwnd) -> None:
    win32api, win32con, win32gui = _win32()
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    x, y = (left + right) // 2, (top + bottom) // 2
    win32api.SetCursorPos((x, y))
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.2)


def _set_clipboard(text: str) -> None:
    import win32clipboard
    import win32con

    for _ in range(5):
        try:
            win32clipboard.OpenClipboard()
            break
        except Exception:
            time.sleep(0.2)
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()


def _bring_to_front(hwnd, tries: int = 5) -> bool:
    """창을 맨 앞으로. 성공 여부를 반환.

    Windows는 다른 프로그램(VS Code·명령 프롬프트 등)이 포커스를 가진 상태에서
    SetForegroundWindow를 막기 때문에, 입력 스레드를 잠시 연결(AttachThreadInput)하고
    '항상 위' 설정을 켰다 끄는 방법을 함께 씀.
    """
    import win32process

    win32api, win32con, win32gui = _win32()
    for _ in range(tries):
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        fg = win32gui.GetForegroundWindow()
        cur_tid = win32api.GetCurrentThreadId()
        fg_tid = win32process.GetWindowThreadProcessId(fg)[0] if fg else 0
        attached = False
        try:
            if fg_tid and fg_tid != cur_tid:
                win32process.AttachThreadInput(cur_tid, fg_tid, True)
                attached = True
            # Alt 키 눌렀다 떼기: 포그라운드 잠금 해제용
            win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
            win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
            flags = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, flags)
            win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, flags)
            win32gui.BringWindowToTop(hwnd)
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                pass
        finally:
            if attached:
                win32process.AttachThreadInput(cur_tid, fg_tid, False)
        time.sleep(0.4)
        if win32gui.GetForegroundWindow() == hwnd:
            return True
    return False


def _key_combo(*keys) -> None:
    win32api, win32con, _ = _win32()
    for k in keys:
        win32api.keybd_event(k, 0, 0, 0)
        time.sleep(0.05)
    for k in reversed(keys):
        win32api.keybd_event(k, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.05)


def _edit_text_length(edit) -> int:
    win32api, win32con, _ = _win32()
    return win32api.SendMessage(edit, win32con.WM_GETTEXTLENGTH, 0, 0)
