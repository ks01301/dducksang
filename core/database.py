"""
데이터베이스 모듈 (Database)
SQLite를 사용하여 매매 기록 및 일일 리포트를 저장합니다.
"""
import sqlite3
from datetime import datetime, date
from typing import List, Dict, Optional


class Database:
    """
    매매 기록 및 일일 리포트 관리 클래스
    
    주요 기능:
    - 매매 기록 저장 및 조회
    - 일일 요약 저장 및 조회
    - 거래 내역 통계
    """
    
    def __init__(self, db_file: str = "trading.db"):
        """
        Args:
            db_file: 데이터베이스 파일 경로
        """
        self.db_file = db_file
        self.conn = None
        self._connect()
        self._create_tables()
    
    def _connect(self):
        """데이터베이스 연결"""
        try:
            self.conn = sqlite3.connect(self.db_file)
            self.conn.row_factory = sqlite3.Row  # 딕셔너리 형태로 결과 반환
            print(f"✅ 데이터베이스 연결: {self.db_file}")
        except Exception as e:
            print(f"❌ 데이터베이스 연결 실패: {e}")
    
    def _create_tables(self):
        """테이블 생성"""
        cursor = self.conn.cursor()
        
        # 1. daily_summary 테이블 (일일 요약)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_summary (
                date TEXT PRIMARY KEY,
                initial_capital INTEGER,
                final_capital INTEGER,
                profit INTEGER,
                profit_rate REAL,
                trade_count INTEGER,
                created_at TEXT
            )
        ''')
        
        # 2. trade_log 테이블 (매매 기록)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                stock_code TEXT,
                stock_name TEXT,
                trade_type TEXT,
                price INTEGER,
                quantity INTEGER,
                total_amount INTEGER,
                order_number TEXT,
                created_at TEXT
            )
        ''')
        
        self.conn.commit()
        print("✅ 테이블 생성 완료")
    
    # ========== 매매 기록 관리 ==========
    
    def save_trade(self, stock_code: str, stock_name: str, trade_type: str,
                   price: int, quantity: int, order_number: str = "") -> int:
        """
        매매 기록 저장
        
        Args:
            stock_code: 종목코드
            stock_name: 종목명
            trade_type: 매매 구분 ("매수" 또는 "매도")
            price: 단가
            quantity: 수량
            order_number: 주문번호
        
        Returns:
            저장된 레코드 ID
        """
        cursor = self.conn.cursor()
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        total_amount = price * quantity
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT INTO trade_log 
            (timestamp, stock_code, stock_name, trade_type, price, quantity, 
             total_amount, order_number, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, stock_code, stock_name, trade_type, price, quantity,
              total_amount, order_number, created_at))
        
        self.conn.commit()
        
        record_id = cursor.lastrowid
        print(f"✅ 매매 기록 저장: {stock_name}({stock_code}) {trade_type} {quantity}주 @ {price:,}원")
        
        return record_id
    
    def get_trade_history(self, start_date: str = None, end_date: str = None,
                          stock_code: str = None, trade_type: str = None) -> List[Dict]:
        """
        매매 내역 조회
        
        Args:
            start_date: 시작 날짜 (YYYY-MM-DD)
            end_date: 종료 날짜 (YYYY-MM-DD)
            stock_code: 종목코드 (선택)
            trade_type: 매매 구분 (선택)
        
        Returns:
            매매 내역 리스트
        """
        cursor = self.conn.cursor()
        
        query = "SELECT * FROM trade_log WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND date(timestamp) >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND date(timestamp) <= ?"
            params.append(end_date)
        
        if stock_code:
            query += " AND stock_code = ?"
            params.append(stock_code)
        
        if trade_type:
            query += " AND trade_type = ?"
            params.append(trade_type)
        
        query += " ORDER BY timestamp DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
    
    def get_today_trades(self) -> List[Dict]:
        """오늘의 매매 내역 조회"""
        today = date.today().strftime('%Y-%m-%d')
        return self.get_trade_history(start_date=today, end_date=today)
    
    def get_trade_count(self, start_date: str = None, end_date: str = None) -> int:
        """매매 횟수 조회"""
        cursor = self.conn.cursor()
        
        query = "SELECT COUNT(*) as count FROM trade_log WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND date(timestamp) >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND date(timestamp) <= ?"
            params.append(end_date)
        
        cursor.execute(query, params)
        result = cursor.fetchone()
        
        return result['count'] if result else 0
    
    # ========== 일일 요약 관리 ==========
    
    def save_daily_summary(self, target_date: str, initial_capital: int,
                          final_capital: int, profit: int, profit_rate: float,
                          trade_count: int):
        """
        일일 요약 저장
        
        Args:
            target_date: 날짜 (YYYY-MM-DD)
            initial_capital: 기초 자산
            final_capital: 기말 자산
            profit: 당일 수익금
            profit_rate: 수익률 (%)
            trade_count: 거래 횟수
        """
        cursor = self.conn.cursor()
        
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT OR REPLACE INTO daily_summary
            (date, initial_capital, final_capital, profit, profit_rate, 
             trade_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (target_date, initial_capital, final_capital, profit, profit_rate,
              trade_count, created_at))
        
        self.conn.commit()
        print(f"✅ 일일 요약 저장: {target_date} (수익: {profit:,}원, {profit_rate:.2f}%)")
    
    def get_daily_summary(self, target_date: str) -> Optional[Dict]:
        """
        특정 날짜의 일일 요약 조회
        
        Args:
            target_date: 날짜 (YYYY-MM-DD)
        
        Returns:
            일일 요약 딕셔너리 또는 None
        """
        cursor = self.conn.cursor()
        
        cursor.execute('''
            SELECT * FROM daily_summary WHERE date = ?
        ''', (target_date,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_summary_history(self, start_date: str = None, end_date: str = None) -> List[Dict]:
        """
        일일 요약 내역 조회
        
        Args:
            start_date: 시작 날짜 (YYYY-MM-DD)
            end_date: 종료 날짜 (YYYY-MM-DD)
        
        Returns:
            일일 요약 리스트
        """
        cursor = self.conn.cursor()
        
        query = "SELECT * FROM daily_summary WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        
        query += " ORDER BY date DESC"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        return [dict(row) for row in rows]
    
    def update_daily_summary(self, target_date: str, **kwargs):
        """
        일일 요약 업데이트
        
        Args:
            target_date: 날짜 (YYYY-MM-DD)
            **kwargs: 업데이트할 필드들
        """
        cursor = self.conn.cursor()
        
        # 업데이트할 필드 구성
        set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
        values = list(kwargs.values()) + [target_date]
        
        query = f"UPDATE daily_summary SET {set_clause} WHERE date = ?"
        
        cursor.execute(query, values)
        self.conn.commit()
        
        print(f"✅ 일일 요약 업데이트: {target_date}")
    
    # ========== 통계 ==========
    
    def get_total_profit(self) -> int:
        """전체 누적 수익금 조회"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            SELECT SUM(profit) as total_profit FROM daily_summary
        ''')
        
        result = cursor.fetchone()
        return result['total_profit'] if result and result['total_profit'] else 0
    
    def get_total_trades(self) -> int:
        """전체 거래 횟수 조회"""
        return self.get_trade_count()
    
    # ========== 유틸리티 ==========
    
    def close(self):
        """데이터베이스 연결 종료"""
        if self.conn:
            self.conn.close()
            print("✅ 데이터베이스 연결 종료")
    
    def clear_all(self):
        """모든 데이터 삭제 (주의!)"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM trade_log")
        cursor.execute("DELETE FROM daily_summary")
        self.conn.commit()
        print("✅ 모든 데이터 삭제 완료")


# ========== 테스트 코드 ==========

if __name__ == "__main__":
    print("=" * 50)
    print("Database 테스트")
    print("=" * 50)
    
    # 테스트용 데이터베이스
    test_db = "test_trading.db"
    
    # Database 생성
    db = Database(test_db)
    
    # 1. 매매 기록 저장
    print("\n[1] 매매 기록 저장")
    db.save_trade("005930", "삼성전자", "매수", 70000, 10, "ORD001")
    db.save_trade("000660", "SK하이닉스", "매수", 130000, 5, "ORD002")
    db.save_trade("005930", "삼성전자", "매도", 72000, 5, "ORD003")
    
    # 2. 오늘의 매매 내역 조회
    print("\n[2] 오늘의 매매 내역")
    today_trades = db.get_today_trades()
    for trade in today_trades:
        print(f"  - {trade['stock_name']}({trade['stock_code']}) "
              f"{trade['trade_type']} {trade['quantity']}주 @ {trade['price']:,}원")
    
    # 3. 일일 요약 저장
    print("\n[3] 일일 요약 저장")
    today = date.today().strftime('%Y-%m-%d')
    db.save_daily_summary(
        target_date=today,
        initial_capital=5000000,
        final_capital=5100000,
        profit=100000,
        profit_rate=2.0,
        trade_count=3
    )
    
    # 4. 일일 요약 조회
    print("\n[4] 일일 요약 조회")
    summary = db.get_daily_summary(today)
    if summary:
        print(f"  날짜: {summary['date']}")
        print(f"  기초 자산: {summary['initial_capital']:,}원")
        print(f"  기말 자산: {summary['final_capital']:,}원")
        print(f"  수익금: {summary['profit']:,}원")
        print(f"  수익률: {summary['profit_rate']:.2f}%")
        print(f"  거래 횟수: {summary['trade_count']}회")
    
    # 5. 통계
    print("\n[5] 통계")
    print(f"  전체 거래 횟수: {db.get_total_trades()}회")
    print(f"  전체 누적 수익: {db.get_total_profit():,}원")
    
    # 데이터베이스 종료
    db.close()
    
    # 테스트 파일 삭제
    import os
    if os.path.exists(test_db):
        os.remove(test_db)
        print(f"\n테스트 파일 삭제: {test_db}")
