from PyQt5.QtCore import QObject, pyqtSignal

class Strategy(QObject):
    """전략 기본 클래스"""
    # 로그 메시지 발생 시그널
    log_msg = pyqtSignal(str)
    
    def __init__(self, kiwoom, asset_manager, db=None):
        super().__init__()
        self.kiwoom = kiwoom
        self.asset_manager = asset_manager
        self.db = db
        self.user_id = None
        self.params = {
            'k': 0.5,
            'stop_loss': -2.0, 
            'take_profit': 5.0,
            'min_vol': 100000,
            'confirm_count': 3
        }
        self.universe = []         # 감시 대상 전체 종목 리스트
        self.auto_universe = {}    # {code: strategy_name}
        self.config_file = None

    def load_config(self, user_id):
        """사용자별 전략 설정 로드 (DB 우선, JSON 마이그레이션 포함)"""
        import json
        import os
        self.user_id = user_id
        self.config_file = f"strategy_config_{user_id}.json"
        
        # 1. DB에서 먼저 시도
        if self.db:
            config = self.db.get_strategy_config(user_id)
            if config:
                if config.get('params'):
                    self.params.update(config['params'])
                if config.get('universe'):
                    self.auto_universe = config['universe']
                    for code in self.auto_universe:
                        if code not in self.universe:
                            self.universe.append(code)
                self.log_msg.emit(f"⚙️ 전략 설정 로드 완료 (DB): {user_id} (자동 {len(self.auto_universe)}개 종목)")
                
                # DB 로드 성공 시 JSON이 있다면 삭제 (마이그레이션 완료로 간주)
                if os.path.exists(self.config_file):
                    try:
                        os.remove(self.config_file)
                        self.log_msg.emit(f"🧹 기존 JSON 설정 파일 삭제 완료 (DB 이관 완료)")
                    except: pass
                return

        # 2. DB에 데이터가 없거나 DB를 못 쓸 경우 JSON 검색 (마이그레이션)
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    if 'params' in data:
                        self.params.update(data['params'])
                    else:
                        self.params.update(data)
                    
                    if 'auto_universe' in data:
                        self.auto_universe = data['auto_universe']
                        for code in self.auto_universe:
                            if code not in self.universe:
                                self.universe.append(code)
                                
                self.log_msg.emit(f"⚙️ 전략 설정 로드 완료 (JSON → DB 이관 예정): {user_id}")
                
                # 로드한 즉시 DB에 저장하여 마이그레이션 수행
                self.save_config()
                
            except Exception as e:
                self.log_msg.emit(f"⚠️ 전략 설정 로드 실패 (JSON): {e}")

    def save_config(self):
        """전략 설정 저장 (DB 전용)"""
        if not self.user_id:
            return
            
        try:
            if self.db:
                self.db.save_strategy_config(self.user_id, self.params, self.auto_universe)
                # self.log_msg.emit(f"💾 전략 설정 DB 저장 완료")
            else:
                # DB가 없는 비상 상황용 (거의 없음)
                import json
                data = {'params': self.params, 'auto_universe': self.auto_universe}
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log_msg.emit(f"⚠️ 전략 설정 저장 실패: {e}")
    
    def update_params(self, params):
        self.params.update(params)
        self.log_msg.emit(f"⚙️ 전략 파라미터 업데이트: {self.params}")
        self.save_config()  # 변경 즉시 저장 (DB)

    def run(self):
        """주기적으로 실행되는 메인 로직"""
        pass

    # ---------- 기술적 지표 계산 헬퍼 (Advanced) ----------
    
    def calculate_sma(self, data, period):
        """단순 이동평균 계산"""
        if len(data) < period:
            return None
        prices = [d['종가'] for d in data[:period]]
        return sum(prices) / period

    def calculate_bollinger_bands(self, data, period=20, k=2):
        """볼린저 밴드 계산"""
        if len(data) < period:
            return None, None, None
        
        import math
        prices = [d['종가'] for d in data[:period]]
        avg = sum(prices) / period
        
        # 표준편차
        variance = sum((p - avg) ** 2 for p in prices) / period
        std_dev = math.sqrt(variance)
        
        upper_band = avg + (k * std_dev)
        lower_band = avg - (k * std_dev)
        
        return upper_band, avg, lower_band

    def check_breakout(self, data, period=20):
        """전고점 돌파 확인 (최근 period일 최고가 상향 돌파)"""
        if len(data) < period + 1:
            return False, 0
        
        current_price = data[0]['종가']
        # 오늘 제외 최근 period일 동안의 최고가
        past_highs = [d['고가'] for d in data[1:period+1]]
        max_high = max(past_highs)
        
        return current_price > max_high, max_high

    def check_trend_alignment(self, data):
        """정배열 확인 (주가 > 5 > 20 > 60)"""
        if len(data) < 60:
            return False
            
        sma5 = self.calculate_sma(data, 5)
        sma20 = self.calculate_sma(data, 20)
        sma60 = self.calculate_sma(data, 60)
        
        current_price = data[0]['종가']
        
        if not (sma5 and sma20 and sma60):
            return False
            
        return current_price > sma5 > sma20 > sma60

    def check_golden_cross(self, data, short_p=5, long_p=20):
        """골든크로스 발생 확인 (오늘 뚫고 올라갔는지)"""
        if len(data) < long_p + 1:
            return False
            
        # 오늘 시점
        curr_short = self.calculate_sma(data, short_p)
        curr_long = self.calculate_sma(data, long_p)
        
        # 어제 시점
        prev_data = data[1:]
        prev_short = self.calculate_sma(prev_data, short_p)
        prev_long = self.calculate_sma(prev_data, long_p)
        
        if None in [curr_short, curr_long, prev_short, prev_long]:
            return False
            
        # 어제는 작았는데 오늘은 크면 골든크로스
        return prev_short <= prev_long and curr_short > curr_long

class VolatilityBreakoutStrategy(Strategy):
    """변동성 돌파 전략"""
    def __init__(self, kiwoom, asset_manager, db=None):
        super().__init__(kiwoom, asset_manager, db=db)
        self.target_prices = {}  # 종목별 목표 매수가

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
        self.log_msg.emit(f"🎯 {code} 목표가 계산: {int(target_price):,}원 (시가 {current_open:,} + 변동 {volatility:,} * K {k})")

    def add_stock(self, code):
        """종목 추가 (조건검색 등)"""
        if code not in self.universe:
            self.universe.append(code)
            # 즉시 목표가 계산 시도
            self.calculate_target_price(code)
            self.log_msg.emit(f"➕ 감시 종목 추가: {code}")

    def remove_stock(self, code):
        """종목 제거"""
        if code in self.universe:
            self.universe.remove(code)
            if code in self.target_prices:
                del self.target_prices[code]
            self.log_msg.emit(f"➖ 감시 종목 해제: {code}")


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
        
        # 손절 기준: 입력값이 양수든 음수든 '손실'이므로 음수로 처리
        stop_loss = -abs(float(self.params['stop_loss']))
        take_profit = abs(float(self.params['take_profit']))
        
        if profit_rate <= stop_loss:
            return True, f"손절 (수익률: {profit_rate:.2f}% / 기준: {stop_loss}%)"
        if profit_rate >= take_profit:
            return True, f"익절 (수익률: {profit_rate:.2f}% / 기준: {take_profit}%)"
            
        return False, None
