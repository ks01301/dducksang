"""
자산 관리 모듈 (Asset Manager)
사용자가 설정한 운용 금액 내에서만 매수가 가능하도록 자산을 관리합니다.
"""
import json
import os
from datetime import datetime
from typing import Dict, Optional


class AssetManager:
    """
    운용 자산 관리 클래스 (Logic Fix v2 적용)
    
    핵심 변수 매핑:
    - A (총 추정자산): API에서 조회 (MainWindow 담당)
    - B (봇 운용 설정 자금): initial_capital + realized_profit (current_capital)
    - C (여유 자금): A - B (MainWindow 담당)
    - D (현재 운용 자산): invested_amount (매수 원금 합계)
    - E (매수 가능 현금): B - D (available_cash)
    """
    
    def __init__(self, db=None, user_id: str = None):
        """
        Args:
            db: Database 인스턴스 (필수)
            user_id: 사용자 ID (없으면 기본값 초기화)
        """
        self.db = db
        self.user_id = user_id
        self.config_file = f"asset_config_{user_id}.json" if user_id else "asset_config.json"
        
        # DB가 있으면 DB 로드, 없으면 기본값
        if self.db and self.user_id:
            self.data = self._load_config_from_db()
        else:
            self.data = self._get_default_config()

    def load_user_config(self, user_id: str):
        """사용자별 설정 로드"""
        self.user_id = user_id
        self.config_file = f"asset_config_{user_id}.json"
        
        if self.db:
            self.data = self._load_config_from_db()

    def _load_config_from_db(self) -> Dict:
        """DB에서 설정 로드 (없으면 파일 마이그레이션 시도)"""
        # 1. DB 조회
        db_config = self.db.get_asset_config(self.user_id)
        if db_config:
            print(f"✅ DB에서 자산 설정 로드: {self.user_id}")
            return db_config
            
        # 2. DB에 없으면 JSON 파일 확인 (마이그레이션)
        print(f"⚠️ DB에 설정 없음. 파일 마이그레이션 시도: {self.config_file}")
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)
                    
                    # 데이터 정제 (기존 로직 유지)
                    data = self._get_default_config()
                    if 'total_profit' in saved_data and 'realized_profit' not in saved_data:
                        saved_data['realized_profit'] = saved_data['total_profit']
                    
                    if 'holdings_value' in saved_data and 'invested_amount' not in saved_data:
                        saved_data['invested_amount'] = 0
                    
                    # [FIX] Logic Fix v2 적용에 따른 데이터 마이그레이션
                    # 기존에 전체 계좌 동기화로 인해 오염된 D값(invested_amount)을 0으로 초기화
                    saved_data['invested_amount'] = 0
                        
                    data.update(saved_data)
                    
                    # 3. DB에 저장
                    self.db.save_asset_config(self.user_id, data)
                    print(f"✅ 파일 -> DB 마이그레이션 및 저장 완료")
                    
                    # 4. 파일 삭제
                    try:
                        os.remove(self.config_file)
                        print(f"🗑️ 기존 설정 파일 삭제 완료: {self.config_file}")
                        # 혹시 generic 파일도 있으면 삭제
                        if os.path.exists("asset_config.json"):
                            os.remove("asset_config.json")
                    except Exception as e:
                        print(f"❌ 파일 삭제 실패: {e}")
                        
                    return data
            except Exception as e:
                print(f"❌ 파일 로드/마이그레이션 실패: {e}")
        
        return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """기본 설정 반환"""
        return {
            'initial_capital': 0,           # 초기 설정 금액 (원금)
            'realized_profit': 0,           # 누적 실현 수익금
            'invested_amount': 0,           # 현재 운용 중인 매수 원금 (D)
            'max_stock_amount': 0,          # 종목당 최대 매수 금액
            'last_updated': None
        }
    
    def _save_config(self):
        """설정 저장 (DB로)"""
        if not self.db or not self.user_id:
            return
            
        try:
            self.db.save_asset_config(self.user_id, self.data)
        except Exception as e:
            print(f"❌ 자산 설정 DB 저장 실패: {e}")
    
    # ========== 속성 (Properties) ==========

    @property
    def current_capital(self) -> int:
        """B: 봇 운용 설정 자금 (초기 설정액 + 누적 수익)"""
        return self.data['initial_capital'] + self.data['realized_profit']

    @property
    def available_cash(self) -> int:
        """E: 매수 가능 현금 (운용 설정 자금 - 현재 운용 자산(주식))"""
        # [FIX] D는 이제 '총 운용 자산'으로 의미 변화됨.
        # 따라서 E = B - (주식 매수 원금)
        return self.current_capital - self.data['invested_amount']

    @property
    def total_managed_asset(self) -> int:
        """D: 총 운용 자산 (주식 매입금 + 현금) -> 이론상 B와 근접해야 함"""
        # 현재 운용 중인 '주식 가치' + '현금'
        return self.data['invested_amount'] + self.available_cash

    # ========== 운용 금액 설정 ==========
    
    def set_initial_capital(self, amount: int):
        """초기 운용 금액 설정"""
        if amount <= 0:
            raise ValueError("운용 금액은 0보다 커야 합니다.")
        
        # 완전 초기화 개념이므로 수익금 등도 리셋할지 여부는 정책 결정.
        # 여기서는 원금만 재설정하고 수익금은 유지하는 방향으로 하되,
        # 사용자가 '초기화'를 원하면 reset()을 호출해야 함.
        # 하지만 명시적으로 값을 세팅하는 것이므로 원금 변경으로 간주.
        self.data['initial_capital'] = amount
        self._save_config()
        print(f"✅ 초기 운용 금액 설정: {amount:,}원")

    def add_capital(self, amount: int):
        """운용 자금 추가 (증액)"""
        if amount <= 0: raise ValueError("추가 금액은 0보다 커야 합니다.")
        self.data['initial_capital'] += amount
        self._save_config()
        print(f"✅ 운용 자금 추가: +{amount:,}원")

    def withdraw_capital(self, amount: int):
        """운용 자금 축소 (감액)"""
        if amount <= 0: raise ValueError("축소할 금액은 0보다 커야 합니다.")
        
        # 가용 현금 내에서만 출금 가능
        if amount > self.available_cash:
            raise ValueError(f"가용 현금이 부족합니다. (가용: {self.available_cash:,}원)")
            
        self.data['initial_capital'] -= amount
        self._save_config()
        print(f"✅ 운용 자금 축소: -{amount:,}원")

    def set_max_stock_amount(self, amount: int):
        """종목당 최대 매수 금액 설정"""
        if amount < 0: raise ValueError("최대 매수 금액은 0보다 작을 수 없습니다.")
        self.data['max_stock_amount'] = amount
        self._save_config()

    def get_max_stock_amount(self) -> int:
        """종목당 최대 매수 금액 조회"""
        return self.data['max_stock_amount']

    # ========== 자산 조회 ==========
    
    def get_summary(self) -> Dict:
        """자산 현황 요약 반환 (UI 표시용)"""
        # 수익률 계산: 누적수익 / 현재운용자금 (또는 초기자금?)
        # 스펙상: 누적수익금 / B * 100
        profit_rate = 0.0
        if self.current_capital > 0:
            profit_rate = (self.data['realized_profit'] / self.current_capital) * 100
            
        return {
            '초기_설정액': self.data['initial_capital'],
            '현재_운용금액': self.current_capital,      # B
            '가용_현금': self.available_cash,           # E
            '현재_운용자산': self.total_managed_asset,  # D (수정됨: 주식+현금)
            '누적_수익금': self.data['realized_profit'],
            '수익률': profit_rate,
            '종목당_최대매수금액': self.data['max_stock_amount']
        }
    
    # ========== 거래 / 상태 업데이트 ==========

    def register_buy(self, amount: int):
        """매수 실행 등록 (D 증가, E 감소)"""
        self.data['invested_amount'] += amount
        self._save_config()
        print(f"📉 [자산] 매수 반영: 운용자산 +{amount:,}원")

    def register_sell(self, buy_amount: int, sell_amount: int):
        """매도 실행 등록 (D 감소, B 증가, E 증가)"""
        profit = sell_amount - buy_amount
        
        self.data['invested_amount'] -= buy_amount
        # D 가 음수가 되는 것을 방지 (데이터 불일치 시)
        if self.data['invested_amount'] < 0:
            self.data['invested_amount'] = 0
            
        self.data['realized_profit'] += profit
        
        self._save_config()
        print(f"📈 [자산] 매도 반영: 원금회수 {buy_amount:,}원 + 수익 {profit:,}원 -> 가용현금 환원")

    def sync_invested_amount(self, amount: int):
        """
        외부(API/UI) 데이터로 운용 중인 자산(매수 원금) 동기화
        사용자 요청으로 전체 계좌 보유분 합산을 [D]로 사용
        """
        self.data['invested_amount'] = amount
        self._save_config()

    def smart_sync_invested_amount(self, api_holdings: list, db_trades: list):
        """
        [Smart Sync] API 보유 종목 중 'DB 매매 기록'에 있는 종목만 추려서 D(매수 원금) 재계산
        """
        if not api_holdings:
            self.data['invested_amount'] = 0
            self._save_config()
            return

        total_bot_investment = 0
        
        # DB에 기록된 종목 코드 집합 (중복 제거)
        bot_stock_codes = set([t['stock_code'] for t in db_trades])
        
        for holding in api_holdings:
            code = holding.get('종목코드', '').replace('A', '').strip()
            if code in bot_stock_codes:
                try:
                    # 매입가 * 수량
                    avg_price = int(holding.get('매입가', '0').replace(',', ''))
                    qty = int(holding.get('보유수량', '0').replace(',', ''))
                    total_bot_investment += (avg_price * qty)
                    print(f"🔄 [Smart Sync] 봇 관리 종목 식별: {holding.get('종목명')} ({qty}주)")
                except: pass
        
        self.data['invested_amount'] = total_bot_investment
        self._save_config()
        print(f"✅ [Smart Sync] 봇 운용 주식 매수 원금 재계산: {total_bot_investment:,}원")
    
    def can_buy(self, amount: int) -> tuple[bool, str]:
        """매수 가능 여부 검증"""
        if self.data['initial_capital'] <= 0:
            return False, "운용 금액이 설정되지 않았습니다."
        
        if amount > self.available_cash:
            return False, f"가용 현금 부족 (필요: {amount:,}원, 보유: {self.available_cash:,}원)"
        
        if self.data['max_stock_amount'] > 0 and amount > self.data['max_stock_amount']:
            return False, f"종목당 최대 매수 한도 초과 (한도: {self.data['max_stock_amount']:,}원)"
        
        return True, "매수 가능"
    
    def calculate_order_qty(self, price: int) -> int:
        """주문 수량 계산 (종목당 최대 매수 금액 기준)"""
        if price <= 0: return 0
        max_amount = self.get_max_stock_amount()
        if max_amount <= 0: return 0
        return int(max_amount // price)
    
    def reserve_cash(self, amount: int) -> bool:
        """매수 주문 시 현금 예약 (즉시 D 증가 처리)"""
        # 실제 체결이 안 되어도 주문 나갈 때 자산 잡음 (보수적 접근)
        can, msg = self.can_buy(amount)
        if not can:
            print(f"❌ 현금 예약 실패: {msg}")
            return False
            
        self.register_buy(amount)
        return True
    
    def release_cash(self, amount: int):
        """주문 취소/미체결 시 예약 해제 (D 감소)"""
        self.data['invested_amount'] -= amount
        if self.data['invested_amount'] < 0:
            self.data['invested_amount'] = 0
        self._save_config()
        print(f"✅ 현금 예약 해제: {amount:,}원")

    def reset(self):
        """자산 관리 초기화"""
        self.data = self._get_default_config()
        self._save_config()
        print("✅ 자산 관리 초기화 완료")
    
    # ========== 사용하지 않는 메서드 (호환성 유지용 빈 껍데기 or 삭제) ==========
    def update_holdings_value(self, val): pass
    def update_available_cash(self, val): pass
    def update_from_account(self, cash, val): pass
    def get_current_capital(self): return self.current_capital
    def get_available_cash(self): return self.available_cash
    def get_total_capital(self): return self.data['initial_capital']
    def get_holdings_value(self): return self.data['invested_amount'] # 의미 변경 주의
