from PyQt5.QtCore import QObject, pyqtSignal

class Strategy(QObject):
    """전략 기본 클래스"""
    # 로그 메시지 발생 시그널
    log_msg = pyqtSignal(str)
    
    def __init__(self, kiwoom, asset_manager):
        super().__init__()
        self.kiwoom = kiwoom
        self.asset_manager = asset_manager
        self.params = {
            'k': 0.5,
            'stop_loss': -2.0, 
            'take_profit': 5.0
        }
        self.config_file = None

    def load_config(self, user_id):
        """사용자별 전략 설정 로드"""
        import json
        import os
        self.config_file = f"strategy_config_{user_id}.json"
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved_params = json.load(f)
                    self.params.update(saved_params)
                self.log_msg.emit(f"⚙️ 전략 설정 로드 완료: {user_id}")
            except Exception as e:
                self.log_msg.emit(f"⚠️ 전략 설정 로드 실패: {e}")
        else:
            self.log_msg.emit(f"ℹ️ 저장된 전략 설정이 없어 기본값을 사용합니다.")

    def save_config(self):
        """전략 설정 저장"""
        import json
        if not self.config_file:
            return
            
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.params, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log_msg.emit(f"⚠️ 전략 설정 저장 실패: {e}")
    
    def update_params(self, params):
        self.params.update(params)
        self.log_msg.emit(f"⚙️ 전략 파라미터 업데이트: {self.params}")
        self.save_config()  # 변경 즉시 저장

    def run(self):
        """주기적으로 실행되는 메인 로직"""
        pass

class VolatilityBreakoutStrategy(Strategy):
    """변동성 돌파 전략"""
    def __init__(self, kiwoom, asset_manager):
        super().__init__(kiwoom, asset_manager)
        self.target_prices = {}  # 종목별 목표 매수가
        self.universe = []       # 감시 대상 종목 리스트

    def set_universe(self, codes):
        """감시 대상 종목 설정 및 목표가 계산"""
        self.universe = codes
        self.log_msg.emit(f"📋 감시 대상 종목 설정: {len(codes)}개")
        for code in codes:
            self.calculate_target_price(code)

    def calculate_target_price(self, code):
        """목표 매수가 계산"""
        # 일봉 데이터 조회 (최근 2일치 필요)
        # 중요: API 호출 제한 고려 (타이머로 분산 필요할 수 있으나 일단 단순 호출)
        daily_data = self.kiwoom.get_daily_data(code)
        
        if len(daily_data) < 2:
            self.log_msg.emit(f"⚠️ {code}: 일봉 데이터 부족으로 목표가 계산 불가")
            return

        # 전일 데이터 (인덱스 1)
        yesterday = daily_data[1]
        high = yesterday['고가']
        low = yesterday['저가']
        close = yesterday['종가']
        
        # 금일 시가 (인덱스 0의 시가 or 실시간 시가)
        # 주의: 장 시작 전이나 장 초반에는 인덱스 0이 전일 데이터일 수도 있음
        # 하지만 API 특성상 장 당일엔 오늘 날짜 데이터가 생성됨.
        today = daily_data[0]
        current_open = today['시가']
        
        # 변동폭
        volatility = high - low
        
        # 목표가 = 금일 시가 + (변동폭 * k)
        k = float(self.params['k'])
        target_price = current_open + (volatility * k)
        
        self.target_prices[code] = int(target_price)
        self.log_msg.emit(f"🎯 {code} 목표가 계산 완료: {int(target_price):,}원 (시가: {current_open}, 변동폭: {volatility}, K: {k})")

    def check_buy_signal(self, code, current_price):
        """매수 신호 확인"""
        if code not in self.target_prices:
            return False
            
        target = self.target_prices[code]
        # 현재가가 목표가 이상이면 매수
        if current_price >= target:
            return True
        return False

    def check_sell_signal(self, code, current_price, buy_price):
        """매도 신호 확인 (손절/익절)"""
        if buy_price == 0:
            return False, None
            
        profit_rate = (current_price - buy_price) / buy_price * 100
        
        stop_loss = float(self.params['stop_loss'])
        take_profit = float(self.params['take_profit'])
        
        if profit_rate <= stop_loss:
            return True, f"손절 (수익률: {profit_rate:.2f}%)"
        if profit_rate >= take_profit:
            return True, f"익절 (수익률: {profit_rate:.2f}%)"
            
        return False, None
