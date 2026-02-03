; DDuckSang 자동매매 프로그램 설치 스크립트
; Inno Setup 6.x 이상 필요

#define MyAppName "DDuckSang 자동매매"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "DDuckSang Trading"
#define MyAppExeName "DDuckSang_AutoTrading.exe"
#define MyAppURL "https://github.com/ks01301/dducksang"

[Setup]
; 기본 설정
AppId={{8F9D4E2A-1B3C-4D5E-6F7A-8B9C0D1E2F3A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\DDuckSang
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=DDuckSang_Installer_v{#MyAppVersion}
SetupIconFile=icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

; 언어 설정
[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면 바로가기 만들기"; GroupDescription: "추가 아이콘:"; Flags: unchecked
Name: "quicklaunchicon"; Description: "빠른 실행 바로가기 만들기"; GroupDescription: "추가 아이콘:"; Flags: unchecked

[Files]
; 메인 실행 파일
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; 추가 파일들
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "INSTALL.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "BUILD_INSTRUCTIONS.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\설치 가이드"; Filename: "{app}\INSTALL.md"
Name: "{group}\{#MyAppName} 제거"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
; 설치 완료 후 실행
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  KiwoomAPIPage: TOutputMsgWizardPage;
  NeedsKiwoomAPI: Boolean;

// 키움 OpenAPI+ 설치 확인
function IsKiwoomAPIInstalled: Boolean;
var
  RegValue: String;
begin
  Result := False;
  
  // 레지스트리에서 키움 API 설치 확인
  if RegQueryStringValue(HKEY_CLASSES_ROOT, 'CLSID\{A1574A0D-6BFA-4BD7-9020-DED88711818D}\InprocServer32', '', RegValue) then
  begin
    Result := FileExists(RegValue);
  end;
end;

// 키움 API 다운로드 URL 열기
function DownloadKiwoomAPI: Boolean;
var
  ErrorCode: Integer;
begin
  Result := ShellExec('', 'https://www.kiwoom.com/nkw.templateFrameSet.do?m=m1408000000', '', '', SW_SHOW, ewNoWait, ErrorCode);
end;

// 초기화
procedure InitializeWizard;
begin
  NeedsKiwoomAPI := not IsKiwoomAPIInstalled;
  
  if NeedsKiwoomAPI then
  begin
    // 키움 API 설치 안내 페이지 생성
    KiwoomAPIPage := CreateOutputMsgPage(wpWelcome,
      '키움 OpenAPI+ 설치 필요',
      '자동매매를 위해 키움 OpenAPI+가 필요합니다.',
      '키움증권 OpenAPI+가 설치되지 않았습니다.' + #13#10 + #13#10 +
      '다음 단계로 진행하면 키움증권 다운로드 페이지가 열립니다.' + #13#10 +
      '1. OpenAPI+ 다운로드 및 설치' + #13#10 +
      '2. 컴퓨터 재부팅 (권장)' + #13#10 +
      '3. 이 설치 프로그램 계속 진행' + #13#10 + #13#10 +
      '이미 설치하셨다면 "다음"을 클릭하여 계속 진행하세요.');
  end;
end;

// 키움 API 페이지에서 다음 버튼 클릭 시
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  
  if (CurPageID = KiwoomAPIPage.ID) and NeedsKiwoomAPI then
  begin
    if MsgBox('키움 OpenAPI+ 다운로드 페이지를 여시겠습니까?' + #13#10 + #13#10 +
              '다운로드 및 설치 후 이 설치를 계속 진행하세요.', 
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      DownloadKiwoomAPI;
      
      MsgBox('키움 OpenAPI+ 설치를 완료한 후:' + #13#10 + #13#10 +
             '1. 컴퓨터를 재부팅하세요 (권장)' + #13#10 +
             '2. 이 설치 프로그램으로 돌아와 "다음"을 클릭하세요.', 
             mbInformation, MB_OK);
    end;
  end;
end;

// 설치 준비
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  
  // 다시 한번 키움 API 확인
  if not IsKiwoomAPIInstalled then
  begin
    if MsgBox('키움 OpenAPI+가 여전히 설치되지 않은 것 같습니다.' + #13#10 + #13#10 +
              '프로그램은 설치되지만 실행 시 오류가 발생할 수 있습니다.' + #13#10 + #13#10 +
              '계속 진행하시겠습니까?', 
              mbConfirmation, MB_YESNO) = IDNO then
    begin
      Result := '설치가 취소되었습니다. 키움 OpenAPI+를 먼저 설치해주세요.';
    end;
  end;
end;

// 설치 완료 후
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    // Visual C++ Redistributable 설치 확인 (선택사항)
    if MsgBox('Visual C++ Redistributable을 설치하시겠습니까?' + #13#10 + #13#10 +
              '일부 시스템에서 프로그램 실행에 필요할 수 있습니다.' + #13#10 +
              '(이미 설치되어 있다면 건너뛰세요)', 
              mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
    begin
      ShellExec('', 'https://aka.ms/vs/17/release/vc_redist.x86.exe', '', '', SW_SHOW, ewNoWait, ResultCode);
    end;
  end;
end;

// 제거 시
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if MsgBox('거래 데이터와 설정을 유지하시겠습니까?' + #13#10 + #13#10 +
              '예: 데이터 보관 (재설치 시 복원 가능)' + #13#10 +
              '아니오: 모든 데이터 삭제', 
              mbConfirmation, MB_YESNO) = IDNO then
    begin
      // 데이터베이스 삭제
      DelTree(ExpandConstant('{app}\*.db'), False, True, False);
      DelTree(ExpandConstant('{app}\*.json'), False, True, False);
      DelTree(ExpandConstant('{app}\logs'), True, True, True);
    end;
  end;
end;
