"""
키움증권 자동매매 프로그램 실행 파일
"""
import sys
from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow
from core.version import VERSION, APP_NAME


def main():
    """메인 함수"""
    print(f"==========================================")
    print(f" ✨ {APP_NAME} Ver {VERSION} 시작합니다.")
    print(f"==========================================")
    
    app = QApplication(sys.argv)
    
    # 메인 윈도우 생성 및 표시
    window = MainWindow()
    window.show()
    
    # 이벤트 루프 실행
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
