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
        
        # 이벤트 루프 종료
        if self.event_loop:
            self.event_loop.exit()
    
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
        """
        주식 현재가 조회 (opt10001 TR 사용)
        
        Args:
            stock_code: 종목코드 (예: "005930")
        
        Returns:
            dict: 현재가 정보 (종목명, 현재가, 등락율 등)
        """
        # 입력값 설정
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "종목코드", stock_code)
        
        # TR 요청 (opt10001: 주식기본정보요청)
        self.ocx.dynamicCall(
            "CommRqData(QString, QString, int, QString)",
            "현재가조회",  # rqname (요청 이름)
            "opt10001",    # trcode (TR 코드)
            0,             # prev_next (0: 조회)
            "0101"         # screen_no (화면번호)
        )
        
        # 데이터 수신 대기
        self.event_loop = QEventLoop()
        self.event_loop.exec_()
        
        return self.data.copy()


if __name__ == "__main__":
    # 모듈 테스트용 코드
    kiwoom = Kiwoom()
    print("Kiwoom 클래스 초기화 성공!")
