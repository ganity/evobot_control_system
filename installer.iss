[Setup]
AppName=EvoBot控制系统
AppVersion=1.0.0
AppPublisher=EvoBot Team
DefaultDirName={autopf}\EvoBot控制系统
DefaultGroupName=EvoBot控制系统
OutputDir=installer
OutputBaseFilename=EvoBot控制系统_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\EvoBot控制系统\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\EvoBot控制系统"; Filename: "{app}\EvoBot控制系统.exe"
Name: "{group}\{cm:UninstallProgram,EvoBot控制系统}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\EvoBot控制系统"; Filename: "{app}\EvoBot控制系统.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\EvoBot控制系统.exe"; Description: "{cm:LaunchProgram,EvoBot控制系统}"; Flags: nowait postinstall skipifsilent