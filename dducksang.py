"""
삼성전자(005930) 현재가 조회 테스트
"""
from kiwoom import Kiwoom


def main():
    # 키움 API 객체 생성
    kiwoom = Kiwoom()
    
    # 로그인 (로그인 창이 뜹니다, 재시도 로직 포함)
    if not kiwoom.login():
        print("\n프로그램을 종료합니다.")
        return
    
    # 접속 상태 확인
    if kiwoom.get_connect_state() == 1:
        print("=" * 50)
        print("📊 접속 정보")
        print("=" * 50)
        
        # 계좌 정보 출력
        account_list = kiwoom.get_login_info("ACCNO")
        print(f"계좌번호 목록: {account_list}")
        
        user_id = kiwoom.get_login_info("USER_ID")
        print(f"사용자 ID: {user_id}")
        
        print()
        print("=" * 50)
        print("📈 삼성전자(005930) 현재가 조회")
        print("=" * 50)
        
        # 삼성전자 현재가 조회
        stock_code = "005930"
        data = kiwoom.get_current_price(stock_code)
        
        # 결과 출력
        print(f"종목명: {data.get('종목명', 'N/A')}")
        
        # 현재가는 음수로 오면 하락, 양수면 상승
        current_price = data.get('현재가', '0')
        price_value = abs(int(current_price)) if current_price else 0
        print(f"현재가: {price_value:,}원")
        
        print(f"등락율: {data.get('등락율', 'N/A')}%")
        
        volume = data.get('거래량', '0')
        volume_value = int(volume) if volume else 0
        print(f"거래량: {volume_value:,}")
        
        # 시가/고가/저가
        open_price = abs(int(data.get('시가', '0') or '0'))
        high_price = abs(int(data.get('고가', '0') or '0'))
        low_price = abs(int(data.get('저가', '0') or '0'))
        print(f"시가: {open_price:,}원 | 고가: {high_price:,}원 | 저가: {low_price:,}원")
        
        print("=" * 50)
    else:
        print("❌ 로그인에 실패했습니다.")


if __name__ == "__main__":
    main()