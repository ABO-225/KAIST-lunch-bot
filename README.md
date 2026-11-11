# KAIST 점심 메뉴 카카오톡 봇

매일 11:30에 KAIST 동측 학생식당, 서측식당, 북측식당(카이마루)의 점심 메뉴와 가격을
PC 카카오톡 채팅방("그 과목")에 보냅니다.

## 구조
```
config.py            채팅방 이름, 식당 목록
main.py              실행 진입점 (--dry-run / --date / --force)
menu/scraper.py      KAIST 페이지에서 중식 메뉴·가격 파싱
menu/formatter.py    카톡 메시지 문자열 생성
sender/kakao_pc.py   Windows PC 카카오톡 창에 입력 후 전송
run_daily.bat        스케줄러가 실행하는 파일
install_schedule.bat 매일 11:30 작업 등록
tests/               파서 테스트
```

## 설치 (Windows)
1. Python 3.10+ 설치 (설치 시 "Add to PATH" 체크)
2. `pip install -r requirements.txt`
3. `python main.py --dry-run` 으로 메시지 확인
4. PC 카카오톡 로그인 후 `python main.py` 로 실제 전송 테스트
5. `install_schedule.bat` 실행 → 매일 11:30 자동 전송

## 주의
- 11:30에 PC가 켜져 있고, 카카오톡이 로그인되어 있어야 합니다. 화면 잠금 상태에서는 실패할 수 있어요.
- 카카오톡 PC 업데이트로 창 구조가 바뀌면 `sender/kakao_pc.py` 수정이 필요할 수 있어요.
- 개인 계정 자동화는 카카오 이용약관상 제한될 수 있으니 소규모·개인 용도로 쓰세요.
