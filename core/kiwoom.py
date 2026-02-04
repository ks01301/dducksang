"""
키움증권 Open API+ 연동 모듈
"""
import sys
import os
import time  # [NEW] Rate Limiting용

# PyQt5 플러그인 경로 설정 (Qt platform plugin 오류 해결)
import PyQt5
pyqt5_path = os.path.dirname(PyQt5.__file__)
plugin_path = os.path.join(pyqt5_path, 'Qt5', 'plugins')
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugin_path

from PyQt5.QtWidgets import QApplication
from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import QEventLoop, pyqtSignal, QObject


class Kiwoom(QObject):
    """키움증권 Open API+ 연동 클래스"""
    
    # 조건검색 및 스캔 관련 시그널
    sig_condition_load = pyqtSignal(list)       # 조건식 목록 수신 시
    sig_condition_result = pyqtSignal(str, list)   # 조건검색 결과 (화면번호, [종목리스트])
    sig_real_condition = pyqtSignal(str, str, str) # 실시간 조건검색 (종목코드, 종류, 조건명)
    
    # [NEW] 체결/실시간 데이터 시그널
    sig_chejan_received = pyqtSignal(str, dict)    # 구분(0:주문체결, 1:잔고), 데이터딕셔너리
    sig_real_data = pyqtSignal(str, dict)          # 종목코드, 실시간데이터(가격, 등락률 등)
    sig_scan_result = pyqtSignal(str, list)      # 스마트 스캔 결과 수신 시 (tr_code, data_list)

    def __init__(self):
        super().__init__()
        # QApplication 인스턴스 확인 및 생성
        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication(sys.argv)
        
        # 키움 OpenAPI ActiveX 컨트롤 생성
        self.ocx = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        
        # 이벤트 루프 (비동기 데이터 수신 대기용)
        self.loops = {}
        
        # 데이터 저장용 딕셔너리
        self.data = {}
        self.account_holdings = []
        self.account_summary = {}
        self.account_list = [] # [NEW] 계좌번호 리스트
        self.login_err_code = None
        
        # [NEW] Rate Limiting (요청 제한)
        self.last_req_time = 0.0

        
        # 이벤트 연결
        self._connect_events()
    
    def _connect_events(self):
        """이벤트 핸들러 연결"""
        # [CHECK] 32비트 Python 환경 확인
        if sys.maxsize > 2**32:
            error_msg = (
                "❌ [키움API 오류] 64비트 Python 환경에서는 실행할 수 없습니다.\n"
                "키움증권 Open API는 32비트 프로그램이므로, 반드시 '32비트 Python'으로 실행해야 합니다.\n\n"
                "현재 환경: 64비트"
            )
            print(error_msg)
            raise Exception(error_msg)

        # 로그인 이벤트
        try:
            self.ocx.OnEventConnect.connect(self._on_event_connect)
        except AttributeError:
             error_msg = (
                "❌ [키움API 오류] 키움 Open API 컨트롤을 찾을 수 없습니다.\n"
                "1. 키움증권 Open API+가 설치되어 있는지 확인하세요.\n"
                "2. 32비트 Python 환경인지 다시 확인하세요.\n"
                "3. 관리자 권한으로 실행해 보세요."
            )
             print(error_msg)
             raise Exception(error_msg)

        # TR 데이터 수신 이벤트
        self.ocx.OnReceiveTrData.connect(self._on_receive_tr_data)
        # 주문 체결 이벤트
        # 주문 체결 이벤트
        self.ocx.OnReceiveChejanData.connect(self._on_receive_chejan_data)
        
        # [조건검색] 이벤트 연결
        self.ocx.OnReceiveConditionVer.connect(self._on_receive_condition_ver)
        self.ocx.OnReceiveTrCondition.connect(self._on_receive_tr_condition)
        self.ocx.OnReceiveRealCondition.connect(self._on_receive_real_condition)
        
        # [NEW] 실시간 데이터 이벤트 연결
        self.ocx.OnReceiveRealData.connect(self._on_receive_real_data)
        
        print("✅ 키움 API 이벤트 연결 완료")
    
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
        if 'login' in self.loops:
            self.loops['login'].exit()
    
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
            self.data['체결강도'] = self._get_comm_data(trcode, rqname, 0, "체결강도")
        
        elif rqname == "예수금조회":
            # 예수금 데이터 추출
            self.data['예수금'] = self._get_comm_data(trcode, rqname, 0, "예수금")
            self.data['d+2추정예수금'] = self._get_comm_data(trcode, rqname, 0, "d+2추정예수금")
            self.data['유가잔고평가액'] = self._get_comm_data(trcode, rqname, 0, "유가잔고평가액")
            self.data['총평가금액'] = self._get_comm_data(trcode, rqname, 0, "총평가금액")
        
        elif rqname == "주식분봉차트조회":
            cnt = self.ocx.dynamicCall("GetRepeatCnt(QString, QString)", trcode, rqname)
            data = []
            for i in range(cnt):
                date = self._get_comm_data(trcode, rqname, i, "체결시간")
                open_price = self._get_comm_data(trcode, rqname, i, "시가")
                high_price = self._get_comm_data(trcode, rqname, i, "고가")
                low_price = self._get_comm_data(trcode, rqname, i, "저가")
                close_price = self._get_comm_data(trcode, rqname, i, "현재가")
                volume = self._get_comm_data(trcode, rqname, i, "거래량")
                
                data.append({
                    '시간': date.strip(),
                    '시가': abs(int(open_price)),
                    '고가': abs(int(high_price)),
                    '저가': abs(int(low_price)),
                    '종가': abs(int(close_price)),
                    '거래량': abs(int(volume))
                })
            self.data['분봉'] = data
        
        elif rqname == "보유종목조회":
            # [FIX] opw00018 싱글 데이터(계좌 요약) 추출
            self.data['총매입금액'] = self._get_comm_data(trcode, rqname, 0, "총매입금액")
            self.data['총평가금액'] = self._get_comm_data(trcode, rqname, 0, "총평가금액")
            self.data['총평가손익금액'] = self._get_comm_data(trcode, rqname, 0, "총평가손익금액")
            self.data['총수익률(%)'] = self._get_comm_data(trcode, rqname, 0, "총수익률(%)")
            self.data['추정예탁자산'] = self._get_comm_data(trcode, rqname, 0, "추정예탁자산")

            # 보유 종목 데이터 추출 (여러 종목)
            cnt = self.ocx.dynamicCall("GetRepeatCnt(QString, QString)", trcode, rqname)
            holdings = []
            for i in range(cnt):
                holding = {
                    '종목코드': self._get_comm_data(trcode, rqname, i, "종목번호").strip(),
                    '종목명': self._get_comm_data(trcode, rqname, i, "종목명").strip(),
                    '보유수량': int(self._get_comm_data(trcode, rqname, i, "보유수량") or 0),
                    '매입가': int(self._get_comm_data(trcode, rqname, i, "매입가") or 0),
                    '현재가': abs(int(self._get_comm_data(trcode, rqname, i, "현재가") or 0)),
                    '평가손익': int(self._get_comm_data(trcode, rqname, i, "평가손익") or 0),
                    '수익률': float(self._get_comm_data(trcode, rqname, i, "수익률(%)") or 0.0)
                }
                holdings.append(holding)
            self.data['보유종목'] = holdings
            # [FIX] 지속성 있는 멤버 변수에도 저장 (MainWindow에서 안정적으로 접근 가능하도록)
            self.account_holdings = holdings
            # 계좌 요약 정보도 저장
            self.account_summary = {
                '총매입금액': self.data.get('총매입금액'),
                '총평가금액': self.data.get('총평가금액'),
                '총평가손익금액': self.data.get('총평가손익금액'),
                '총수익률(%)': self.data.get('총수익률(%)'),
                '추정예탁자산': self.data.get('추정예탁자산')
            }
        
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
                volume = self._get_comm_data(trcode, rqname, i, "거래량")
                
                data.append({
                    '일자': date.strip(),
                    '시가': abs(int(open_price)),
                    '고가': abs(int(high_price)),
                    '저가': abs(int(low_price)),
                    '종가': abs(int(close_price)),
                    '거래량': abs(int(volume))
                })
            self.data['일봉'] = data
        
        elif trcode == "opt10032":  # 거래량급증요청
            self._on_receive_opt10032(trcode, rqname)
        elif trcode == "opt10019":  # 가격급등락요청
            self._on_receive_opt10019(trcode, rqname)
        
        # 이벤트 루프 종료
        if rqname in self.loops:
            self.loops[rqname].exit()
    
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
            order_status = self.ocx.dynamicCall("GetChejanData(int)", 913)  # 주문상태 (접수/체결/확인 등)
            
            print(f"\n📢 주문 체결: {stock_name}({stock_code})")
            print(f"   주문번호: {order_no}")
            print(f"   주문구분: {order_type}")
            print(f"   주문상태: {order_status}")
            print(f"   체결수량: {filled_qty} / {order_qty}")
            print(f"   체결가격: {filled_price}원")
            
            # [NEW] UI 및 전략으로 체결 정보 전송
            info = {
                '주문번호': order_no,
                '종목코드': stock_code,
                '종목명': stock_name,
                '주문구분': order_type, # +매수, -매도
                '주문상태': order_status, # [NEW] 접수/체결 구분용
                '체결수량': filled_qty,
                '체결가격': filled_price,
                '주문수량': order_qty,
                '주문가격': order_price
            }
            self.sig_chejan_received.emit("0", info)

    def _on_receive_real_data(self, code, real_type, real_data):
        """실시간 데이터 수신 (OnReceiveRealData)"""
        if real_type == "주식체결":
            # 현재가 (FID 10)
            current_price = self.ocx.dynamicCall("GetCommRealData(QString, int)", code, 10)
            current_price = abs(int(current_price))
            
            # 등락율 (FID 12)
            rate = self.ocx.dynamicCall("GetCommRealData(QString, int)", code, 12)
            # 누적거래량 (FID 13)
            volume = self.ocx.dynamicCall("GetCommRealData(QString, int)", code, 13)
            # 체결강도 (FID 228)
            strength = self.ocx.dynamicCall("GetCommRealData(QString, int)", code, 228)
            
            data = {
                'current_price': float(current_price),
                'rate': float(rate) if rate else 0.0,
                'volume': int(volume) if volume else 0,
                'strength': float(strength) if strength else 0.0
            }
            
            # 메인 윈도우로 전송
            self.sig_real_data.emit(code, data)
    
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
            
            # 로그인 시도
            self.ocx.dynamicCall("CommConnect()")
            
            # 이벤트 루프 생성 및 대기
            self.loops['login'] = QEventLoop()
            self.loops['login'].exec_()
            
            # 로그인 성공 시
            if self.login_err_code == 0:
                return True
            
            # 특정 에러는 재시도하지 않음
            if self.login_err_code in [-105, -300, -301, -302, -303, -304, -305]:
                print("\n⚠️  재시도 불가능한 오류입니다. 입력값을 확인해주세요.")
                return False
        
        print(f"\n❌ {retry_count}회 재시도 후에도 로그인에 실패했습니다.")
        return False
    
    def get_connect_state(self):
        """접속 상태 확인 (0: 미접속, 1: 접속)"""
        return self.ocx.dynamicCall("GetConnectState()")
    
    def _wait_rate_limit(self):
        """API 요청 제한 대기 (초당 3~4회 제한 준수)"""
        elapsed = time.time() - self.last_req_time
        if elapsed < 0.25:  # 250ms 미만 경과 시 대기
            time.sleep(0.25 - elapsed)
        self.last_req_time = time.time()

    def get_login_info(self, tag):
        """로그인 정보 조회"""
        return self.ocx.dynamicCall("GetLoginInfo(QString)", tag)
    
    def get_current_price(self, stock_code):
        """주식 현재가 조회"""
        self._wait_rate_limit() # [NEW] 과부하 방지
        self.data.clear() # [FIX] 이전 데이터 잔존 방지
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "종목코드", stock_code)
        ret = self.ocx.dynamicCall("CommRqData(QString, QString, int, QString)", "현재가조회", "opt10001", 0, "0101")
        
        if ret != 0:
            return {}

        # 데이터 수신 대기 (네임드 루프 사용)
        self.loops['현재가조회'] = QEventLoop()
        self.loops['현재가조회'].exec_()
        
        return self.data.copy()

    def set_real_reg(self, codes, fid_list="10", opt_type="1"):
        """
        실시간 데이터 등록 (SetRealReg)
        Args:
            codes: 종목코드 리스트 (또는 세미콜론 구분 문자열)
            fid_list: 실시간 FID 리스트 (기본: 10=현재가)
            opt_type: 등록타입 (0:교체, 1:추가)
        """
        if isinstance(codes, list):
            codes = ";".join(codes)
            
        # 화면번호는 '1000' 등으로 고정하거나 관리 필요
        self.ocx.dynamicCall("SetRealReg(QString, QString, QString, QString)", 
                             "1000", codes, fid_list, opt_type)
        # print(f"📡 실시간 등록 요청: {codes} (FID: {fid_list})")
    
    def get_account_balance(self, account_no):
        """
        예수금 조회 (opw00001 TR 사용)
        """
        self.data['예수금'] = {}
        
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "계좌번호", account_no)
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "비밀번호", "")
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "비밀번호입력매체구분", "00")
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "조회구분", "2")
        
        self._wait_rate_limit() # [NEW] 과부하 방지
        ret = self.ocx.dynamicCall(
            "CommRqData(QString, QString, int, QString)",
            "예수금조회", "opw00001", 0, "0102"
        )
        
        if ret != 0:
            return {}

        self.loops['예수금조회'] = QEventLoop()
        self.loops['예수금조회'].exec_()
        
        return self.data.copy()
    
    def get_holdings(self, account_no):
        """
        보유 종목 조회 (opw00018 TR 사용)
        """
        self.data['보유종목'] = []
        
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "계좌번호", account_no)
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "비밀번호", "")
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "비밀번호입력매체구분", "00")
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "조회구분", "1")
        
        ret = self.ocx.dynamicCall(
            "CommRqData(QString, QString, int, QString)",
            "보유종목조회", "opw00018", 0, "0103"
        )
        
        if ret != 0:
            return []

        self.loops['보유종목조회'] = QEventLoop()
        self.loops['보유종목조회'].exec_()
        
        return self.data.get('보유종목', [])
    
    def send_order(self, order_type, stock_code, quantity, price, account_no):
        """
        매수/매도 주문 (SendOrder 직접 호출)
        """
        hoga_type = "03" if price == 0 else "00"
        
        # dynamicCall 대신 직접 메서드 호출하여 8개 인자 제한 회피
        result = self.ocx.SendOrder(
            "주문", "0104", account_no, order_type, stock_code, int(quantity), int(price), hoga_type, ""
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
        """
        self.data['일봉'] = []
        
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "종목코드", stock_code)
        # [FIX] date가 None이면 빈 문자열로 변환 (오늘 날짜 기준 조회)
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "기준일자", date if date else "")
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "수정주가구분", "1")
        
        self._wait_rate_limit() # [NEW] 과부하 방지
        ret = self.ocx.dynamicCall(
            "CommRqData(QString, QString, int, QString)", 
            "주식일봉차트조회", "opt10081", 0, "0104"
        )
        
        if ret != 0:
            print(f"❌ TR 요청 실패 (코드: {ret})")
            return []
            
        self.loops['주식일봉차트조회'] = QEventLoop()
        self.loops['주식일봉차트조회'].exec_()
        
        return self.data.get('일봉', [])

    def get_minute_data(self, stock_code, interval=3):
        """
        분봉 데이터 조회 (opt10080 TR)
        interval: 1, 3, 5, 10, 15, 30, 45, 60
        """
        self.data['분봉'] = []
        
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "종목코드", stock_code)
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "틱범위", str(interval))
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "수정주가구분", "1")
        
        self._wait_rate_limit() # [NEW] 과부하 방지
        ret = self.ocx.dynamicCall(
            "CommRqData(QString, QString, int, QString)", 
            "주식분봉차트조회", "opt10080", 0, "0106"
        )
        
        if ret != 0:
            print(f"❌ TR 요청 실패 (코드: {ret})")
            return []
            
        self.loops['주식분봉차트조회'] = QEventLoop()
        self.loops['주식분봉차트조회'].exec_()
        
        return self.data.get('분봉', [])


    # ========== 조건검색 메서드 ==========

    def get_condition_load(self):
        """서버에 저장된 사용자 조건식 리스트 요청"""
        ret = self.ocx.dynamicCall("GetConditionLoad()")
        if ret == 1:
            print("🔍 조건식 목록 요청 성공")
        else:
            print("❌ 조건식 목록 요청 실패")

    def send_condition(self, screen_no, condition_name, condition_index, is_real_time):
        """조건검색 실행 요청
        screen_no: 화면번호
        condition_name: 조건식 이름
        condition_index: 조건식 인덱스
        is_real_time: 0(단순조회), 1(실시간검색)
        """
        ret = self.ocx.dynamicCall("SendCondition(QString, QString, int, int)", 
                                   screen_no, condition_name, condition_index, is_real_time)
        if ret == 1:
            print(f"📡 조건검색 요청: {condition_name} (실시간: {is_real_time})")
        else:
            print(f"❌ 조건검색 요청 실패: {condition_name}")

    def send_condition_stop(self, screen_no, condition_name, condition_index):
        """조건검색 중지 요청"""
        self.ocx.dynamicCall("SendConditionStop(QString, QString, int)", 
                             screen_no, condition_name, condition_index)
        print(f"⏹ 조건검색 중지: {condition_name}")

    # ========== 조건검색 이벤트 핸들러 ==========

    def _on_receive_condition_ver(self, ret, msg):
        """조건식 목록 수신 이벤트"""
        if ret != 1:
            return
            
        condition_list_str = self.ocx.dynamicCall("GetConditionNameList()")
        # Format: "index^name;index^name;..."
        conditions = []
        if condition_list_str:
            raw_list = condition_list_str.split(';')
            for item in raw_list:
                if not item: continue
                index, name = item.split('^')
                conditions.append((int(index), name))
        
        print(f"✅ 조건식 목록 수신: {len(conditions)}개")
        self.sig_condition_load.emit(conditions)

    def _on_receive_tr_condition(self, screen_no, code_list_str, condition_name, index, next):
        """조건검색 결과 수신 (최초 조회, 실시간 X)"""
        codes = []
        if code_list_str:
            codes = code_list_str.split(';')
            codes = [c for c in codes if c] # 빈 문자열 제거
        
        print(f"🔍 조건검색 결과 [{condition_name}]: {len(codes)}개 발견")
        # index는 문자열일 수도 있음, 주의 (API 문서는 int지만 pyqt signal은?)
        # OnReceiveTrCondition(BSTR, BSTR, BSTR, int, int)
        self.sig_condition_result.emit(str(index), codes)

    def _on_receive_real_condition(self, code, type_str, condition_name, condition_index):
        """실시간 조건검색 편입/이탈
        type_str: "I"(편입), "D"(이탈)
        """
        type_kor = "편입" if type_str == "I" else "이탈"
        # print(f"⚡ 실시간 {type_kor}: {code} [{condition_name}]")
        self.sig_real_condition.emit(code, type_str, str(condition_index))

    # ========== 스마트 스캔 (TR 기반) 메서드 ==========

    def request_volume_surge(self, market="000", sort="1", time_unit="1", vol_unit="1"):
        """
        거래량 급증 종목 요청 (opt10032)
        market: 000:전체, 001:코스피, 101:코스닥
        sort: 1:급증량, 2:급증률
        time_unit: 1:1분, 3:3분, 5:5분, 10:10분, 30:30분, 60:60분
        vol_unit: 1:5일평균거래량대비
        """
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "시장구분", market)
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "정렬구분", sort)
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "시간구분", time_unit)
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "거래량구분", vol_unit)
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "시간", "1") # 직전 대비
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "종목조건", "0") # 전체
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "가격구분", "0") # 전체가격
        
        self._wait_rate_limit() # [NEW] 과부하 방지
        ret = self.ocx.dynamicCall("CommRqData(QString, QString, int, QString)", "거래량급증", "opt10032", 0, "1032")
        return ret

    def request_price_surge(self, market="000", up_down="1", time_unit="1"):
        """
        가격 급등락 종목 요청 (opt10019)
        market: 000:전체, 001:코스피, 101:코스닥
        up_down: 1:급등, 2:급락
        time_unit: 1:1분, 3:3분, 5:5분, 10:10분, 30:30분, 60:60분
        """
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "시장구분", market)
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "등락구분", up_down)
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "시간구분", time_unit)
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "시간", "1")
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "종목조건", "0")
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "가격구분", "0")
        
        self._wait_rate_limit() # [NEW] 과부하 방지
        ret = self.ocx.dynamicCall("CommRqData(QString, QString, int, QString)", "가격급등락", "opt10019", 0, "1019")
        return ret

    # ========== TR 응답 핸들러 ==========

    def _on_receive_opt10032(self, trcode, rqname):
        """거래량 급증 결과 처리"""
        count = self.ocx.dynamicCall("GetRepeatCnt(QString, QString)", trcode, rqname)
        results = []
        for i in range(count):
            code = self._get_comm_data(trcode, rqname, i, "종목코드")
            name = self._get_comm_data(trcode, rqname, i, "종목명")
            volume_rate = self._get_comm_data(trcode, rqname, i, "급증량") # % 단위일 수 있음
            price = self._get_comm_data(trcode, rqname, i, "현재가")
            price_rate = self._get_comm_data(trcode, rqname, i, "등락율")
            
            results.append({
                'code': code.strip(),
                'name': name.strip(),
                'volume_rate': float(volume_rate.replace('%', '') or 0),
                'price': abs(int(price or 0)),
                'price_rate': float(price_rate or 0)
            })
        self.sig_scan_result.emit(trcode, results)

    def _on_receive_opt10019(self, trcode, rqname):
        """가격 급등락 결과 처리"""
        count = self.ocx.dynamicCall("GetRepeatCnt(QString, QString)", trcode, rqname)
        results = []
        for i in range(count):
            code = self._get_comm_data(trcode, rqname, i, "종목코드")
            name = self._get_comm_data(trcode, rqname, i, "종목명")
            price = self._get_comm_data(trcode, rqname, i, "현재가")
            price_rate = self._get_comm_data(trcode, rqname, i, "등락율")
            volume = self._get_comm_data(trcode, rqname, i, "거래량")
            
            results.append({
                'code': code.strip(),
                'name': name.strip(),
                'price': abs(int(price or 0)),
                'price_rate': float(price_rate or 0),
                'volume': int(volume or 0)
            })
        self.sig_scan_result.emit(trcode, results)


if __name__ == "__main__":
    kiwoom = Kiwoom()
    print("Kiwoom 클래스 초기화 성공!")
