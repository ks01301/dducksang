# 📦 EXE 빌드 가이드

## 🔧 준비 사항

### 1. PyInstaller 설치

```bash
pip install pyinstaller
```

### 2. requirements.txt 확인

다음 패키지들이 설치되어 있어야 합니다:

```
PyQt5
pywin32
```

---

## 🚀 빌드 방법

### 방법 1: Spec 파일 사용 (권장)

```bash
pyinstaller build.spec
```

### 방법 2: 명령줄로 직접 빌드

```bash
pyinstaller --onefile --windowed --name="DDuckSang_AutoTrading" ^
  --hidden-import=PyQt5.QtCore ^
  --hidden-import=PyQt5.QtGui ^
  --hidden-import=PyQt5.QtWidgets ^
  --hidden-import=PyQt5.QAxContainer ^
  main.py
```

---

## 📁 빌드 결과

빌드가 완료되면 다음 폴더 구조가 생성됩니다:

```
project/
├── build/              # 임시 빌드 파일 (삭제 가능)
├── dist/               # 최종 실행 파일
│   └── DDuckSang_AutoTrading.exe
└── DDuckSang_AutoTrading.spec
```

---

## ⚠️ 중요 제약사항

### 키움 API 요구사항

키움증권 OpenAPI는 **ActiveX 컨트롤**이므로:

1. **32비트 Python 필수**
   - 64비트 Python에서는 작동 불가
   - 32비트 Python 3.7~3.10 권장

2. **키움 OpenAPI+ 설치 필요**
   - exe 실행 전 대상 PC에 키움 OpenAPI+ 설치 필수
   - [다운로드 링크](https://www.kiwoom.com/nkw.templateFrameSet.do?m=m1408000000)

3. **Windows 전용**
   - macOS, Linux에서는 실행 불가

---

## 📦 배포 패키지 구성

다른 환경에서 실행하려면 다음 파일들을 함께 배포:

```
배포_폴더/
├── DDuckSang_AutoTrading.exe  # 실행 파일
├── README.md                   # 사용 설명서
└── INSTALL.md                  # 설치 가이드
```

---

## 🔍 테스트 방법

### 1. 로컬 테스트

```bash
# dist 폴더의 exe 실행
cd dist
DDuckSang_AutoTrading.exe
```

### 2. 다른 PC에서 테스트

1. 키움 OpenAPI+ 설치
2. 키움증권 계좌 로그인
3. exe 실행

---

## 🐛 문제 해결

### "OCX 컨트롤을 등록할 수 없습니다"

→ 키움 OpenAPI+ 재설치

### "DLL을 찾을 수 없습니다"

→ Visual C++ Redistributable 설치

### "Python 버전 오류"

→ 32비트 Python으로 빌드 확인

---

## 📝 빌드 전 체크리스트

- [ ] 32비트 Python 사용 중
- [ ] 모든 의존성 설치됨 (`pip install -r requirements.txt`)
- [ ] 키움 API 로컬에서 정상 작동 확인
- [ ] `.gitignore`에 `build/`, `dist/`, `*.spec` 추가 고려

---

## 🎯 권장사항

### 개발 환경

```bash
# 가상환경 사용
python -m venv venv_32bit
venv_32bit\Scripts\activate
pip install -r requirements.txt
```

### 배포 시

- console=False로 변경 (콘솔 창 숨김)
- 아이콘 파일 추가 (icon='icon.ico')
- 버전 정보 추가

---

## 💡 대안: 설치 프로그램 제작

더 전문적인 배포를 원한다면:

1. **Inno Setup**: Windows 설치 프로그램 제작
2. **NSIS**: 커스터마이징 가능한 설치 프로그램

하지만 키움 API 특성상 **exe 단독 배포가 가장 간단**합니다.
