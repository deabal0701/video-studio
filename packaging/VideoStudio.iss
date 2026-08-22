; Inno Setup — Video Studio 설치기 (07_desktop "단일 실행파일 — 패키징").
;
;   1) .\.qt-venv\Scripts\pyinstaller.exe packaging\VideoStudio.spec --noconfirm
;   2) .\packaging\collect-runtime.ps1
;   3) .\packaging\collect-licenses.ps1          ← 고지 없이 배포 금지 (R8)
;   4) ISCC.exe packaging\VideoStudio.iss        → packaging\out\VideoStudioSetup.exe
;
; 또는 한 번에:  .\packaging\build-installer.ps1
;
; PrivilegesRequired=lowest + {localappdata}\Programs — **관리자 권한 불요** (VS Code 방식).
; 담당자 PC 에 admin 이 없어도 설치되고, engine\assets 에 소재를 받을 수 있다.
; 데이터(projects·out·캐시)는 설치 폴더가 아니라 %LOCALAPPDATA%\VideoStudio\ 로 간다
; — 제거·재설치해도 사용자 파일이 남는다 (파일이 SSOT).

#define AppName "Video Studio"
#define AppVer "0.5.0"
#define AppExe "VideoStudio.exe"

[Setup]
AppId={{8E5C1B54-2C7D-4E9A-9E1F-0D3A6B7C8D90}
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher=Video Studio
DefaultDirName={localappdata}\Programs\VideoStudio
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=out
OutputBaseFilename=VideoStudioSetup
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
; 설치 마법사에 제3자 고지를 띄운다 (LGPL "prominent notice" 요건 — NOTICE.md 참조)
InfoBeforeFile=NOTICE.md
; ── 코드 서명 (5-8 · R8) ────────────────────────────────────────────────────
; 서명이 없으면 담당자 PC 에서 SmartScreen 이 실행을 차단한다. 인증서를 받으면
; 아래 두 줄의 주석을 풀고 ISCC 에 /S 파라미터로 서명 도구를 넘긴다:
;   SignTool=vsstudio
;   SignedUninstaller=yes
; 예:  ISCC.exe /Ssigntool="signtool.exe sign /f cert.pfx /p PASS /fd sha256 /tr <TSA> /td sha256 $f" packaging\VideoStudio.iss

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Files]
; 동결본 + 런타임 + 엔진 + licenses\ + NOTICE.md — collect-* 가 만든 dist\VideoStudio 통째로
Source: "..\dist\VideoStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; 담당자용 사용 안내 — 시작 메뉴에서 바로 열 수 있게
Source: "사용안내.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\사용 안내"; Filename: "{app}\사용안내.md"
Name: "{group}\오픈소스 고지"; Filename: "{app}\NOTICE.md"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 바로가기 만들기"; GroupDescription: "추가 작업:"

[Run]
Filename: "{app}\{#AppExe}"; Description: "{#AppName} 실행"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 설치 후 생긴 것만 지운다 — 사용자 데이터(%LOCALAPPDATA%\VideoStudio)는 건드리지 않는다
Type: filesandordirs; Name: "{app}\engine\node_modules\.cache"
