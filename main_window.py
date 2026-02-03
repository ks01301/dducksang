"""
키움증권 자동매매 프로그램 메인 GUI
"""
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QTableWidget, 
    QTableWidgetItem, QGroupBox, QMessageBox, QHeaderView, QTabWidget,
    QFormLayout, QFrame, QComboBox, QStackedWidget, QSpacerItem, QSizePolicy,
    QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSlot, QTimer, QTime
from PyQt5.QtGui import QFont
from PyQt5.QtGui import QFont
from kiwoom import Kiwoom
from asset_manager import AssetManager
from database import Database
from strategy import VolatilityBreakoutStrategy

VERSION = "1.0.0"

class MainWindow(QMainWindow):
    """메인 윈도우 클래스"""
    
    def __init__(self):
        super().__init__()
        
        # 키움 API 객체
        self.kiwoom = None
        
        # 자산 관리자 및 데이터베이스
        self.asset_manager = AssetManager()
        self.db = Database()
        
        # 전략 초기화
        self.strategy = VolatilityBreakoutStrategy(self.kiwoom, self.asset_manager)
        self.strategy.log_msg.connect(self.log)
        
        # 자동매매 상태 변수
        self.is_trading_active = False
        self.polling_index = 0  # 감시 종목 순차 조회용 인덱스
        
        # 타이머 설정 (1초마다 상태 체크)
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_market_status)
        self.status_timer.start(1000)
        
        # [NEW] 발굴 검증 큐 및 타이머
        self.verification_queue = []
        self.verify_timer = QTimer(self)
        self.verify_timer.timeout.connect(self.process_verification_queue)
        self.verify_timer.start(500) # 0.5초마다 하나씩 검증 (API 제한 방지)
        
        # [NEW] 자동 발굴 종목 관리 (TTL: 3회 미포착 시 제거)
        self.auto_stock_hits = {} # {code: hit_count}
        self.cleanup_timer = QTimer(self)
        self.cleanup_timer.timeout.connect(self.cleanup_auto_watchlist)
        self.cleanup_timer.start(180000) # 3분마다 청소
        
        # [NEW] 스마트 스캔 타이머
        self.scan_timer = QTimer(self)
        self.scan_timer.timeout.connect(self.request_smart_scan)
        
        # UI 초기화
        self.init_ui()
        
        # [NEW] 초기 전략 정보 반영
        self.refresh_strategy_info()
    
    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle(f"떡상기원 Ver {VERSION}")
        self.setGeometry(100, 100, 1200, 800)
        
        # 스택 위젯 생성 (0: 로그인, 1: 메인 앱)
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        
        # 1. 로그인 페이지 초기화
        self.page_login = QWidget()
        self.init_login_page()
        self.stack.addWidget(self.page_login)
        
        # 2. 메인 앱 페이지 초기화
        self.page_main = QWidget()
        self.init_main_app_ui()
        self.stack.addWidget(self.page_main)
        
        # 시작은 로그인 페이지
        self.stack.setCurrentIndex(0)

    def init_login_page(self):
        """로그인 페이지 초기화"""
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        
        # 제목
        title = QLabel(f"떡상기원 Ver {VERSION}")
        title.setStyleSheet("font-size: 30px; font-weight: bold; color: #E04F5F; margin-bottom: 20px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # 설명
        desc = QLabel("키움증권 OpenAPI 자동매매 시스템")
        desc.setStyleSheet("font-size: 16px; color: #555; margin-bottom: 50px;")
        desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc)
        
        # 로그인 버튼
        btn_login = QPushButton("로그인 시작")
        btn_login.setMinimumSize(200, 60)
        btn_login.setStyleSheet("""
            QPushButton { background-color: #007AFF; color: white; font-size: 18px; font-weight: bold; border-radius: 10px; }
            QPushButton:hover { background-color: #0056b3; }
        """)
        btn_login.clicked.connect(self.login)
        layout.addWidget(btn_login)
        
        self.page_login.setLayout(layout)

    def init_main_app_ui(self):
        """메인 애플리케이션 UI 초기화"""
        main_layout = QVBoxLayout(self.page_main)
        
        # 탭 위젯 생성
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # 탭 1: 자동매매 (메인)
        self.tab_trading = QWidget()
        self.init_trading_tab()
        self.tabs.addTab(self.tab_trading, "자동매매")
        
        # 탭 2: 자산관리
        self.tab_asset = QWidget()
        self.init_asset_tab()
        self.tabs.addTab(self.tab_asset, "자산관리")
        
        # 탭 3: 거래내역
        self.tab_history = QWidget()
        self.init_history_tab()
        self.tabs.addTab(self.tab_history, "거래내역")
        
        # 탭 4: 설정
        self.tab_setting = QWidget()
        self.init_setting_tab()
        self.tabs.addTab(self.tab_setting, "설정")
        
        # 4. 로그 영역 (공통) - 메인 화면 하단에 위치
        log_group = self.create_log_group()
        main_layout.addWidget(log_group)
        
        # 초기화 후 자산 현황 한 번 로드 (로그인 후 실행되므로 안전)
        # self.refresh_asset_status() -> 로그인 후에 호출됨


        
    def init_trading_tab(self):
        """자동매매 탭 초기화"""
        layout = QVBoxLayout()
        
        # 1. 사용자 접속 정보 (로그아웃 포함)
        user_info_group = self.create_user_info_group()
        layout.addWidget(user_info_group)
        
        # 0. 자동매매 제어 패널
        control_group = QGroupBox("시스템 제어")
        control_group.setStyleSheet("QGroupBox { font-weight: bold; border: 2px solid #555; border-radius: 5px; margin-top: 10px; }")
        control_layout = QGridLayout()
        
        # 상태 표시
        self.lbl_market_status = QLabel("준비")
        self.lbl_market_status.setStyleSheet("background-color: gray; color: white; padding: 5px; border-radius: 3px; font-weight: bold;")
        self.lbl_market_status.setAlignment(Qt.AlignCenter)
        
        self.lbl_trading_status = QLabel("중지됨")
        self.lbl_trading_status.setStyleSheet("color: red; font-weight: bold; font-size: 14px;")
        
        # 시작/중지 버튼
        self.btn_auto_start = QPushButton("자동매매 시작")
        self.btn_auto_start.setCheckable(True)
        self.btn_auto_start.setMinimumHeight(40)
        self.btn_auto_start.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; font-weight: bold; font-size: 14px; }
            QPushButton:checked { background-color: #f44336; }
        """)
        self.btn_auto_start.clicked.connect(self.toggle_trading)
        
        control_layout.addWidget(QLabel("장 상태:"), 0, 0)
        control_layout.addWidget(self.lbl_market_status, 0, 1)
        control_layout.addWidget(QLabel("동작 상태:"), 0, 2)
        control_layout.addWidget(self.lbl_trading_status, 0, 3)
        control_layout.addWidget(self.btn_auto_start, 1, 0, 1, 4)
        
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        # 0.6. 전략 설정 정보
        strategy_info_group = self.create_strategy_info_group()
        layout.addWidget(strategy_info_group)
        
        # 0.7. 감시 종목 (Separated Universe)
        manual_watchlist_group = self.create_manual_watchlist_group()
        layout.addWidget(manual_watchlist_group)
        
        auto_watchlist_group = self.create_auto_watchlist_group()
        layout.addWidget(auto_watchlist_group)
        
        # 2. 하단 로깅 영역 (기존 유지)
        log_group = self.create_log_group()
        layout.addWidget(log_group)
        
        # 2. 상단 영역 (종목조회 + 주문입력)
        top_layout = QHBoxLayout()
        
        # 2-1. 종목 조회 영역
        stock_info_group = self.create_stock_info_group()
        top_layout.addWidget(stock_info_group)
        
        # 2-2. 주문 입력 영역
        order_group = self.create_order_group()
        top_layout.addWidget(order_group)
        
        layout.addLayout(top_layout)
        
        # 3. 보유 종목 영역
        holdings_group = self.create_holdings_group()
        layout.addWidget(holdings_group)
        
        self.tab_trading.setLayout(layout)

    def init_asset_tab(self):
        """자산관리 탭 초기화"""
        layout = QVBoxLayout()
        
        # 1. 실제 계좌 정보 (Kiwoom API 연동)
        account_group = QGroupBox("실제 계좌 현황")
        account_layout = QGridLayout()
        account_group.setStyleSheet("QGroupBox { font-weight: bold; color: #444; }")
        
        account_layout.addWidget(QLabel("총 예수금:", styleSheet="font-size: 14px;"), 0, 0)
        self.lbl_total_deposit = QLabel("-", styleSheet="font-size: 16px; font-weight: bold;")
        account_layout.addWidget(self.lbl_total_deposit, 0, 1)
        
        account_layout.addWidget(QLabel("주문 가능 (D+2):", styleSheet="font-size: 14px; color: blue;"), 1, 0)
        self.lbl_available_deposit = QLabel("-", styleSheet="font-size: 16px; font-weight: bold; color: blue;")
        account_layout.addWidget(self.lbl_available_deposit, 1, 1)
        
        # 계좌 잔고 불러오기 버튼
        btn_load_account = QPushButton("내 계좌 잔고 조회")
        btn_load_account.setStyleSheet("background-color: #eee; height: 30px;")
        btn_load_account.clicked.connect(self.load_account_balance)
        account_layout.addWidget(btn_load_account, 0, 2, 2, 1)
        
        account_group.setLayout(account_layout)
        layout.addWidget(account_group)
        
        
        # 2. 봇 운용 자금 설정 (AssetManager)
        setting_group = QGroupBox("봇 운용 자금 관리")
        setting_layout = QVBoxLayout()
        setting_group.setStyleSheet("QGroupBox { font-weight: bold; color: #444; }")
        
        # [NEW] 현재 운용 설정액 표시 (크게)
        current_cap_layout = QHBoxLayout()
        current_cap_layout.addWidget(QLabel("🤖 현재 봇이 운용 중인 자금:", styleSheet="font-size: 14px;"))
        self.lbl_bot_capital_setting = QLabel("0원", styleSheet="font-size: 20px; font-weight: bold; color: #E04F5F;")
        current_cap_layout.addWidget(self.lbl_bot_capital_setting)
        current_cap_layout.addStretch()
        setting_layout.addLayout(current_cap_layout)
        
        # [NEW] 미운용 여유 자금 표시
        free_cap_layout = QHBoxLayout()
        free_cap_layout.addWidget(QLabel("💤 봇이 건드리지 않는 여유 자금:", styleSheet="font-size: 14px;"))
        self.lbl_free_capital = QLabel("-", styleSheet="font-size: 16px; font-weight: bold; color: green;")
        free_cap_layout.addWidget(self.lbl_free_capital)
        free_cap_layout.addStretch()
        setting_layout.addLayout(free_cap_layout)
        
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        setting_layout.addWidget(line)
        
        # 1. 입력 및 실행 (상단)
        manual_layout = QHBoxLayout()
        self.input_capital_change = QLineEdit()
        self.input_capital_change.setPlaceholderText("금액 입력 (원)")
        self.input_capital_change.textChanged.connect(self.format_money_input)
        self.input_capital_change.setAlignment(Qt.AlignRight) # 우측 정렬
        
        btn_manual_add = QPushButton("추가(+)")
        btn_manual_add.clicked.connect(self.add_capital)
        btn_manual_add.setStyleSheet("font-weight: bold; color: blue;")
        
        btn_manual_sub = QPushButton("축소(-)")
        btn_manual_sub.clicked.connect(self.withdraw_capital)
        btn_manual_sub.setStyleSheet("font-weight: bold; color: red;")
        
        manual_layout.addWidget(self.input_capital_change)
        manual_layout.addWidget(btn_manual_add)
        manual_layout.addWidget(btn_manual_sub)
        
        setting_layout.addLayout(manual_layout)

        # 2. 금액 조절 버튼 (하단)
        quick_btn_layout = QGridLayout()
        
        amounts = [100000, 500000, 1000000]
        # 단위 텍스트 맵핑
        unit_text = {100000: "10만", 500000: "50만", 1000000: "100만"}

        for i, amt in enumerate(amounts):
            u_text = unit_text.get(amt, f"{amt:,}")
            
            # 증가 버튼
            btn_inc = QPushButton(f"+{u_text}")
            btn_inc.clicked.connect(lambda checked, a=amt: self.update_input_value(a))
            quick_btn_layout.addWidget(btn_inc, 0, i)
            
            # 감소 버튼
            btn_dec = QPushButton(f"-{u_text}")
            btn_dec.clicked.connect(lambda checked, a=-amt: self.update_input_value(a))
            quick_btn_layout.addWidget(btn_dec, 1, i)

        setting_layout.addLayout(quick_btn_layout)

        
        # 종목당 한도 설정
        limit_layout = QHBoxLayout()
        self.input_max_stock = QLineEdit()
        self.input_max_stock.setPlaceholderText("0 = 무제한 (기본값)")
        self.input_max_stock.textChanged.connect(self.format_money_input)
        
        current_max = self.asset_manager.get_max_stock_amount()
        self.input_max_stock.setText(str(current_max))
        
        btn_set_max = QPushButton("한도 적용")
        btn_set_max.clicked.connect(self.set_max_stock_amount)
        
        limit_layout.addWidget(QLabel("종목당 매수 한도:"))
        limit_layout.addWidget(self.input_max_stock)
        limit_layout.addWidget(QLabel("(0=무제한)", styleSheet="color: gray; font-size: 11px;"))
        limit_layout.addWidget(btn_set_max)

        
        setting_layout.addLayout(limit_layout)
        setting_group.setLayout(setting_layout)
        layout.addWidget(setting_group)
        
        # 3. 자산 운용 현황 (통계)
        status_group = QGroupBox("자산 운용 현황")
        status_layout = QGridLayout()
        status_group.setStyleSheet("QGroupBox { font-weight: bold; color: #444; }")
        
        idx_style = "font-size: 14px; color: gray;"
        val_style = "font-size: 18px; font-weight: bold;"
        
        status_layout.addWidget(QLabel("현재 운용 자산", styleSheet=idx_style), 0, 0)
        self.dash_current_capital = QLabel("-", styleSheet=val_style)
        status_layout.addWidget(self.dash_current_capital, 1, 0)
        
        status_layout.addWidget(QLabel("매수 가능 현금", styleSheet=idx_style), 0, 1)
        self.dash_available_cash = QLabel("-", styleSheet="font-size: 18px; font-weight: bold; color: blue;")
        status_layout.addWidget(self.dash_available_cash, 1, 1)
        
        status_layout.addWidget(QLabel("누적 수익금", styleSheet=idx_style), 2, 0)
        self.dash_profit = QLabel("-", styleSheet=val_style)
        status_layout.addWidget(self.dash_profit, 3, 0)
        
        status_layout.addWidget(QLabel("총 수익률", styleSheet=idx_style), 2, 1)
        self.dash_profit_rate = QLabel("-", styleSheet=val_style)
        status_layout.addWidget(self.dash_profit_rate, 3, 1)
        
        btn_refresh_asset = QPushButton("현황 새로고침")
        btn_refresh_asset.clicked.connect(self.refresh_asset_status)
        status_layout.addWidget(btn_refresh_asset, 4, 0, 1, 2)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        layout.addStretch()
        self.tab_asset.setLayout(layout)



    def init_history_tab(self):
        """거래내역 탭 초기화"""
        layout = QVBoxLayout()
        
        # 1. 조회 옵션
        option_group = QGroupBox("조회 옵션")
        option_layout = QHBoxLayout()
        
        btn_refresh_history = QPushButton("내역 새로고침")
        btn_refresh_history.clicked.connect(self.refresh_history)
        option_layout.addWidget(btn_refresh_history)
        option_layout.addStretch()
        
        option_group.setLayout(option_layout)
        layout.addWidget(option_group)
        
        # 2. 일일 수익률 요약
        summary_group = QGroupBox("일일 수익 리포트")
        summary_layout = QVBoxLayout()
        
        self.table_summary = QTableWidget()
        self.table_summary.setColumnCount(6)
        self.table_summary.setHorizontalHeaderLabels([
            "날짜", "기초자산", "기말자산", "수익금", "수익률(%)", "거래수"
        ])
        header = self.table_summary.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        
        summary_layout.addWidget(self.table_summary)
        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)
        
        # 3. 상세 매매 기록
        log_group = QGroupBox("상세 매매 기록")
        log_layout = QVBoxLayout()
        
        self.table_trade_log = QTableWidget()
        self.table_trade_log.setColumnCount(7)  # 날짜, 시간 분리 고려하거나 포맷팅
        self.table_trade_log.setHorizontalHeaderLabels([
            "일시", "종목명", "구분", "단가", "수량", "총액", "주문번호"
        ])
        header = self.table_trade_log.horizontalHeader()
        
        # 컬럼 너비 조절
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents) # 일시
        header.setSectionResizeMode(1, QHeaderView.Stretch)          # 종목명
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents) # 구분
        
        log_layout.addWidget(self.table_trade_log)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        
        self.tab_history.setLayout(layout)

    @pyqtSlot(str)
    def format_money_input(self, text):
        """금액 입력 시 3자리마다 콤마 추가"""
        widget = self.sender()
        if not widget or not isinstance(widget, QLineEdit):
            return
            
        if not text:
            return
            
        # 커서 위치 저장
        cursor_pos = widget.cursorPosition()
        
        # 콤마 제거 및 숫자 변환
        clean_text = text.replace(',', '')
        if not clean_text:
            return
            
        if not clean_text.isdigit():
            # 숫자가 아닌 문자 입력 시 제거
            widget.blockSignals(True)
            widget.setText(clean_text[:-1]) # 마지막 문자 제거 시도 (단순화)
            # 재귀 호출 방지를 위해 로직 단순화가 필요하나, 여기서는 포맷팅 로직 위주로 처리
            # 더 안전한 방법: 이전 텍스트 복원이지만 복잡함.
            # 단순히 int 변환 가능한 부분까지만 살리기
            valid_chars = [c for c in clean_text if c.isdigit()]
            clean_text = "".join(valid_chars)
            
        # 포맷팅
        try:
            val = int(clean_text)
            formatted_text = f"{val:,}"
        except ValueError:
            formatted_text = ""
        
        # 텍스트 변경
        if text != formatted_text:
            widget.blockSignals(True)
            widget.setText(formatted_text)
            widget.blockSignals(False)
            
            # 커서 위치 조정 (단순히 끝으로 이동 - 사용성 타협)
            # 정확한 커서 복원은 복잡하므로 끝으로 이동
            widget.setCursorPosition(len(formatted_text))


    # ========== 자산 관리 메서드 ==========

    def processing_capital_change(self, amount):
        """버튼을 통한 자금 변경 처리"""
        if amount > 0:
            self.asset_manager.add_capital(amount)
            self.log(f"💰 운용 자금 추가: +{amount:,}원")
        elif amount < 0:
            abs_amount = abs(amount)
            # 현금 부족 체크
            if self.asset_manager.get_available_cash() < abs_amount:
                QMessageBox.warning(self, "잔액 부족", "출금 가능한 봇 운용 현금이 부족합니다.")
                return

            self.asset_manager.withdraw_capital(abs_amount)
            self.log(f"💸 운용 자금 축소: -{abs_amount:,}원")
            
        self.refresh_asset_status()

    def update_input_value(self, delta):
        """입력 필드의 값을 변경"""
        current_text = self.input_capital_change.text().replace(',', '')
        if not current_text:
            current_val = 0
        else:
            try:
                current_val = int(current_text)
            except ValueError:
                current_val = 0
        
        new_val = current_val + delta
        if new_val < 0: new_val = 0
        
        self.input_capital_change.setText(f"{new_val:,}")

    @pyqtSlot()
    def load_account_balance(self):
        """계좌 잔고 조회 (실제 계좌 현황 업데이트)"""
        if self.kiwoom is None or self.kiwoom.get_connect_state() != 1:
            QMessageBox.warning(self, "경고", "먼저 로그인해주세요.")
            return
            
        try:
            account_no = self.label_account.text()
            if not account_no or account_no == "-":
                QMessageBox.warning(self, "경고", "계좌 번호를 가져올 수 없습니다.")
                return

            self.log(f"계좌 잔고 조회 중... ({account_no})")
            balance_data = self.kiwoom.get_account_balance(account_no)
            
            # 데이터 파싱 (빈 문자열 처리 추가)
            raw_deposit = balance_data.get('예수금', '0').strip().replace(',', '')
            raw_d2 = balance_data.get('d+2추정예수금', '0').strip().replace(',', '')
            
            deposit = int(raw_deposit) if raw_deposit else 0
            d2_deposit = int(raw_d2) if raw_d2 else 0
            
            # 멤버 변수에 저장 (계산용)
            self.current_d2_deposit = d2_deposit
            
            # UI 업데이트
            self.lbl_total_deposit.setText(f"{deposit:,}원")
            self.lbl_available_deposit.setText(f"{d2_deposit:,}원")
            
            # 자산 현황 갱신 (여유 자금 계산을 위해)
            self.refresh_asset_status()
            
            self.log(f"💰 계좌 잔고 조회 완료: 총예수금 {deposit:,}원, 주문가능 {d2_deposit:,}원")
            QMessageBox.information(self, "알림", "계좌 잔고 조회가 완료되었습니다.")

            
        except Exception as e:
            self.log(f"❌ 잔고 조회 실패: {e}")

    @pyqtSlot()
    def set_initial_capital(self):
        """운용 자금 초기화"""
        try:
            amount = int(self.input_capital_change.text().replace(',', ''))
            
            # [안전장치] 예수금 초과 방지
            if hasattr(self, 'current_d2_deposit') and self.current_d2_deposit > 0:
                if amount > self.current_d2_deposit:
                    QMessageBox.critical(self, "자금 설정 오류", f"설정 금액({amount:,}원)이 주문 가능 금액({self.current_d2_deposit:,}원)을 초과합니다.")
                    return
            else:
                 QMessageBox.warning(self, "경고", "안전한 운용을 위해 먼저 [내 계좌 잔고 조회]를 실행해주세요.")
                 return

            self.asset_manager.set_initial_capital(amount)
            self.log(f"✅ 운용 자금 설정: {amount:,}원")
            QMessageBox.information(self, "성공", f"운용 자금이 {amount:,}원으로 설정되었습니다.")
            self.refresh_asset_status()
            self.input_capital_change.clear()
        except ValueError:
            QMessageBox.warning(self, "오류", "숫자만 입력해주세요.")

    @pyqtSlot()
    def add_capital(self):
        """운용 자금 추가"""
        try:
            amount = int(self.input_capital_change.text().replace(',', ''))
            
            # [안전장치] 예수금 초과 방지
            if hasattr(self, 'current_d2_deposit') and self.current_d2_deposit > 0:
                current_total = self.asset_manager.get_total_capital()
                if current_total + amount > self.current_d2_deposit:
                    QMessageBox.critical(self, "한도 초과", f"운용 자금이 실제 예수금({self.current_d2_deposit:,}원)을 초과할 수 없습니다.")
                    return
            else:
                 QMessageBox.warning(self, "경고", "안전한 운용을 위해 먼저 [내 계좌 잔고 조회]를 실행해주세요.")
                 return
                 
            # 확인 절차
            reply = QMessageBox.question(self, "추가 확인", f"현재 입력된 {amount:,}원을 운용 자금에 '추가' 하시겠습니까?", 
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
                 
            self.asset_manager.add_capital(amount)
            self.log(f"✅ 운용 자금 추가: +{amount:,}원")
            # QMessageBox.information(self, "성공", f"{amount:,}원이 추가되었습니다.")
            self.refresh_asset_status()
            self.input_capital_change.clear()
        except ValueError:
            QMessageBox.warning(self, "오류", "숫자만 입력해주세요.")

    @pyqtSlot()
    def withdraw_capital(self):
        """운용 자금 축소"""
        try:
            amount = int(self.input_capital_change.text().replace(',', ''))
            
            # 확인 절차
            reply = QMessageBox.question(self, "축소 확인", f"현재 입력된 {amount:,}원을 운용 자금에서 '축소(반환)' 하시겠습니까?", 
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
                
            self.asset_manager.withdraw_capital(amount)
            self.log(f"✅ 운용 자금 축소: -{amount:,}원")
            # QMessageBox.information(self, "성공", f"{amount:,}원이 축소되었습니다.")
            self.refresh_asset_status()
            self.input_capital_change.clear()
        except Exception as e:
            QMessageBox.warning(self, "오류", str(e))


    @pyqtSlot()
    def set_max_stock_amount(self):
        """종목당 매수 한도 설정"""
        try:
            amount = int(self.input_max_stock.text().replace(',', ''))
            self.asset_manager.set_max_stock_amount(amount)
            self.log(f"✅ 종목당 매수 한도 설정: {amount:,}원")
            self.log(f"✅ 종목당 매수 한도 설정: {amount:,}원")
            QMessageBox.information(self, "성공", "매수 한도가 적용되었습니다.")
            self.refresh_asset_status()
            self.input_max_stock.clear()
        except ValueError:
             QMessageBox.warning(self, "오류", "숫자만 입력해주세요.")

    def create_strategy_info_group(self):
        """현재 적용된 전략 정보 표시 그룹 생성"""
        group = QGroupBox("현재 적용 전략")
        group.setStyleSheet("QGroupBox { border: 2px solid #007AFF; font-weight: bold; margin-top: 10px; } QGroupBox::title { color: #007AFF; }")
        layout = QHBoxLayout()
        
        # 전략명
        self.lbl_strategy_name = QLabel("변동성 돌파 전략")
        self.lbl_strategy_name.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        # 파라미터 표시
        self.lbl_strategy_params = QLabel("K: - | 손절: -% | 익절: -%")
        self.lbl_strategy_params.setStyleSheet("color: #333; font-size: 13px;")
        
        layout.addWidget(QLabel("전략:"))
        layout.addWidget(self.lbl_strategy_name)
        layout.addSpacing(20)
        layout.addWidget(QLabel("설정:"))
        layout.addWidget(self.lbl_strategy_params)
        layout.addStretch()
        
        group.setLayout(layout)
        return group

    def refresh_strategy_info(self):
        """전략 정보 UI 갱신"""
        params = self.strategy.params
        k = params.get('k', 0.5)
        stop = params.get('stop_loss', -2.0)
        take = params.get('take_profit', 5.0)
        
        self.lbl_strategy_params.setText(f"K: {k} | 손절: {stop}% | 익절: {take}%")
        self.log(f"ℹ️ 전략 정보 갱신: K={k}, 손절={stop}%, 익절={take}%")

    @pyqtSlot()
    def refresh_asset_status(self):
        """자산 현황 새로고침"""
        summary = self.asset_manager.get_summary()
        
        current_capital = summary['현재_운용금액']
        
        # 상단 설정액 표시 업데이트
        self.lbl_bot_capital_setting.setText(f"{summary['초기_설정액']:,}원")
        
        # 미운용 자금 계산 (계좌 정보가 있을 때만)
        if hasattr(self, 'current_d2_deposit'):
            free_money = self.current_d2_deposit - current_capital
            self.lbl_free_capital.setText(f"{free_money:,}원")
            if free_money < 0:
                self.lbl_free_capital.setStyleSheet("font-size: 16px; font-weight: bold; color: red;")
            else:
                self.lbl_free_capital.setStyleSheet("font-size: 16px; font-weight: bold; color: green;")
        
        self.dash_current_capital.setText(f"{current_capital:,}원")

        self.dash_available_cash.setText(f"{summary['가용_현금']:,}원")
        self.dash_profit.setText(f"{summary['누적_수익금']:,}원")
        
        profit_rate = summary['수익률']
        self.dash_profit_rate.setText(f"{profit_rate:.2f}%")
        
        # 색상 적용
        if profit_rate > 0:
            self.dash_profit_rate.setStyleSheet("font-size: 18px; font-weight: bold; color: red;")
            self.dash_profit.setStyleSheet("font-size: 18px; font-weight: bold; color: red;")
        elif profit_rate < 0:
            self.dash_profit_rate.setStyleSheet("font-size: 18px; font-weight: bold; color: blue;")
            self.dash_profit.setStyleSheet("font-size: 18px; font-weight: bold; color: blue;")
        
        self.log("자산 현황 업데이트 완료")

    # ========== 거래 내역 메서드 ==========

    @pyqtSlot()
    def refresh_history(self):
        """거래 내역 및 리포트 조회"""
        try:
            # 1. 일일 요약 조회
            summaries = self.db.get_summary_history()
            self.table_summary.setRowCount(0)
            
            for i, item in enumerate(summaries):
                self.table_summary.insertRow(i)
                self.table_summary.setItem(i, 0, QTableWidgetItem(item.get('date', '-')))
                self.table_summary.setItem(i, 1, QTableWidgetItem(f"{item.get('initial_capital', 0):,}"))
                self.table_summary.setItem(i, 2, QTableWidgetItem(f"{item.get('final_capital', 0):,}"))
                self.table_summary.setItem(i, 3, QTableWidgetItem(f"{item.get('profit', 0):,}"))
                self.table_summary.setItem(i, 4, QTableWidgetItem(f"{item.get('profit_rate', 0):.2f}%"))
                self.table_summary.setItem(i, 5, QTableWidgetItem(str(item.get('trade_count', 0))))
            
            # 2. 상세 매매 기록 조회
            trades = self.db.get_trade_history()
            self.table_trade_log.setRowCount(0)
            
            for i, item in enumerate(trades):
                self.table_trade_log.insertRow(i)
                self.table_trade_log.setItem(i, 0, QTableWidgetItem(item.get('timestamp', '-')))
                self.table_trade_log.setItem(i, 1, QTableWidgetItem(item.get('stock_name', '-')))
                
                trade_type = item.get('trade_type', '-')
                type_item = QTableWidgetItem(trade_type)
                if trade_type == "매수":
                    type_item.setForeground(Qt.red)
                elif trade_type == "매도":
                    type_item.setForeground(Qt.blue)
                self.table_trade_log.setItem(i, 2, type_item)
                
                self.table_trade_log.setItem(i, 3, QTableWidgetItem(f"{item.get('price', 0):,}"))
                self.table_trade_log.setItem(i, 4, QTableWidgetItem(f"{item.get('quantity', 0):,}"))
                self.table_trade_log.setItem(i, 5, QTableWidgetItem(f"{item.get('total_amount', 0):,}"))
                self.table_trade_log.setItem(i, 6, QTableWidgetItem(item.get('order_number', '-')))
            
            self.log("거래 내역 조회 완료")
            
        except Exception as e:
            self.log(f"❌ 내역 조회 실패: {e}")

    def create_user_info_group(self):
        """사용자 접속 정보 및 로그아웃 영역 생성"""
        group = QGroupBox("접속 정보")
        layout = QHBoxLayout()
        
        # 접속 상태
        layout.addWidget(QLabel("접속 상태:"))
        self.label_connect_status = QLabel("미접속")
        self.label_connect_status.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.label_connect_status)
        
        # 계좌번호
        layout.addWidget(QLabel("계좌번호:"))
        self.label_account = QLabel("-")
        layout.addWidget(self.label_account)
        
        # 사용자 ID
        layout.addWidget(QLabel("사용자 ID:"))
        self.label_user_id = QLabel("-")
        layout.addWidget(self.label_user_id)
        
        layout.addStretch()
        
        # 로그아웃 버튼
        btn_logout = QPushButton("로그아웃")
        btn_logout.setStyleSheet("background-color: #ff4444; color: white; font-weight: bold;")
        btn_logout.clicked.connect(self.logout)
        layout.addWidget(btn_logout)
        
        group.setLayout(layout)
        return group

    def create_stock_info_group(self):
        """종목 조회 영역 생성"""
        group = QGroupBox("종목 조회")
        layout = QGridLayout()
        
        # 종목코드 입력
        layout.addWidget(QLabel("종목코드:"), 0, 0)
        self.input_stock_code = QLineEdit()
        self.input_stock_code.setPlaceholderText("예: 005930")
        layout.addWidget(self.input_stock_code, 0, 1)
        
        # 조회 버튼
        self.btn_search = QPushButton("조회")
        self.btn_search.clicked.connect(self.search_stock)
        layout.addWidget(self.btn_search, 0, 2)
        
        # 종목명
        layout.addWidget(QLabel("종목명:"), 1, 0)
        self.label_stock_name = QLabel("-")
        self.label_stock_name.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.label_stock_name, 1, 1, 1, 2)
        
        # 현재가
        layout.addWidget(QLabel("현재가:"), 2, 0)
        self.label_current_price = QLabel("-")
        self.label_current_price.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self.label_current_price, 2, 1, 1, 2)
        
        # 등락율
        layout.addWidget(QLabel("등락율:"), 3, 0)
        self.label_change_rate = QLabel("-")
        layout.addWidget(self.label_change_rate, 3, 1, 1, 2)
        
        # 거래량
        layout.addWidget(QLabel("거래량:"), 4, 0)
        self.label_volume = QLabel("-")
        layout.addWidget(self.label_volume, 4, 1, 1, 2)
        
        # 시가/고가/저가
        layout.addWidget(QLabel("시가:"), 5, 0)
        self.label_open = QLabel("-")
        layout.addWidget(self.label_open, 5, 1, 1, 2)
        
        layout.addWidget(QLabel("고가:"), 6, 0)
        self.label_high = QLabel("-")
        layout.addWidget(self.label_high, 6, 1, 1, 2)
        
        layout.addWidget(QLabel("저가:"), 7, 0)
        self.label_low = QLabel("-")
        layout.addWidget(self.label_low, 7, 1, 1, 2)
        
        group.setLayout(layout)
        return group
    
    def create_order_group(self):
        """주문 입력 영역 생성"""
        group = QGroupBox("주문 입력")
        layout = QGridLayout()
        
        # 종목코드
        layout.addWidget(QLabel("종목코드:"), 0, 0)
        self.input_order_code = QLineEdit()
        self.input_order_code.setPlaceholderText("예: 005930")
        layout.addWidget(self.input_order_code, 0, 1)
        
        # 주문수량
        layout.addWidget(QLabel("수량:"), 1, 0)
        self.input_order_qty = QLineEdit()
        self.input_order_qty.setPlaceholderText("예: 10")
        layout.addWidget(self.input_order_qty, 1, 1)
        
        # 주문가격
        layout.addWidget(QLabel("가격:"), 2, 0)
        self.input_order_price = QLineEdit()
        self.input_order_price.setPlaceholderText("0 = 시장가")
        layout.addWidget(self.input_order_price, 2, 1)
        
        # 매수 버튼
        self.btn_buy = QPushButton("매수")
        self.btn_buy.clicked.connect(self.buy_stock)
        self.btn_buy.setStyleSheet("background-color: #ff4444; color: white; font-weight: bold; padding: 10px;")
        layout.addWidget(self.btn_buy, 3, 0)
        
        # 매도 버튼
        self.btn_sell = QPushButton("매도")
        self.btn_sell.clicked.connect(self.sell_stock)
        self.btn_sell.setStyleSheet("background-color: #4444ff; color: white; font-weight: bold; padding: 10px;")
        layout.addWidget(self.btn_sell, 3, 1)
        
        # 빈 공간 추가
        layout.setRowStretch(4, 1)
        
        group.setLayout(layout)
        return group
    
    def create_holdings_group(self):
        """보유 종목 영역 생성"""
        group = QGroupBox("보유 종목")
        layout = QVBoxLayout()
        
        # 새로고침 버튼
        btn_refresh = QPushButton("새로고침")
        btn_refresh.clicked.connect(self.refresh_holdings)
        layout.addWidget(btn_refresh)
        
        # 테이블
        self.table_holdings = QTableWidget()
        self.table_holdings.setColumnCount(7)
        self.table_holdings.setHorizontalHeaderLabels([
            "종목코드", "종목명", "보유수량", "매입가", "현재가", "평가손익", "수익률(%)"
        ])
        
        # 테이블 헤더 설정
        header = self.table_holdings.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        
        layout.addWidget(self.table_holdings)
        group.setLayout(layout)
        return group
    
    def create_log_group(self):
        """로그 영역 생성"""
        group = QGroupBox("로그")
        layout = QVBoxLayout()
        
        self.text_log = QTextEdit()
        self.text_log.setReadOnly(True)
        self.text_log.setStyleSheet("background-color: #f0f0f0;")
        
        layout.addWidget(self.text_log)
        group.setLayout(layout)
        return group
    
    # ========== 이벤트 핸들러 ==========
    
    @pyqtSlot()
    def login(self):
        """로그인"""
        try:
            self.log("로그인을 시작합니다...")
            
            # 키움 API 객체 생성
            if self.kiwoom is None:
                self.kiwoom = Kiwoom()
                # 전략에 키움 객체 연결
                self.strategy.kiwoom = self.kiwoom
                
            # 시그널 연결 (중복 방지를 위해 안전하게 처리)
            try:
                self.kiwoom.sig_scan_result.disconnect()
                self.kiwoom.sig_condition_load.disconnect()
                self.kiwoom.sig_condition_result.disconnect()
                self.kiwoom.sig_real_condition.disconnect()
            except: pass

            self.kiwoom.sig_scan_result.connect(self.on_scan_result)
            self.kiwoom.sig_condition_load.connect(self.update_condition_combo)
            self.kiwoom.sig_condition_result.connect(self.on_condition_result)
            self.kiwoom.sig_real_condition.connect(self.on_real_condition)
            
            # 로그인
            self.kiwoom.login()
            
            # 접속 상태 확인
            if self.kiwoom.get_connect_state() == 1:
                self.label_connect_status.setText("접속됨")
                self.label_connect_status.setStyleSheet("color: green; font-weight: bold;")
                
                # 계좌 정보 표시
                account_list = self.kiwoom.get_login_info("ACCNO")
                self.label_account.setText(account_list.split(';')[0])
                
                user_id = self.kiwoom.get_login_info("USER_ID")
                self.label_user_id.setText(user_id)
                
                # 사용자별 자산 및 전략 설정 로드
                user_id_str = user_id.strip()
                self.asset_manager.load_user_config(user_id_str)
                self.strategy.load_config(user_id_str)  # 전략 설정 로드
                
                self.log(f"📂 사용자 설정 로드 완료: {user_id}")
                
                self.log("✅ 로그인 성공!")
                # 메인 화면으로 전환
                self.stack.setCurrentIndex(1)
                
                # 예수금 및 보유종목 조회
                self.refresh_holdings()
                self.refresh_asset_status()
                
                # 저장된 Max Stock Amount UI 반영
                max_stock = self.asset_manager.get_max_stock_amount()
                if max_stock >= 0:
                    self.input_max_stock.setText(f"{max_stock:,}")
                    
                    
                # [NEW] 전략 설정 UI 반영
                self.refresh_settings_ui()
                self.refresh_strategy_info()  # 메인 화면 전략 정보도 갱신

            else:
                self.log("❌ 로그인 실패")
                QMessageBox.warning(self, "로그인 실패", "로그인에 실패했습니다. 다시 시도해주세요.")
                
        except Exception as e:
            self.log(f"❌ 로그인 오류: {str(e)}")
            QMessageBox.critical(self, "오류", f"로그인 중 오류가 발생했습니다:\n{str(e)}")

    @pyqtSlot()
    def logout(self):
        """로그아웃"""
        confirm = QMessageBox.question(self, "로그아웃", "로그아웃 하시겠습니까?", 
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if confirm == QMessageBox.Yes:
            # 설정 초기화 등 필요한 작업 수행
            # self.kiwoom = None # 주의: OCX 객체를 해제하면 재로그인 시 크래시 발생 가능. 객체 재사용.
            
            # UI 초기화
            self.label_connect_status.setText("미접속")
            self.label_connect_status.setStyleSheet("color: red;")
            self.label_account.setText("-")
            self.label_user_id.setText("-")
            
            # 메인 화면 -> 로그인 화면 전환
            self.stack.setCurrentIndex(0)
            self.log("🔒 로그아웃되었습니다.")
    
    @pyqtSlot()
    def search_stock(self):
        """종목 조회"""
        if self.kiwoom is None or self.kiwoom.get_connect_state() != 1:
            QMessageBox.warning(self, "경고", "먼저 로그인해주세요.")
            return
        
        stock_code = self.input_stock_code.text().strip()
        if not stock_code:
            QMessageBox.warning(self, "경고", "종목코드를 입력해주세요.")
            return
        
        try:
            self.log(f"종목 조회 중: {stock_code}")
            
            # 현재가 조회
            data = self.kiwoom.get_current_price(stock_code)
            
            # 결과 표시
            self.label_stock_name.setText(data.get('종목명', 'N/A'))
            
            # 현재가
            current_price = data.get('현재가', '0')
            price_value = abs(int(current_price)) if current_price else 0
            self.label_current_price.setText(f"{price_value:,}원")
            
            # 등락율
            change_rate = data.get('등락율', '0')
            self.label_change_rate.setText(f"{change_rate}%")
            if float(change_rate) > 0:
                self.label_change_rate.setStyleSheet("color: red; font-weight: bold;")
            elif float(change_rate) < 0:
                self.label_change_rate.setStyleSheet("color: blue; font-weight: bold;")
            else:
                self.label_change_rate.setStyleSheet("color: black;")
            
            # 거래량
            volume = data.get('거래량', '0')
            volume_value = int(volume) if volume else 0
            self.label_volume.setText(f"{volume_value:,}")
            
            # 시가/고가/저가
            open_price = abs(int(data.get('시가', '0') or '0'))
            high_price = abs(int(data.get('고가', '0') or '0'))
            low_price = abs(int(data.get('저가', '0') or '0'))
            
            self.label_open.setText(f"{open_price:,}원")
            self.label_high.setText(f"{high_price:,}원")
            self.label_low.setText(f"{low_price:,}원")
            
            self.log(f"✅ 조회 완료: {data.get('종목명', 'N/A')} - {price_value:,}원")
            
        except Exception as e:
            self.log(f"❌ 조회 오류: {str(e)}")
            QMessageBox.critical(self, "오류", f"종목 조회 중 오류가 발생했습니다:\n{str(e)}")
    
    @pyqtSlot()
    def refresh_holdings(self):
        """보유 종목 새로고침"""
        if self.kiwoom is None or self.kiwoom.get_connect_state() != 1:
            QMessageBox.warning(self, "경고", "먼저 로그인해주세요.")
            return
        
        try:
            self.log("계좌 정보를 조회합니다...")
            account_no = self.label_account.text()
            
            # 1. 예수금 조회
            balance_data = self.kiwoom.get_account_balance(account_no)
            
            raw_deposit = balance_data.get('예수금', '0').strip().replace(',', '')
            raw_eval = balance_data.get('총평가금액', '0').strip().replace(',', '')
            
            deposit = int(raw_deposit) if raw_deposit else 0
            total_eval = int(raw_eval) if raw_eval else 0
            
            # UI 업데이트 (삭제됨)
            
            self.log(f"💰 예수금: {deposit:,}원 / 총 평가금액: {total_eval:,}원")
            
            # AssetManager 업데이트 (계좌 정보와 동기화)
            # 주의: 초기 자산 설정 이후에는 AssetManager가 독자적으로 관리해야 하므로
            # 여기서는 AssetManager의 현금을 강제로 업데이트하면 안 됩니다.
            # (봇 운용 자금 != 전체 예수금)
            # self.asset_manager.update_available_cash(deposit)  <-- 삭제
            
            # 2. 보유 종목 조회
            holdings = self.kiwoom.get_holdings(account_no)
            
            # 테이블 초기화
            self.table_holdings.setRowCount(0)
            
            for i, item in enumerate(holdings):
                self.table_holdings.insertRow(i)
                
                # 데이터 파싱
                code = item['종목코드'].strip()[1:]  # A005930 -> 005930
                name = item['종목명'].strip()
                qty = int(item['보유수량'])
                buy_price = int(item['매입가'])
                curr_price = int(item['현재가'])
                eval_profit = int(item['평가손익'])
                profit_rate = float(item['수익률'])
                
                # 테이블에 추가
                self.table_holdings.setItem(i, 0, QTableWidgetItem(code))
                self.table_holdings.setItem(i, 1, QTableWidgetItem(name))
                self.table_holdings.setItem(i, 2, QTableWidgetItem(f"{qty:,}"))
                self.table_holdings.setItem(i, 3, QTableWidgetItem(f"{buy_price:,}"))
                self.table_holdings.setItem(i, 4, QTableWidgetItem(f"{curr_price:,}"))
                
                # 손익 색상 처리
                item_profit = QTableWidgetItem(f"{eval_profit:,}")
                if eval_profit > 0:
                    item_profit.setForeground(Qt.red)
                elif eval_profit < 0:
                    item_profit.setForeground(Qt.blue)
                self.table_holdings.setItem(i, 5, item_profit)
                
                item_rate = QTableWidgetItem(f"{profit_rate:.2f}%")
                if profit_rate > 0:
                    item_rate.setForeground(Qt.red)
                elif profit_rate < 0:
                    item_rate.setForeground(Qt.blue)
                self.table_holdings.setItem(i, 6, item_rate)
            
            self.log(f"✅ 보유 종목 조회 완료 ({len(holdings)}개)")
            
        except Exception as e:
            self.log(f"❌ 계좌 조회 오류: {str(e)}")

    @pyqtSlot()
    def buy_stock(self):
        """매수 주문"""
        if self.kiwoom is None or self.kiwoom.get_connect_state() != 1:
            QMessageBox.warning(self, "경고", "먼저 로그인해주세요.")
            return
        
        stock_code = self.input_order_code.text().strip()
        qty = self.input_order_qty.text().strip()
        price = self.input_order_price.text().strip()
        
        if not stock_code or not qty:
            QMessageBox.warning(self, "경고", "종목코드와 수량을 입력해주세요.")
            return
            
        try:
            qty = int(qty)
            input_price = int(price) if price else 0  # 0이면 시장가
            account_no = self.label_account.text()
            
            self.log(f"매수 주문 요청: {stock_code} {qty}주")
            
            # 1. 주문 금액 계산
            # 시장가인 경우 현재가 조회 필요
            if input_price == 0:
                data = self.kiwoom.get_current_price(stock_code)
                current_price = int(data.get('현재가', '0').replace('+', '').replace('-', ''))
                order_price = current_price
                self.log(f"시장가 주문 (현재가: {current_price:,}원)")
            else:
                order_price = input_price
            
            total_amount = order_price * qty
            
            # 2. AssetManager 검증 (핵심 기능)
            can_buy, msg = self.asset_manager.can_buy(total_amount)
            if not can_buy:
                self.log(f"❌ 자산 검증 실패: {msg}")
                QMessageBox.warning(self, "주문 거부", f"자산 관리 원칙에 위배됩니다.\n{msg}")
                return
            
            # 3. 주문 실행
            result = self.kiwoom.send_order(1, stock_code, qty, input_price, account_no)
            
            # 4. 결과 처리
            if result == 0:
                self.log(f"✅ 매수 주문 전송 완료")
                
                # 자산 예약 (가용 현금 차감)
                self.asset_manager.reserve_cash(total_amount)
                
                # DB에 매매 기록 저장
                stock_name = self.kiwoom.data.get('종목명', '알수없음')
                self.db.save_trade(stock_code, stock_name, "매수", order_price, qty)
                
                QMessageBox.information(self, "성공", "매수 주문이 전송되었습니다.")
            else:
                self.log(f"❌ 매수 주문 실패 (에러코드: {result})")
                QMessageBox.warning(self, "실패", f"주문 전송에 실패했습니다.\n에러코드: {result}")
                
        except ValueError:
            QMessageBox.warning(self, "오류", "수량과 가격은 숫자여야 합니다.")

    @pyqtSlot()
    def sell_stock(self):
        """매도 주문"""
        if self.kiwoom is None or self.kiwoom.get_connect_state() != 1:
            QMessageBox.warning(self, "경고", "먼저 로그인해주세요.")
            return
        
        stock_code = self.input_order_code.text().strip()
        qty = self.input_order_qty.text().strip()
        price = self.input_order_price.text().strip()
        
        if not stock_code or not qty:
            QMessageBox.warning(self, "경고", "종목코드와 수량을 입력해주세요.")
            return
            
        try:
            qty = int(qty)
            price = int(price) if price else 0
            account_no = self.label_account.text()
            
            # 주문 실행
            result = self.kiwoom.send_order(2, stock_code, qty, price, account_no)
            
            if result == 0:
                self.log(f"📉 매도 주문 전송: {stock_code} {qty}주")
                QMessageBox.information(self, "성공", "매도 주문이 전송되었습니다.")
            else:
                self.log(f"❌ 매도 주문 실패 (에러코드: {result})")
                QMessageBox.warning(self, "실패", f"주문 전송에 실패했습니다.\n에러코드: {result}")
                
        except ValueError:
            QMessageBox.warning(self, "오류", "수량과 가격은 숫자여야 합니다.")
    
    def log(self, message):
        """로그 출력"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.text_log.append(f"[{timestamp}] {message}")

    def create_manual_watchlist_group(self):
        """수동 관리 종목 UI 생성"""
        group = QGroupBox("수동 관리 종목 (User Managed)")
        group.setStyleSheet("QGroupBox { border: 2px solid #555; font-weight: bold; }")
        layout = QVBoxLayout()
        
        # 입력 및 추가 버튼
        input_layout = QHBoxLayout()
        self.input_watch_code = QLineEdit()
        self.input_watch_code.setPlaceholderText("종목코드 입력 (예: 005930)")
        btn_add_watch = QPushButton("추가")
        btn_add_watch.clicked.connect(self.add_watch_stock)
        btn_del_watch = QPushButton("삭제")
        btn_del_watch.clicked.connect(self.remove_watch_stock)
        
        input_layout.addWidget(QLabel("종목코드:"))
        input_layout.addWidget(self.input_watch_code)
        input_layout.addWidget(btn_add_watch)
        input_layout.addWidget(btn_del_watch)
        layout.addLayout(input_layout)
        
        self.table_watchlist_manual = QTableWidget()
        self.table_watchlist_manual.setColumnCount(5)
        self.table_watchlist_manual.setHorizontalHeaderLabels(["코드", "종목명", "현재가", "목표가", "상태"])
        self.table_watchlist_manual.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table_watchlist_manual)
        
        group.setLayout(layout)
        return group

    def create_auto_watchlist_group(self):
        """자동 발굴 종목 UI 생성"""
        group = QGroupBox("실시간 전략 발굴 목록 (System Bot)")
        group.setStyleSheet("QGroupBox { border: 2px solid #007bff; font-weight: bold; } QGroupBox::title { color: #007bff; }")
        layout = QVBoxLayout()
        
        self.table_watchlist_auto = QTableWidget()
        self.table_watchlist_auto.setColumnCount(6) # 코드, 이름, 현재가, 전략명, 조건충족, 상태
        self.table_watchlist_auto.setHorizontalHeaderLabels(["코드", "종목명", "현재가", "발굴전략", "조건", "상태"])
        self.table_watchlist_auto.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table_watchlist_auto)
        
        group.setLayout(layout)
        return group

    def create_watchlist_group(self):
        """(하위 호환성 유지용)"""
        return QWidget()

    def init_setting_tab(self):
        """설정 탭 초기화"""
        layout = QVBoxLayout()
        
        # 1. 매매 전략 설정
        strategy_group = QGroupBox("매매 전략 설정")
        strategy_layout = QFormLayout()
        
        # 전략 선택
        self.combo_strategy = QComboBox()
        self.combo_strategy.addItem("변동성 돌파 전략")
        self.combo_strategy.addItem("이동평균선 크로스 (준비중)")
        
        # 설명 라벨
        self.lbl_strategy_desc = QLabel()
        self.lbl_strategy_desc.setStyleSheet("color: #333; font-size: 13px; margin-bottom: 10px; line-height: 150%;")
        self.lbl_strategy_desc.setWordWrap(True)
        self.combo_strategy.currentIndexChanged.connect(self.update_strategy_desc)
        
        # 파라미터 설정 (변동성 돌파 k)
        self.input_k_value = QLineEdit("0.5")
        self.input_k_value.setPlaceholderText("기본 0.5")
        
        strategy_layout.addRow("사용 전략:", self.combo_strategy)
        strategy_layout.addRow("", self.lbl_strategy_desc)
        strategy_layout.addRow("변동성 돌파 계수 (K):", self.input_k_value)
        strategy_layout.addRow("", QLabel("단위: 배 (권장 0.4 ~ 0.6)", styleSheet="color: gray; font-size: 11px;"))
        
        # 초기 설명 설정
        self.update_strategy_desc(0)
        
        strategy_group.setLayout(strategy_layout)
        layout.addWidget(strategy_group)
        
        # 2. 리스크 관리 설정
        risk_group = QGroupBox("리스크 관리")
        risk_layout = QFormLayout()
        
        # 손절
        self.input_stop_loss = QLineEdit("-2.0")
        self.input_stop_loss.setPlaceholderText("예: -2.0")
        desc_stop = QLabel("📉 설정된 손절율에 도달하면 자동으로 매도하여 추가 손실을 방지합니다.")
        desc_stop.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 5px;")
        
        # 익절
        self.input_take_profit = QLineEdit("5.0")
        self.input_take_profit.setPlaceholderText("예: 5.0")
        desc_take = QLabel("💰 설정된 익절율에 도달하면 수익을 확정하기 위해 자동으로 매도합니다.")
        desc_take.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 5px;")
        
        risk_layout.addRow("손절율 (%):", self.input_stop_loss)
        risk_layout.addRow("", desc_stop)
        risk_layout.addRow("익절율 (%):", self.input_take_profit)
        risk_layout.addRow("", desc_take)
        
        risk_group.setLayout(risk_layout)
        layout.addWidget(risk_group)
        
        # 2. 실시간 종목 스캔 설정
        discovery_group = QGroupBox("실시간 종목 스캔 기능 설정")
        discovery_layout = QVBoxLayout()
        form_layout = QFormLayout()
        
        # 자동 스캔 여부
        self.chk_auto_scan = QCheckBox("실시간 스마트 스캔 활성화")
        self.chk_auto_scan.setToolTip("활성화 시 60초마다 시장을 분석하여 유리한 종목을 자동 발굴합니다.")
        
        # 스캔 프로필
        self.combo_scan_profile = QComboBox()
        self.combo_scan_profile.addItems([
            "전고점 돌파 (Breakout)", 
            "정배열 & 골클 (Trend)", 
            "볼린저 밴드 돌파 (Vola)", 
            "사용자 정의"
        ])
        self.combo_scan_profile.currentIndexChanged.connect(self.update_scan_profile_desc)
        
        # 상세 필터 설정 (사용자 정의 시 활성화)
        self.input_min_vol_rate = QLineEdit("500")
        self.input_min_vol_rate.setToolTip("직전 5일 평균 거래량 대비 급증 비율")
        self.input_min_price_rate = QLineEdit("2.0")
        self.input_min_price_rate.setToolTip("당일 시가 대비 상승폭")
        
        form_layout.addRow(self.chk_auto_scan)
        form_layout.addRow("발굴 방식(프로필):", self.combo_scan_profile)
        form_layout.addRow("최소 거래량 급증 (%):", self.input_min_vol_rate)
        form_layout.addRow("최소 등락율 (%):", self.input_min_price_rate)
        
        # 프로필 상세 설명
        self.lbl_scan_desc = QLabel()
        self.lbl_scan_desc.setStyleSheet("color: #0056b3; background-color: #e7f3ff; padding: 10px; border-radius: 5px;")
        self.lbl_scan_desc.setWordWrap(True)
        
        discovery_layout.addLayout(form_layout)
        discovery_layout.addWidget(self.lbl_scan_desc)
        discovery_group.setLayout(discovery_layout)
        layout.addWidget(discovery_group)

        # 3. 설정 저장 버튼
        btn_save_settings = QPushButton("설정 저장 (Save Settings)")
        btn_save_settings.setStyleSheet("height: 45px; background-color: #007bff; color: white; font-weight: bold; font-size: 14px;")
        btn_save_settings.clicked.connect(self.save_settings)
        layout.addWidget(btn_save_settings)
        
        layout.addStretch()
        
        # 초기 설명 및 폼 상태 동기화
        self.update_strategy_desc(0)
        self.update_scan_profile_desc(0)
        
        # 버전 정보 표시
        version_label = QLabel(f"떡상기원 Ver {VERSION}")
        version_label.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        version_label.setStyleSheet("color: #999; font-size: 12px; margin: 10px;")
        layout.addWidget(version_label)
        
        self.tab_setting.setLayout(layout)

    def update_scan_profile_desc(self, index):
        """스캔 프로필 상세 설명 및 입력창 제어"""
        profile = self.combo_scan_profile.currentText()
        is_custom = (profile == "사용자 정의")
        
        self.input_min_vol_rate.setEnabled(True)
        self.input_min_price_rate.setEnabled(True)
        
        if "전고점 돌파" in profile:
            desc = (
                "🛠️ **[전고점 돌파 전략]**\n"
                "- **원리**: 강력한 저항선(20일 신고가)을 압도적 거래량으로 뚫는 순간을 포착\n"
                "- **기본값**: 거래량 500%↑ + 20일 신고가 경신 + 당일 등락 5%~15%\n"
                "- **포인트**: 가짜 돌파를 걸러내고 '진짜 상승'의 시작점에 올라탑니다."
            )
            # 설정값이 이미 입력되어 있지 않을 때만 기본값 세팅
            if not self.input_min_vol_rate.text(): self.input_min_vol_rate.setText("500")
            if not self.input_min_price_rate.text(): self.input_min_price_rate.setText("5")
        elif "정배열" in profile:
            desc = (
                "🛠️ **[정배열 & 골든크로스]**\n"
                "- **원리**: 5/20일 이평선 골든크로스 및 정배열(주가>5>20>60) 시작점 포착\n"
                "- **기본값**: 5/20 골크 + 정배열 완성 + 전일비 거래량 150%↑\n"
                "- **포인트**: 바닥권을 탈출하여 대시세 분출을 준비하는 안정적 추세 추종"
            )
            if not self.input_min_vol_rate.text(): self.input_min_vol_rate.setText("150") # 전일비 기준
            if not self.input_min_price_rate.text(): self.input_min_price_rate.setText("2")
        elif "볼린저" in profile:
            desc = (
                "🛠️ **[볼린저 밴드 돌파]**\n"
                "- **원리**: 변동성이 극도로 축축됐다가 상단선을 뚫으며 에너지를 분출할 때 포착\n"
                "- **기본값**: Bollinger Band(20,2) 상단 돌파 + 밴드 수축 후 확산\n"
                "- **포인트**: 짧은 시간 내에 강력한 시세 분출을 노리는 변동성 매매"
            )
            if not self.input_min_vol_rate.text(): self.input_min_vol_rate.setText("200")
            if not self.input_min_price_rate.text(): self.input_min_price_rate.setText("3")
        else:
            desc = "⚙️ **[사용자 정의]**\n필터 기준을 직접 입력하여 나만의 발굴 기법을 적용하세요."
            
        self.lbl_scan_desc.setText(desc)

    def update_strategy_desc(self, index):
        """전략 설명 업데이트"""
        if index == 0:
            desc = (
                "🚀 [변동성 돌파 전략]\n"
                "오늘 주가가 '어제 하루 동안의 변동폭(고가-저가)'의 일정 비율(K)만큼 올랐을 때,\n"
                "'상승세가 붙었다'고 판단하고 따라 사는 단기 급등주 공략 전략입니다.\n"
                "(K값이 작을수록 빨리 사고, 클수록 신중하게 삽니다)"
            )
        else:
            desc = (
                "📈 [이동평균선 크로스 전략 (준비중)]\n"
                "단기 평균 가격이 장기 평균 가격을 뚫고 올라가면(골든크로스) 매수하고,\n"
                "내려가면(데드크로스) 매도하는 정석적인 추세 매매법입니다."
            )
        self.lbl_strategy_desc.setText(desc)

    @pyqtSlot()
    def save_settings(self):
        """설정 저장"""
        try:
            # 1. 전략 설정
            k = float(self.input_k_value.text().strip())
            stop = float(self.input_stop_loss.text().strip())
            take = float(self.input_take_profit.text().strip())
            
            if k > 1.0:
                reply = QMessageBox.question(self, "확인", f"K값({k})이 1.0보다 큽니다. 계속하시겠습니까?", QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.No: return

            params = {
                'k': k, 
                'stop_loss': stop, 
                'take_profit': take,
                'min_vol': float(self.input_min_vol_rate.text().strip()),
                'min_price': float(self.input_min_price_rate.text().strip()),
                'auto_scan': self.chk_auto_scan.isChecked(),
                'profile': self.combo_scan_profile.currentText()
            }
            self.strategy.update_params(params)
            
            # 2. 스캔 타이머 제어
            if params['auto_scan']:
                self.log("🚀 스마트 스캔 활성화")
                if not self.scan_timer.isActive():
                    self.start_smart_scan()
            else:
                self.log("⏹ 스마트 스캔 중지")
                if self.scan_timer.isActive():
                    self.stop_smart_scan()

            QMessageBox.information(self, "저장 완료", "모든 설정이 성공적으로 저장되었습니다.")
            self.refresh_strategy_info()
            
        except ValueError:
            QMessageBox.warning(self, "오류", "유효한 숫자를 입력해주세요.")

    def refresh_settings_ui(self):
        """전략 설정을 UI에 반영 (로그인 후 호출)"""
        params = self.strategy.params
        
        # 기본 전략 파라미터
        if 'k' in params: self.input_k_value.setText(str(params['k']))
        if 'stop_loss' in params: self.input_stop_loss.setText(str(params['stop_loss']))
        if 'take_profit' in params: self.input_take_profit.setText(str(params['take_profit']))
        
        # 스캔 설정 파라미터
        if 'min_vol' in params: self.input_min_vol_rate.setText(str(params['min_vol']))
        if 'min_price' in params: self.input_min_price_rate.setText(str(params['min_price']))
        if 'auto_scan' in params: 
            self.chk_auto_scan.setChecked(params['auto_scan'])
            if params['auto_scan']: self.start_smart_scan()
        
        if 'profile' in params:
            index = self.combo_scan_profile.findText(params['profile'])
            if index >= 0:
                self.combo_scan_profile.setCurrentIndex(index)
                self.update_scan_profile_desc(index)

    @pyqtSlot()
    def toggle_trading(self):
        """자동매매 시작/중지 토글"""
        if self.btn_auto_start.isChecked():
            # 로그인 상태 확인
            if self.kiwoom is None or self.kiwoom.get_connect_state() != 1:
                QMessageBox.warning(self, "경고", "먼저 로그인을 해주세요.")
                self.btn_auto_start.setChecked(False)  # 버튼 상태 원복
                return

            # 시작
            self.is_trading_active = True
            self.btn_auto_start.setText("자동매매 중지")
            self.lbl_trading_status.setText("가동 중 (Trading On)")
            self.lbl_trading_status.setStyleSheet("color: blue; font-weight: bold; font-size: 14px;")
            self.log("🚀 자동매매를 시작합니다.")
        else:
            # 중지
            self.is_trading_active = False
            self.btn_auto_start.setText("자동매매 시작")
            self.lbl_trading_status.setText("중지됨 (Stopped)")
            self.lbl_trading_status.setStyleSheet("color: red; font-weight: bold; font-size: 14px;")
            self.log("⏹ 자동매매를 중지합니다.")

    @pyqtSlot()
    def update_market_status(self):
        """시장 상태(시간) 체크 및 라벨 업데이트"""
        current_time = QTime.currentTime()
        
        # 장 운영 시간 설정 (09:00 ~ 15:30)
        market_start = QTime(9, 0)
        market_end = QTime(15, 30)
        
        if current_time < market_start:
            status = "장 시작 전 (준비)"
            color = "orange"
        elif current_time > market_end:
            status = "장 마감"
            color = "gray"
        else:
            status = "장 중 (실시간)"
            color = "#4CAF50"  # Green
            
            # 자동매매가 켜져 있을 때만 실제 로직 수행 예정
            # 자동매매가 켜져 있을 때만 실제 로직 수행 예정
            if self.is_trading_active:
                self.run_strategy_cycle()

        self.lbl_market_status.setText(status)
        self.lbl_market_status.setStyleSheet(f"background-color: {color}; color: white; padding: 5px; border-radius: 3px; font-weight: bold;")
        
    def deprecated_method_cleanup(self):
        """삭제 예정 메서드 모음"""
        pass

    @pyqtSlot()
    def add_watch_stock(self):
        """수동 감시 종목 추가"""
        code = self.input_watch_code.text().strip()
        if not code:
            return
            
        if self.kiwoom is None or self.kiwoom.get_connect_state() != 1:
            QMessageBox.warning(self, "경고", "로그인이 필요합니다.")
            return

        self.log(f"🔍 {code} 종목 분석 및 사장님 픽 추가 중...")
        
        # 1. 전략 유니버스에 추가 (수동 태그)
        self.strategy.set_universe(self.strategy.universe + [code])
        
        # 2. UI 테이블에 추가
        row = self.table_watchlist_manual.rowCount()
        self.table_watchlist_manual.insertRow(row)
        self.table_watchlist_manual.setItem(row, 0, QTableWidgetItem(code))
        
        # 종목명 조회 (GetMasterCodeName)
        name = self.kiwoom.ocx.dynamicCall("GetMasterCodeName(QString)", code)
        self.table_watchlist_manual.setItem(row, 1, QTableWidgetItem(name))
        self.table_watchlist_manual.setItem(row, 2, QTableWidgetItem("조회중"))
        
        # 목표가 표시
        target = self.strategy.target_prices.get(code, 0)
        self.table_watchlist_manual.setItem(row, 3, QTableWidgetItem(f"{target:,}"))
        self.table_watchlist_manual.setItem(row, 4, QTableWidgetItem("감시중"))
        
        self.input_watch_code.clear()

    @pyqtSlot()
    def remove_watch_stock(self):
        """수동 선택 종목 삭제"""
        row = self.table_watchlist_manual.currentRow()
        if row < 0:
            return
            
        code_item = self.table_watchlist_manual.item(row, 0)
        if code_item:
            code = code_item.text()
            self.strategy.remove_stock(code)
            self.table_watchlist_manual.removeRow(row)
            self.log(f"🗑 {code} 감시 해제 (사장님 픽 삭제)")

    # ========== 조건검색 관련 메서드 (NEW) ==========

    # ========== 조건검색/스캔 관련 내부 로직 ==========

    @pyqtSlot()
    def load_condition_list(self):
        """조건식 목록 요청"""
        if self.kiwoom is None or self.kiwoom.get_connect_state() != 1:
            QMessageBox.warning(self, "경고", "로그인이 필요합니다.")
            return
        self.kiwoom.get_condition_load()

    @pyqtSlot(list)
    def update_condition_combo(self, conditions):
        """콤보박스에 조건식 목록 채우기"""
        self.combo_condition.clear()
        self.condition_list = conditions # Store list [(index, name), ...]
        for idx, name in conditions:
            self.combo_condition.addItem(f"{idx}^ {name}", idx)
        
        self.log(f"✅ 조건식 {len(conditions)}개 로드 완료")
        QMessageBox.information(self, "완료", f"조건식 {len(conditions)}개를 불러왔습니다.")

    @pyqtSlot()
    def start_condition_monitoring(self):
        """조건검색 감시 시작"""
        if self.combo_condition.currentIndex() < 0:
            QMessageBox.warning(self, "경고", "조건식을 선택해주세요.")
            return

        selected_idx = self.combo_condition.itemData(self.combo_condition.currentIndex())
        selected_text = self.combo_condition.currentText()
        if not selected_idx and selected_idx != 0: 
             return
             
        # Format: "index^ name" -> extract user friendly name
        cond_name = selected_text.split('^')[1].strip()
        screen_no = "1000" # 임의의 화면번호
        
        # 실시간 검색 요청 (1)
        self.kiwoom.send_condition(screen_no, cond_name, int(selected_idx), 1)
        
        self.log(f"⚡ 조건검색 감시 시작: {cond_name}")
        self.current_condition_idx = int(selected_idx)
        self.current_condition_name = cond_name
        self.current_screen_no = screen_no
        
        self.btn_start_cond.setEnabled(False)
        self.btn_stop_cond.setEnabled(True)
        self.combo_condition.setEnabled(False)

    @pyqtSlot()
    def stop_condition_monitoring(self):
        """조건검색 감시 중지"""
        if hasattr(self, 'current_condition_idx'):
            self.kiwoom.send_condition_stop(self.current_screen_no, self.current_condition_name, self.current_condition_idx)
            self.log(f"⏹ 조건검색 감시 중지: {self.current_condition_name}")
            
            self.btn_start_cond.setEnabled(True)
            self.btn_stop_cond.setEnabled(False)
            self.combo_condition.setEnabled(True)

    # ========== 스마트 스캔 관련 메서드 (NEW) ==========



    @pyqtSlot()
    def start_smart_scan(self):
        """스마트 스캔 시작"""
        if self.kiwoom is None or self.kiwoom.get_connect_state() != 1:
            return
            
        self.log("🚀 실시간 스마트 스캔을 시작합니다 (주기: 60초)")
        self.request_smart_scan() # 즉시 1회 실행
        self.scan_timer.start(60000) # 60초 간격

    @pyqtSlot()
    def stop_smart_scan(self):
        """스마트 스캔 중지"""
        self.scan_timer.stop()
        self.log("⏹ 스마트 스캔이 중지되었습니다.")

    def request_smart_scan(self):
        """Kiwoom API에 데이터 요청"""
        if self.kiwoom.get_connect_state() == 1:
            # 거래량 급증 및 가격 급등 동시 요청
            self.kiwoom.request_volume_surge()
            # 0.5초 대기 (API 조절)
            QTimer.singleShot(500, self.kiwoom.request_price_surge)

    @pyqtSlot(str, list)
    def on_condition_result(self, index, codes):
        """HTS 조건검색 결과 수신 -> 검증 큐로 전달"""
        self.log(f"🔎 [HTS포착] {len(codes)}개 종목 분석 대기열 추가")
        profile = self.combo_scan_profile.currentText()
        for code in codes:
            if code not in self.strategy.universe and code not in [c[0] for c in self.verification_queue]:
                name = self.kiwoom.ocx.dynamicCall("GetMasterCodeName(QString)", code)
                self.verification_queue.append((code, name, f"HTS 조건({profile})"))

    @pyqtSlot(str, str, str)
    def on_real_condition(self, code, type_str, index):
        """실시간 HTS 조건 편입/이탈 처리"""
        if type_str == "I": # 편입
            if code not in self.strategy.universe and code not in [c[0] for c in self.verification_queue]:
                name = self.kiwoom.ocx.dynamicCall("GetMasterCodeName(QString)", code)
                self.log(f"⚡ [HTS편입] {name}({code}) 검증 시작")
                profile = self.combo_scan_profile.currentText()
                self.verification_queue.append((code, name, f"실시간HTS({profile})"))

    def update_condition_combo(self, conditions):
        """HTS 조건식 목록 업데이트 (기존 유지)"""
        if hasattr(self, 'combo_conditions'): # 만약 UI에 살아있다면
             self.combo_conditions.clear()
             for cond in conditions:
                 self.combo_conditions.addItem(f"{cond['name']}", cond['index'])
    def on_scan_result(self, trcode, results):
        """스마트 스캔 결과 수신 및 초기 필터링"""
        try:
            profile = self.combo_scan_profile.currentText()
            # 1차 필터: 거래량 급증 기준 (프로필별 초기값)
            min_vol = float(self.input_min_vol_rate.text())
        except (ValueError, AttributeError):
            min_vol = 500.0

        for item in results:
            code = item['code']
            # 기초 필터링 (거래량/가격 기초 조건)
            if trcode == "opt10032" and item['volume_rate'] < min_vol: continue
            
            # 이미 감시 중이면 카운트 초기화 (TTL 연장)
            if code in self.auto_stock_hits:
                self.auto_stock_hits[code] = 0
                continue
                
            # 신규 후보라면 검증 큐에 추가
            if code not in self.strategy.universe and code not in [c[0] for c in self.verification_queue]:
                self.verification_queue.append((code, item['name'], profile))

    def process_verification_queue(self):
        """큐에서 종목을 꺼내 정밀 검증 (차트 분석)"""
        if not self.verification_queue or self.kiwoom.get_connect_state() != 1:
            return
            
        code, name, profile = self.verification_queue.pop(0)
        self.log(f"🔎 [검증대기] {name}({code}) 전략 적합성 분석 중...")
        
        # 1. 일봉 데이터 조회 (QEventLoop로 동기적 대기)
        daily_data = self.kiwoom.get_daily_data(code)
        if not daily_data: return
        
        # 2. 프로필별 정밀 검증
        passed = False
        if "전고점 돌파" in profile:
            is_break, target = self.strategy.check_breakout(daily_data, 20)
            if is_break: passed = True
        elif "정배열" in profile:
            if self.strategy.check_trend_alignment(daily_data) and self.strategy.check_golden_cross(daily_data):
                passed = True
        elif "볼린저" in profile:
            upper, avg, lower = self.strategy.calculate_bollinger_bands(daily_data)
            if upper and daily_data[0]['종가'] > upper:
                passed = True
        elif "사용자 정의" in profile:
            passed = True # 사용자 정의는 1차 필터만 통과하면 바로 추가
            
        # 3. 최종 통과 시 자동 리스트에 추가
        if passed:
            self.log(f"✨ [전략일치] {name}({code}) 포착! 자동 감시를 시작합니다.")
            self.add_watch_stock_auto(code, name, profile)
        else:
            # self.log(f"❌ [조건미달] {name}({code})")
            pass

    def add_watch_stock_auto(self, code, name, strategy_name):
        """자동 발굴 종목 편입 로직 (Dedicated Table)"""
        if code in self.strategy.universe:
            return
        
        # 전략에 추가
        self.strategy.add_stock(code)
        self.auto_stock_hits[code] = 0 # TTL 초기화
        
        # UI 테이블(AUTO)에 추가
        row = self.table_watchlist_auto.rowCount()
        self.table_watchlist_auto.insertRow(row)
        self.table_watchlist_auto.setItem(row, 0, QTableWidgetItem(code))
        self.table_watchlist_auto.setItem(row, 1, QTableWidgetItem(name))
        self.table_watchlist_auto.setItem(row, 2, QTableWidgetItem("조회중"))
        self.table_watchlist_auto.setItem(row, 3, QTableWidgetItem(strategy_name))
        self.table_watchlist_auto.setItem(row, 4, QTableWidgetItem("조건충족"))
        self.table_watchlist_auto.setItem(row, 5, QTableWidgetItem("감시중"))

    def run_strategy_cycle(self):
        """자동매매 주기적 실행 (수동/자동 리스트 모두 감시)"""
        # 1. 대상 종목 리스트 합치기 (중복 제거)
        manual_rows = self.table_watchlist_manual.rowCount()
        auto_rows = self.table_watchlist_auto.rowCount()
        total_rows = manual_rows + auto_rows
        
        if total_rows == 0:
            return

        # Polling: 1회당 1종목씩
        idx = self.polling_index % total_rows
        self.polling_index += 1
        
        if idx < manual_rows:
            target_table = self.table_watchlist_manual
            row_idx = idx
            price_col = 2
            status_col = 4
        else:
            target_table = self.table_watchlist_auto
            row_idx = idx - manual_rows
            price_col = 2
            status_col = 5
            
        code_item = target_table.item(row_idx, 0)
        if not code_item: return
        code = code_item.text()
        
        try:
            # 현재가 조회
            data = self.kiwoom.get_current_price(code)
            current_price = abs(int(data.get('현재가', '0').replace('+', '').replace('-', '') or 0))
            if current_price == 0: return

            target_table.setItem(row_idx, price_col, QTableWidgetItem(f"{current_price:,}"))
            
            # 매수 신호 확인
            status_item = target_table.item(row_idx, status_col)
            current_status = status_item.text() if status_item else ""
            
            if self.strategy.check_buy_signal(code, current_price):
                if "매수완료" not in current_status:
                    self.log(f"⚡ [매수신호] {code} - 현재가 {current_price:,}")
                    account = self.label_account.text()
                    qty = self.calculate_order_qty(current_price)
                    ret = self.kiwoom.send_order(1, code, qty, 0, account)
                    if ret == 0:
                        target_table.setItem(row_idx, status_col, QTableWidgetItem("매수완료"))
                        self.asset_manager.reserve_cash(current_price * qty)
        except Exception as e:
            self.log(f"⚠️ 사이클 매수대기 에러 ({code}): {e}")

        # 2. 보유 종목 순회 (매도 - 손절/익절)
        try:
            holdings = self.kiwoom.data.get('보유종목', [])
            for item in holdings:
                raw_code = item['종목코드']
                code = raw_code.strip()
                if len(code) > 6: code = code[-6:]
                
                current_price = abs(int(item['현재가']))
                buy_price = int(item['매입가'])
                qty = int(item['보유수량'])
                
                if qty <= 0: continue
                
                should_sell, msg = self.strategy.check_sell_signal(code, current_price, buy_price)
                if should_sell:
                    account = self.label_account.text()
                    self.log(f"📉 매도 신호 발생: {item['종목명']}({code}) - {msg}")
                    self.kiwoom.send_order(2, code, qty, 0, account)
        except Exception as e:
            pass

    def calculate_order_qty(self, price):
        """주문 수량 계산"""
        max_amount = self.asset_manager.get_max_stock_amount()
        if max_amount <= 0: return 1
        qty = max_amount // price
        return qty if qty > 0 else 1

    def cleanup_auto_watchlist(self):
        """자동 발굴된 종목 중 더 이상 조건에 안 맞는 종목 제거"""
        # 현재 보유 중인 종목 리스트 확인
        holding_codes = [item['종목코드'].strip() for item in self.kiwoom.data.get('보유종목', [])]
        for i in range(len(holding_codes)):
            if len(holding_codes[i]) > 6: holding_codes[i] = holding_codes[i][-6:]
        
        removed_count = 0
        # 역순으로 순회하며 제거
        for i in range(self.table_watchlist_auto.rowCount() - 1, -1, -1):
            code = self.table_watchlist_auto.item(i, 0).text()
            status = self.table_watchlist_auto.item(i, 5).text()
            
            # 1. 보유 중인 종목인 경우 자동 발굴 리스트에서 제거 (보유종목 테이블에서 관리하도록 유도)
            if code in holding_codes:
                self.strategy.remove_stock(code)
                self.table_watchlist_auto.removeRow(i)
                if code in self.auto_stock_hits: del self.auto_stock_hits[code]
                removed_count += 1
                continue
                
            # 2. 보유 중이 아니고 매수완료 상태가 아니면 TTL 상승
            if "매수완료" not in status:
                self.auto_stock_hits[code] = self.auto_stock_hits.get(code, 0) + 1
                if self.auto_stock_hits[code] >= 3:
                    self.log(f"🧹 [자동청소] 도태된 종목 제거: {code}")
                    self.strategy.remove_stock(code)
                    self.table_watchlist_auto.removeRow(i)
                    if code in self.auto_stock_hits: del self.auto_stock_hits[code]
                    removed_count += 1
        
        if removed_count > 0:
            self.log(f"🤖 총 {removed_count}개의 유효하지 않은 자동 발굴 종목을 정리했습니다.")
