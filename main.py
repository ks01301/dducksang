"""
키움증권 자동매매 프로그램 실행 파일
"""
import sys
from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow


def main():
    """메인 함수"""
    app = QApplication(sys.argv)
    
    # 메인 윈도우 생성 및 표시
    window = MainWindow()
    window.show()
    
    # 이벤트 루프 실행
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
