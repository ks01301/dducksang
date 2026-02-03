"""
키움증권 자동매매 프로그램 메인 GUI
"""
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QTableWidget, 
    QTableWidgetItem, QGroupBox, QMessageBox, QHeaderView
)
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QFont
from kiwoom import Kiwoom


class MainWindow(QMainWindow):
    """메인 윈도우 클래스"""
    
    def __init__(self):
        super().__init__()
        
        # 키움 API 객체
        self.kiwoom = None
        
        # UI 초기화
        self.init_ui()
    
    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle("키움증권 자동매매 프로그램")
        self.setGeometry(100, 100, 1200, 800)
        
        # 중앙 위젯 설정
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 메인 레이아웃
        main_layout = QVBoxLayout(central_widget)
        
        # 1. 로그인 영역
        login_group = self.create_login_group()
        main_layout.addWidget(login_group)
        
        # 2. 상단 영역 (종목조회 + 주문입력)
        top_layout = QHBoxLayout()
        
        # 2-1. 종목 조회 영역
        stock_info_group = self.create_stock_info_group()
        top_layout.addWidget(stock_info_group)
        
        # 2-2. 주문 입력 영역
        order_group = self.create_order_group()
        top_layout.addWidget(order_group)
        
        main_layout.addLayout(top_layout)
        
        # 3. 보유 종목 영역
        holdings_group = self.create_holdings_group()
        main_layout.addWidget(holdings_group)
        
        # 4. 로그 영역
        log_group = self.create_log_group()
        main_layout.addWidget(log_group)
        
        # 레이아웃 비율 설정
        main_layout.setStretch(0, 1)  # 로그인
        main_layout.setStretch(1, 2)  # 종목조회+주문
        main_layout.setStretch(2, 3)  # 보유종목
        main_layout.setStretch(3, 2)  # 로그
    
    def create_login_group(self):
        """로그인 영역 생성"""
        group = QGroupBox("접속 정보")
        layout = QHBoxLayout()
        
        # 로그인 버튼
        self.btn_login = QPushButton("로그인")
        self.btn_login.clicked.connect(self.login)
        self.btn_login.setFixedSize(100, 40)
        layout.addWidget(self.btn_login)
        
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
                
                self.log("✅ 로그인 성공!")
                self.btn_login.setEnabled(False)
            else:
                self.log("❌ 로그인 실패")
                
        except Exception as e:
            self.log(f"❌ 로그인 오류: {str(e)}")
            QMessageBox.critical(self, "오류", f"로그인 중 오류가 발생했습니다:\n{str(e)}")
    
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
        
        # TODO: 실제 매수 주문 기능 구현
        self.log(f"📈 매수 주문 (준비중): {stock_code} / {qty}주 / {price}원")
        QMessageBox.information(self, "알림", "매수 주문 기능은 곧 구현될 예정입니다.")
    
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
        
        # TODO: 실제 매도 주문 기능 구현
        self.log(f"📉 매도 주문 (준비중): {stock_code} / {qty}주 / {price}원")
        QMessageBox.information(self, "알림", "매도 주문 기능은 곧 구현될 예정입니다.")
    
    @pyqtSlot()
    def refresh_holdings(self):
        """보유 종목 새로고침"""
        if self.kiwoom is None or self.kiwoom.get_connect_state() != 1:
            QMessageBox.warning(self, "경고", "먼저 로그인해주세요.")
            return
        
        # TODO: 실제 보유 종목 조회 기능 구현
        self.log("보유 종목 조회 (준비중)")
        QMessageBox.information(self, "알림", "보유 종목 조회 기능은 곧 구현될 예정입니다.")
    
    def log(self, message):
        """로그 출력"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.text_log.append(f"[{timestamp}] {message}")
