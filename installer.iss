; Instalator VideoPixel (Inno Setup). Se compilează automat de build_exe.bat dacă Inno Setup e instalat.
#define AppName "VideoPixel"
#define AppVersion "1.2"

[Setup]
AppId={{6E1F0C58-2D0B-4C47-9B52-5C6F1B5A7A01}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=VideoPixel
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=dist
OutputBaseFilename=VideoPixel-Setup
SetupIconFile=assets\videopixel.ico
UninstallDisplayIcon={app}\VideoPixel.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Scurtătură pe Desktop"; GroupDescription: "Scurtături:"

[Files]
Source: "dist\VideoPixel\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\VideoPixel.exe"; IconFilename: "{app}\VideoPixel.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\VideoPixel.exe"; IconFilename: "{app}\VideoPixel.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\VideoPixel.exe"; Description: "Pornește VideoPixel"; Flags: nowait postinstall skipifsilent
