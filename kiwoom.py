"""
키움증권 Open API+ 연동 모듈
"""
import sys
import os

# PyQt5 플러그인 경로 설정 (Qt platform plugin 오류 해결)
import PyQt5
pyqt5_path = os.path.dirname(PyQt5.__file__)
plugin_path = os.path.join(pyqt5_path, 'Qt5', 'plugins')
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugin_path

from PyQt5.QtWidgets import QApplication
from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import QEventLoop


class Kiwoom:
    """키움증권 Open API+ 연동 클래스"""
    
    def __init__(self):
        # QApplication 인스턴스 확인 및 생성
        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication(sys.argv)
        
        # 키움 OpenAPI ActiveX 컨트롤 생성
        self.ocx = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        
        # 이벤트 루프 (비동기 데이터 수신 대기용)
        self.event_loop = None
        
        # 데이터 저장용 딕셔너리
        self.data = {}
        
        # 로그인 상태
        self.login_err_code = None
        
        # 이벤트 연결
        self._connect_events()
    
    def _connect_events(self):
        """이벤트 핸들러 연결"""
        # 로그인 이벤트
        self.ocx.OnEventConnect.connect(self._on_event_connect)
        # TR 데이터 수신 이벤트
        self.ocx.OnReceiveTrData.connect(self._on_receive_tr_data)
        # 주문 체결 이벤트
        self.ocx.OnReceiveChejanData.connect(self._on_receive_chejan_data)
    
    # ========== 이벤트 핸들러 ==========
    
    def _on_event_connect(self, err_code):
        """로그인 이벤트 처리"""
        self.login_err_code = err_code
        
        if err_code == 0:
            print("✅ 로그인 성공!")
        else:
            error_msg = self._get_login_error_message(err_code)
            print(f"❌ 로그인 실패: {error_msg} (에러코드: {err_code})")
        
        # 이벤트 루프 종료
        if self.event_loop:
            self.event_loop.exit()
    
    def _on_receive_tr_data(self, screen_no, rqname, trcode, record_name, 
                            prev_next, data_len, err_code, msg1, msg2):
        """TR 데이터 수신 이벤트 처리"""
        if rqname == "현재가조회":
            # 현재가 데이터 추출
            self.data['현재가'] = self._get_comm_data(trcode, rqname, 0, "현재가")
            self.data['종목명'] = self._get_comm_data(trcode, rqname, 0, "종목명")
            self.data['등락율'] = self._get_comm_data(trcode, rqname, 0, "등락율")
            self.data['거래량'] = self._get_comm_data(trcode, rqname, 0, "거래량")
            self.data['시가'] = self._get_comm_data(trcode, rqname, 0, "시가")
            self.data['고가'] = self._get_comm_data(trcode, rqname, 0, "고가")
            self.data['저가'] = self._get_comm_data(trcode, rqname, 0, "저가")
        
        elif rqname == "예수금조회":
            # 예수금 데이터 추출
            self.data['예수금'] = self._get_comm_data(trcode, rqname, 0, "예수금")
            self.data['d+2추정예수금'] = self._get_comm_data(trcode, rqname, 0, "d+2추정예수금")
            self.data['유가잔고평가액'] = self._get_comm_data(trcode, rqname, 0, "유가잔고평가액")
            self.data['총평가금액'] = self._get_comm_data(trcode, rqname, 0, "총평가금액")
        
        elif rqname == "보유종목조회":
            # 보유 종목 데이터 추출 (여러 종목)
            cnt = self.ocx.dynamicCall("GetRepeatCnt(QString, QString)", trcode, rqname)
            holdings = []
            for i in range(cnt):
                holding = {
                    '종목코드': self._get_comm_data(trcode, rqname, i, "종목번호"),
                    '종목명': self._get_comm_data(trcode, rqname, i, "종목명"),
                    '보유수량': self._get_comm_data(trcode, rqname, i, "보유수량"),
                    '매입가': self._get_comm_data(trcode, rqname, i, "매입가"),
                    '현재가': self._get_comm_data(trcode, rqname, i, "현재가"),
                    '평가손익': self._get_comm_data(trcode, rqname, i, "평가손익"),
                    '수익률': self._get_comm_data(trcode, rqname, i, "수익률(%)")
                }
                holdings.append(holding)
            self.data['보유종목'] = holdings
        
        elif rqname == "주식일봉차트조회":
            # 일봉 데이터 추출 (600일치)
            cnt = self.ocx.dynamicCall("GetRepeatCnt(QString, QString)", trcode, rqname)
            data = []
            for i in range(cnt):
                date = self._get_comm_data(trcode, rqname, i, "일자")
                open_price = self._get_comm_data(trcode, rqname, i, "시가")
                high_price = self._get_comm_data(trcode, rqname, i, "고가")
                low_price = self._get_comm_data(trcode, rqname, i, "저가")
                close_price = self._get_comm_data(trcode, rqname, i, "현재가")
                
                data.append({
                    '일자': date.strip(),
                    '시가': abs(int(open_price)),
                    '고가': abs(int(high_price)),
                    '저가': abs(int(low_price)),
                    '종가': abs(int(close_price))
                })
            self.data['일봉'] = data
        
        # 이벤트 루프 종료
        if self.event_loop:
            self.event_loop.exit()
    
    def _on_receive_chejan_data(self, gubun, item_cnt, fid_list):
        """주문 체결 이벤트 처리"""
        if gubun == "0":  # 주문 체결
            order_no = self.ocx.dynamicCall("GetChejanData(int)", 9203)  # 주문번호
            stock_code = self.ocx.dynamicCall("GetChejanData(int)", 9001)  # 종목코드
            stock_name = self.ocx.dynamicCall("GetChejanData(int)", 302)  # 종목명
            order_type = self.ocx.dynamicCall("GetChejanData(int)", 905)  # 주문구분
            order_qty = self.ocx.dynamicCall("GetChejanData(int)", 900)  # 주문수량
            order_price = self.ocx.dynamicCall("GetChejanData(int)", 901)  # 주문가격
            filled_qty = self.ocx.dynamicCall("GetChejanData(int)", 911)  # 체결수량
            filled_price = self.ocx.dynamicCall("GetChejanData(int)", 910)  # 체결가격
            
            print(f"\n📢 주문 체결: {stock_name}({stock_code})")
            print(f"   주문번호: {order_no}")
            print(f"   주문구분: {order_type}")
            print(f"   체결수량: {filled_qty} / {order_qty}")
            print(f"   체결가격: {filled_price}원")
    
    # ========== API 메서드 ==========
    
    def _get_comm_data(self, trcode, rqname, index, item_name):
        """데이터 조회 (GetCommData 호출)"""
        data = self.ocx.dynamicCall(
            "GetCommData(QString, QString, int, QString)", 
            trcode, rqname, index, item_name
        )
        return data.strip()
    
    def _get_login_error_message(self, err_code):
        """로그인 에러 코드별 메시지 반환"""
        error_messages = {
            0: "정상처리",
            -100: "사용자 정보 교환 실패",
            -101: "서버 접속 실패",
            -102: "버전 처리 실패",
            -103: "개인 방화벽 실패",
            -104: "메모리 보호 실패",
            -105: "함수 입력값 오류",
            -106: "통신 연결 종료",
            -200: "시세 조회 과부하",
            -201: "전문 작성 초기화 실패",
            -202: "전문 작성 입력값 오류",
            -203: "데이터 없음",
            -300: "주문 입력값 오류",
            -301: "계좌 비밀번호 없음",
            -302: "타인 계좌 사용 오류",
            -303: "주문가격이 주문착오 금액 기준 초과",
            -304: "주문수량이 총 발행주수의 1% 초과",
            -305: "주문수량이 주문착오 수량 기준 초과"
        }
        return error_messages.get(err_code, "알 수 없는 오류")
    
    def login(self, retry_count=3, retry_delay=2):
        """
        로그인 (CommConnect 호출)
        
        Args:
            retry_count: 재시도 횟수 (기본 3회)
            retry_delay: 재시도 대기 시간(초) (기본 2초)
        
        Returns:
            bool: 로그인 성공 여부
        """
        import time
        
        for attempt in range(retry_count):
            if attempt > 0:
                print(f"\n⏳ {retry_delay}초 후 재시도합니다... ({attempt + 1}/{retry_count})")
                time.sleep(retry_delay)
            
            print("🔐 로그인 창을 띄웁니다...")
            self.login_err_code = None
            self.ocx.dynamicCall("CommConnect()")
            
            # 로그인 완료까지 대기
            self.event_loop = QEventLoop()
            self.event_loop.exec_()
            
            # 로그인 성공 시
            if self.login_err_code == 0:
                return True
            
            # 특정 에러는 재시도하지 않음
            if self.login_err_code in [-105, -300, -301, -302, -303, -304, -305]:
                print("\n⚠️  재시도 불가능한 오류입니다. 입력값을 확인해주세요.")
                return False
        
        print(f"\n❌ {retry_count}회 재시도 후에도 로그인에 실패했습니다.")
        print("💡 해결 방법:")
        print("   1. 영웅문 HTS를 재시작해보세요")
        print("   2. 잠시 후 다시 시도해보세요 (서버 과부하일 수 있음)")
        print("   3. 키움증권 Open API+ 모듈이 정상 설치되어 있는지 확인하세요")
        return False
    
    def get_connect_state(self):
        """접속 상태 확인 (0: 미접속, 1: 접속)"""
        return self.ocx.dynamicCall("GetConnectState()")
    
    def get_login_info(self, tag):
        """로그인 정보 조회"""
        return self.ocx.dynamicCall("GetLoginInfo(QString)", tag)
    
    def get_current_price(self, stock_code):
        """주식 현재가 조회"""
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "종목코드", stock_code)
        self.ocx.dynamicCall("CommRqData(QString, QString, int, QString)", "현재가조회", "opt10001", 0, "0101")
        self.event_loop = QEventLoop()
        self.event_loop.exec_()
        return self.data.copy()
    
    def get_account_balance(self, account_no):
        """
        예수금 조회 (opw00001 TR 사용)
        
        Args:
            account_no: 계좌번호
        
        Returns:
            dict: 예수금 정보
        """
        self.data['예수금'] = {}
        
        # 입력값 설정
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "계좌번호", account_no)
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "비밀번호", "")
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "비밀번호입력매체구분", "00")
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "조회구분", "2")
        
        # TR 요청
        self.ocx.dynamicCall(
            "CommRqData(QString, QString, int, QString)",
            "예수금조회", "opw00001", 0, "0102"
        )
        
        # 데이터 수신 대기
        self.event_loop = QEventLoop()
        self.event_loop.exec_()
        
        return self.data.copy()
    
    def get_holdings(self, account_no):
        """
        보유 종목 조회 (opw00018 TR 사용)
        
        Args:
            account_no: 계좌번호
        
        Returns:
            list: 보유 종목 리스트
        """
        self.data['보유종목'] = []
        
        # 입력값 설정
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "계좌번호", account_no)
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "비밀번호", "")
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "비밀번호입력매체구분", "00")
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "조회구분", "1")
        
        # TR 요청
        self.ocx.dynamicCall(
            "CommRqData(QString, QString, int, QString)",
            "보유종목조회", "opw00018", 0, "0103"
        )
        
        # 데이터 수신 대기
        self.event_loop = QEventLoop()
        self.event_loop.exec_()
        
        return self.data.get('보유종목', [])
    
    def send_order(self, order_type, stock_code, quantity, price, account_no):
        """
        매수/매도 주문 (SendOrder 사용)
        
        Args:
            order_type: 주문 유형 (1: 매수, 2: 매도)
            stock_code: 종목코드
            quantity: 주문 수량
            price: 주문 가격 (0: 시장가)
            account_no: 계좌번호
        
        Returns:
            int: 주문번호 (0: 실패)
        """
        # 시장가/지정가 구분
        hoga_type = "03" if price == 0 else "00"
        
        # SendOrder 호출
        result = self.ocx.dynamicCall(
            "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
            "주문",              # sRQName
            "0104",             # sScreenNo
            account_no,         # sAccNo
            order_type,         # nOrderType (1: 신규매수, 2: 신규매도)
            stock_code,         # sCode
            quantity,           # nQty
            price,              # nPrice
            hoga_type,          # sHogaGb (00: 지정가, 03: 시장가)
            ""                  # sOrgOrderNo
        )
        
        if result == 0:
            type_str = "매수" if order_type == 1 else "매도"
            print(f"✅ 주문 전송 성공: {type_str} {stock_code} {quantity}주")
        else:
            print(f"❌ 주문 전송 실패 (에러코드: {result})")
        
        return result
    
    def get_daily_data(self, stock_code, date=None):
        """
        일봉 데이터 조회 (opt10081 TR)
        
        Args:
            stock_code: 종목코드
            date: 기준 일자 (YYYYMMDD) - 생략 시 최근일
            
        Returns:
            list: 일봉 데이터 리스트 (최신순)
        """
        self.data['일봉'] = []  # 초기화
        
        # SetInputValue
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "종목코드", stock_code)
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "기준일자", date if date else "")
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "수정주가구분", "1")
        
        # CommRqData
        ret = self.ocx.dynamicCall(
            "CommRqData(QString, QString, int, QString)", 
            "주식일봉차트조회", 
            "opt10081", 
            0, 
            "0105"
        )
        
        if ret != 0:
            print(f"❌ 일봉 조회 요청 실패 (코드: {ret})")
            return []
            
        # 이벤트 루프 대기
        self.event_loop = QEventLoop()
        self.event_loop.exec_()
        
        return self.data.get('일봉', [])


if __name__ == "__main__":
    kiwoom = Kiwoom()
    print("Kiwoom 클래스 초기화 성공!")
