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
    운용 자산 관리 클래스
    
    주요 기능:
    - 운용 금액 설정 및 관리
    - 가용 자산 계산
    - 매수 주문 가능 여부 검증
    - 수익/손실 추적
    """
    
    def __init__(self, user_id: str = None):
        """
        Args:
            user_id: 사용자 ID (없으면 기본값 초기화)
        """
        if user_id:
            self.config_file = f"asset_config_{user_id}.json"
            self.data = self._load_config()
        else:
            self.config_file = None
            self.data = self._get_default_config()

    def load_user_config(self, user_id: str):
        """사용자별 설정 로드"""
        self.config_file = f"asset_config_{user_id}.json"
        self.data = self._load_config()
    
    def _load_config(self) -> Dict:
        """설정 파일 로드"""
        if self.config_file and os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)
                    
                    # 기본값 생성
                    data = self._get_default_config()
                    
                    # 저장된 데이터 모두 복원 (사용자 요청: 설정값 유지 및 이어하기)
                    # 초기 설정액, 가용 현금, 누적 수익 등 모든 상태를 마지막 저장 시점으로 복구합니다.
                    data.update(saved_data)
                    
                    return data
            except Exception as e:
                print(f"설정 파일 로드 실패: {e}")
                return self._get_default_config()
        else:
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """기본 설정 반환"""
        return {
            'initial_capital': 0,           # 초기 설정 금액
            'current_capital': 0,           # 현재 운용 금액
            'available_cash': 0,            # 가용 현금
            'holdings_value': 0,            # 보유 종목 평가액
            'total_profit': 0,              # 누적 수익금
            'profit_rate': 0.0,             # 수익률 (%)
            'max_stock_amount': 0,          # 종목당 최대 매수 금액 (기본 0 = 무제한)
            'last_updated': None
        }
    
    def _save_config(self):
        """설정 파일 저장"""
        if not self.config_file:
            return
            
        try:
            self.data['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"설정 파일 저장 실패: {e}")
    
    # ========== 운용 금액 설정 ==========
    
    def set_initial_capital(self, amount: int):
        """
        초기 운용 금액 설정
        
        Args:
            amount: 운용할 금액 (원)
        """
        if amount <= 0:
            raise ValueError("운용 금액은 0보다 커야 합니다.")
        
        self.data['initial_capital'] = amount
        self.data['current_capital'] = amount
        self.data['available_cash'] = amount
        self.data['holdings_value'] = 0
        self.data['total_profit'] = 0
        self.data['profit_rate'] = 0.0
        
        self._save_config()
        self._save_config()
        print(f"✅ 초기 운용 금액 설정: {amount:,}원")

    def add_capital(self, amount: int):
        """운용 자금 추가 (증액)"""
        if amount <= 0:
            raise ValueError("추가 금액은 0보다 커야 합니다.")
            
        self.data['initial_capital'] += amount
        self.data['current_capital'] += amount
        self.data['available_cash'] += amount
        
        if self.data['initial_capital'] > 0:
            self.data['profit_rate'] = (self.data['total_profit'] / self.data['initial_capital']) * 100
            
        self._save_config()
        print(f"✅ 운용 자금 추가: +{amount:,}원 (총 {self.data['initial_capital']:,}원)")

    def get_total_capital(self) -> int:
        """현재 운용 설정액(initial_capital) 반환"""
        return self.data.get('initial_capital', 0)

    def withdraw_capital(self, amount: int):
        """운용 자금 축소 (감액)"""
        if amount <= 0:
            raise ValueError("축소할 금액은 0보다 커야 합니다.")
            
        if amount > self.data['available_cash']:
            raise ValueError(f"가용 현금이 부족합니다. (가용: {self.data['available_cash']:,}원)")
            
        self.data['initial_capital'] -= amount
        self.data['current_capital'] -= amount
        self.data['available_cash'] -= amount
        
        if self.data['initial_capital'] > 0:
            self.data['profit_rate'] = (self.data['total_profit'] / self.data['initial_capital']) * 100
        else:
            self.data['profit_rate'] = 0.0
            
        self._save_config()
        print(f"✅ 운용 자금 축소: -{amount:,}원 (총 {self.data['initial_capital']:,}원)")

    
    def set_max_stock_amount(self, amount: int):
        """
        종목당 최대 매수 금액 설정
        
        Args:
            amount: 종목당 최대 매수 금액 (원)
        """
        if amount < 0:
            raise ValueError("최대 매수 금액은 0보다 작을 수 없습니다.")
        
        self.data['max_stock_amount'] = amount
        self._save_config()
        print(f"✅ 종목당 최대 매수 금액 설정: {amount:,}원")
    
    # ========== 자산 조회 ==========
    
    def get_initial_capital(self) -> int:
        """초기 운용 금액 조회"""
        return self.data['initial_capital']
    
    def get_current_capital(self) -> int:
        """현재 운용 금액 조회 (수익/손실 반영)"""
        return self.data['current_capital']
    
    def get_available_cash(self) -> int:
        """가용 현금 조회"""
        return self.data['available_cash']
    
    def get_holdings_value(self) -> int:
        """보유 종목 평가액 조회"""
        return self.data['holdings_value']
    
    def get_total_profit(self) -> int:
        """누적 수익금 조회"""
        return self.data['total_profit']
    
    def get_profit_rate(self) -> float:
        """수익률 조회 (%)"""
        return self.data['profit_rate']
    
    def get_max_stock_amount(self) -> int:
        """종목당 최대 매수 금액 조회"""
        return self.data['max_stock_amount']
    
    def get_summary(self) -> Dict:
        """자산 현황 요약 반환"""
        return {
            '초기_운용금액': self.data['initial_capital'],
            '초기_설정액': self.data['initial_capital'],
            '현재_운용금액': self.data['current_capital'],
            '가용_현금': self.data['available_cash'],
            '보유종목_평가액': self.data['holdings_value'],
            '누적_수익금': self.data['total_profit'],
            '수익률': self.data['profit_rate'],
            '종목당_최대매수금액': self.data['max_stock_amount']
        }
    
    # ========== 자산 업데이트 ==========
    
    def update_holdings_value(self, holdings_value: int):
        """
        보유 종목 평가액 업데이트
        
        Args:
            holdings_value: 현재 보유 종목 평가액
        """
        self.data['holdings_value'] = holdings_value
        
        # 현재 운용 금액 = 가용 현금 + 보유 종목 평가액
        self.data['current_capital'] = self.data['available_cash'] + holdings_value
        
        # 수익금 및 수익률 계산
        if self.data['initial_capital'] > 0:
            self.data['total_profit'] = self.data['current_capital'] - self.data['initial_capital']
            self.data['profit_rate'] = (self.data['total_profit'] / self.data['initial_capital']) * 100
        
        self._save_config()
    
    def update_available_cash(self, cash: int):
        """
        가용 현금 업데이트
        
        Args:
            cash: 현재 가용 현금
        """
        self.data['available_cash'] = cash
        
        # 현재 운용 금액 재계산
        self.data['current_capital'] = cash + self.data['holdings_value']
        
        # 수익금 및 수익률 재계산
        if self.data['initial_capital'] > 0:
            self.data['total_profit'] = self.data['current_capital'] - self.data['initial_capital']
            self.data['profit_rate'] = (self.data['total_profit'] / self.data['initial_capital']) * 100
        
        self._save_config()
    
    def update_from_account(self, available_cash: int, holdings_value: int):
        """
        계좌 정보로부터 자산 업데이트
        
        Args:
            available_cash: 가용 현금
            holdings_value: 보유 종목 평가액
        """
        self.data['available_cash'] = available_cash
        self.data['holdings_value'] = holdings_value
        self.data['current_capital'] = available_cash + holdings_value
        
        # 수익금 및 수익률 계산
        if self.data['initial_capital'] > 0:
            self.data['total_profit'] = self.data['current_capital'] - self.data['initial_capital']
            self.data['profit_rate'] = (self.data['total_profit'] / self.data['initial_capital']) * 100
        
        self._save_config()
    
    # ========== 주문 검증 ==========
    
    def can_buy(self, amount: int) -> tuple[bool, str]:
        """
        매수 가능 여부 검증
        
        Args:
            amount: 매수하려는 금액 (원)
        
        Returns:
            (가능 여부, 메시지)
        """
        # 1. 운용 금액이 설정되어 있는지 확인
        if self.data['initial_capital'] <= 0:
            return False, "운용 금액이 설정되지 않았습니다."
        
        # 2. 가용 현금이 충분한지 확인
        if amount > self.data['available_cash']:
            return False, f"가용 현금 부족 (필요: {amount:,}원, 보유: {self.data['available_cash']:,}원)"
        
        # 3. 종목당 최대 매수 금액 확인 (0이면 제한 없음)
        if self.data['max_stock_amount'] > 0 and amount > self.data['max_stock_amount']:
            return False, f"종목당 최대 매수 한도 초과 (한도: {self.data['max_stock_amount']:,}원)"
        
        return True, "매수 가능"
    
    def reserve_cash(self, amount: int) -> bool:
        """
        매수 주문을 위한 현금 예약
        
        Args:
            amount: 예약할 금액
        
        Returns:
            성공 여부
        """
        can_buy, message = self.can_buy(amount)
        if not can_buy:
            print(f"❌ 현금 예약 실패: {message}")
            return False
        
        self.data['available_cash'] -= amount
        self._save_config()
        print(f"✅ 현금 예약 성공: {amount:,}원 (잔여: {self.data['available_cash']:,}원)")
        return True
    
    def release_cash(self, amount: int):
        """
        예약된 현금 해제 (주문 취소 시)
        
        Args:
            amount: 해제할 금액
        """
        self.data['available_cash'] += amount
        self._save_config()
        print(f"✅ 현금 해제: {amount:,}원 (잔여: {self.data['available_cash']:,}원)")

    def release_cash_after_sell(self, amount: int):
        """
        매도 성공 후 금액을 가용 현금으로 환원 (즉시 재투자 가능하도록)
        
        Args:
            amount: 매도된 총 금액 (현재가 * 수량)
        """
        # 세금/수수료 고려 시 약간의 오차가 있을 수 있지만, 
        # 가용 현금으로 즉시 돌려서 다음 매수를 가능하게 합니다.
        self.data['available_cash'] += amount
        
        # 현재 운용 금액 및 수익률 재계산
        self.update_available_cash(self.data['available_cash'])
        print(f"💰 [자산환원] 매도 수익 {amount:,}원이 가용 현금으로 추가되었습니다.")
    
    # ========== 리셋 ==========
    
    def reset(self):
        """자산 관리 초기화"""
        self.data = self._get_default_config()
        self._save_config()
        print("✅ 자산 관리 초기화 완료")


# ========== 테스트 코드 ==========

if __name__ == "__main__":
    print("=" * 50)
    print("AssetManager 테스트")
    print("=" * 50)
    
    # 테스트용 설정 파일
    test_config = "test_asset_config.json"
    
    # AssetManager 생성
    manager = AssetManager(test_config)
    
    # 1. 초기 운용 금액 설정
    print("\n[1] 초기 운용 금액 설정")
    manager.set_initial_capital(5000000)  # 500만원
    manager.set_max_stock_amount(1000000)  # 종목당 100만원
    
    # 2. 자산 현황 조회
    print("\n[2] 자산 현황")
    summary = manager.get_summary()
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"{key}: {value:.2f}%")
        else:
            print(f"{key}: {value:,}원")
    
    # 3. 매수 가능 여부 테스트
    print("\n[3] 매수 가능 여부 테스트")
    test_amounts = [500000, 1500000, 6000000]
    for amount in test_amounts:
        can_buy, message = manager.can_buy(amount)
        status = "✅" if can_buy else "❌"
        print(f"{status} {amount:,}원 매수: {message}")
    
    # 4. 현금 예약 테스트
    print("\n[4] 현금 예약 테스트")
    manager.reserve_cash(1000000)  # 100만원 예약
    
    # 5. 보유 종목 평가액 업데이트
    print("\n[5] 보유 종목 평가액 업데이트")
    manager.update_holdings_value(1200000)  # 120만원 (20만원 수익)
    
    # 6. 최종 자산 현황
    print("\n[6] 최종 자산 현황")
    summary = manager.get_summary()
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"{key}: {value:.2f}%")
        else:
            print(f"{key}: {value:,}원")
    
    # 테스트 파일 삭제
    if os.path.exists(test_config):
        os.remove(test_config)
        print(f"\n테스트 파일 삭제: {test_config}")
