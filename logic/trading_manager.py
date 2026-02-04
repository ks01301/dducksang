import time
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer

class TradingManager(QObject):
    """
    매매 로직 관리 클래스 (Controller/Logic)
    - 실시간 데이터 수신 및 캐싱
    - 매매 신호 포착 (익절/손절)
    - 주문 전송 및 DB 저장
    - 자산 관리자 연동
    """
    # UI 업데이트용 시그널
    sig_log = pyqtSignal(str)  # 로그 메시지
    sig_update_status = pyqtSignal(str, str) # 종목코드, 상태메시지 (예: "매수완료")
    sig_trade_event = pyqtSignal() # 매매 발생 (보유목록/자산 갱신 요청)

    def __init__(self, kiwoom, db, asset_manager, strategy):
        super().__init__()
        self.kiwoom = kiwoom
        self.db = db
        self.asset_manager = asset_manager
        self.strategy = strategy
        
        # 실시간 가격 캐시 (shared with MainWindow via getter if needed)
        self.price_cache = {}
        
        # 이벤트 연결
        self._connect_signals()
        
    def _connect_signals(self):
        """Kiwoom 시그널 연결"""
        self.kiwoom.sig_real_data.connect(self.on_real_data)
        self.kiwoom.sig_chejan_received.connect(self.on_chejan_data)
        
    @pyqtSlot(str, dict)
    def on_real_data(self, code, data):
        """실시간 시세 수신 (캐시 업데이트 + 이벤트 드리븐 감시)"""
        # 1. 캐시 업데이트
        self.price_cache[code] = data
        
        # 2. 이벤트 드리븐 매도 감시 (익절/손절)
        try:
            current_price = int(data.get('current_price', 0))
            if current_price == 0: return

            # 보유 종목인지 확인
            holdings = self.kiwoom.account_holdings
            target_holding = None
            for h in holdings:
                h_code = h['종목코드'].strip()
                if len(h_code) > 6: h_code = h_code[-6:]
                if h_code == code:
                    target_holding = h
                    break
            
            if target_holding:
                buy_price = int(target_holding['매입가'])
                qty = int(target_holding['보유수량'])
                
                if qty > 0 and buy_price > 0:
                    profit_rate = (current_price - buy_price) / buy_price * 100
                    
                    # 1) 익절 (Take Profit)
                    target_rate = self.strategy.params.get('take_profit', 5.0)
                    
                    # 개별 목표가 우선 확인
                    if code in self.strategy.target_prices:
                         target_one = self.strategy.target_prices[code]
                         if current_price >= target_one:
                             self.sig_log.emit(f"⚡ [즉시익절] {code} 목표가({target_one}) 도달! (현재: {current_price}) -> 매도실행")
                             self.kiwoom.send_order(2, code, qty, 0, "ACC_NO_PLACEHOLDER") # MainWindow에서 계좌번호 주입 필요? 
                             # 수정: 계좌번호는 TradingManager가 알고 있거나 인자로 받아야 함. 
                             # 일단 간단히 kiwoom.account_holdings가 있으면 계좌번호도 알 수 있음.
                             # 여기서는 Kiwoom 클래스가 계좌번호를 관리하지 않으므로, 추후 보완.
                             # 임시: strategy나 asset_manager에 계좌번호가 있나? Main이 관리함.
                             # 해결: send_order 호출 시 계좌번호가 필요한데... 
                             # 일단 self.kiwoom에 account_list가 있으므로 첫번째 계좌 사용 (개선 포인트)
                             if self.kiwoom.account_list:
                                acc = self.kiwoom.account_list[0]
                                self.kiwoom.send_order(2, code, qty, 0, acc)
                             del self.strategy.target_prices[code]
                             return

                    if profit_rate >= target_rate:
                        self.sig_log.emit(f"⚡ [즉시익절] {code} 목표수익률({target_rate}%) 달성! (현재: {profit_rate:.2f}%) -> 매도실행")
                        if self.kiwoom.account_list:
                            self.kiwoom.send_order(2, code, qty, 0, self.kiwoom.account_list[0])
                        return

                    # 2) 손절 (Stop Loss)
                    stop_rate = self.strategy.params.get('stop_loss', 3.0)
                    if profit_rate <= -stop_rate:
                         self.sig_log.emit(f"⚡ [즉시손절] {code} 손절라인(-{stop_rate}%) 이탈! (현재: {profit_rate:.2f}%) -> 매도실행")
                         if self.kiwoom.account_list:
                            self.kiwoom.send_order(2, code, qty, 0, self.kiwoom.account_list[0])
                         return
        except Exception as e:
            pass

    @pyqtSlot(str, dict)
    def on_chejan_data(self, gubun, data):
        """체결/잔고 데이터 처리 (DB 저장 및 상태 갱신)"""
        if gubun == '0': # 주문체결
            order_type = data['주문구분'].strip().replace('+', '').replace('-', '')
            stock_code = data['종목코드'].strip()
            if stock_code.startswith('A'): stock_code = stock_code[1:]
            
            if "매수" in order_type:
                try:
                    # [FIX] 접수 vs 체결 구분
                    order_status = data.get('주문상태', '')
                    filled_qty_str = str(data.get('체결수량', '0')).strip()
                    if not filled_qty_str: filled_qty_str = "0"
                    
                    qty = int(filled_qty_str)
                    buy_price = abs(int(data.get('체결가격', '0')))

                    if qty <= 0: return # 접수 단계 무시

                    # 전략: 익절 목표가 자동 설정
                    target_rate = self.strategy.params.get('take_profit', 5.0)
                    target_price = int(buy_price * (1 + target_rate / 100))
                    
                    # 호가 보정
                    if target_price < 1000: target_price = (target_price // 1) * 1
                    elif target_price < 5000: target_price = (target_price // 5) * 5
                    elif target_price < 10000: target_price = (target_price // 10) * 10
                    elif target_price < 50000: target_price = (target_price // 50) * 50
                    else: target_price = (target_price // 100) * 100
                    
                    self.sig_log.emit(f"⚡ [자동예약] {data['종목명']} {qty}주 매수체결! 목표가 {target_price:,}원 설정")
                    self.strategy.target_prices[stock_code] = target_price
                    
                    # UI 상태 업데이트 요청
                    self.sig_update_status.emit(stock_code, "매수완료")
                    
                    # DB 저장 & 자산 갱신
                    name_for_db = data['종목명'].strip()
                    self.db.save_trade(stock_code, name_for_db, "매수", buy_price, qty)
                    self.sig_trade_event.emit()

                except Exception as e:
                    self.sig_log.emit(f"❌ 체결 처리 오류: {e}")
            
            elif "매도" in order_type:
                # 매도 체결 시 처리
                try:
                    filled_qty = int(data.get('체결수량', 0))
                    if filled_qty > 0:
                        price = abs(int(data.get('체결가격', 0)))
                        name = data['종목명'].strip()
                        self.db.save_trade(stock_code, name, "매도", price, filled_qty)
                        
                        # 자산 환원 (AssetManager)
                        total_amount = price * filled_qty
                        self.asset_manager.release_cash_after_sell(total_amount)
                        
                        self.sig_trade_event.emit()
                        self.sig_log.emit(f"📉 [매도체결] {name} {filled_qty}주 정산 완료")
                except Exception as e:
                    self.sig_log.emit(f"❌ 매도 체결 처리 오류: {e}")

    def process_buy_strategy(self, code, current_price, rate, strength, name):
        """매수 전략 확인 및 실행 (MainWindow에서 호출)"""
        # 캐시가 없거나 가격 0이면 스킵
        if current_price == 0: return None
        
        # 1. 매수 신호 확인
        if self.strategy.check_buy_signal(code, current_price):
            # 안전장치들
            try:
                curr_rate = float(rate)
                if curr_rate > 20.0:
                    self.sig_log.emit(f"🛑 [주문차단] {name}: 등락률 과다 ({curr_rate}%)")
                    return "REMOVE" # 목록 제거 신호
            except: pass
            
            if strength < 100.0: return None # 체결강도 약함

            # 2. 주문 실행
            account = self.kiwoom.account_list[0] if self.kiwoom.account_list else ""
            if not account: return None
            
            qty = self.calculate_order_qty(current_price)
            if qty <= 0:
                self.sig_log.emit(f"⚠️ [자산부족] {name} 매수 수량 0")
                return None
                
            total_amt = current_price * qty
            can_buy, msg = self.asset_manager.can_buy(total_amt)
            if not can_buy: return None
            
            self.sig_log.emit(f"💰 [매수시도] {name} {qty}주")
            ret = self.kiwoom.send_order(1, code, qty, 0, account)
            if ret == 0:
                self.asset_manager.reserve_cash(total_amt)
                return "ORDERING" # 주문 중 상태로 변경
                
        return None

    def calculate_order_qty(self, price):
        """주문 수량 계산"""
        # AssetManager의 '1회 매수 금액' 사용 권장하지만, 간단히 여기서 계산 or AssetManager에 위임
        # 여기서는 MainWindow 로직을 가져옴
        one_time_amount = self.asset_manager.one_time_invest_amount
        if price <= 0: return 0
        return int(one_time_amount // price)
