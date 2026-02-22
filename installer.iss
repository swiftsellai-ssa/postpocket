[Setup]
AppName=PostPocket Pro
AppVersion=1.1.0
AppPublisher=Your Company Name
AppPublisherURL=https://github.com/swiftsellai-ssa/postpocket
DefaultDirName={autopf}\PostPocket
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputBaseFilename=PostPocket_Setup_v1.1.0
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourcePath}\dist\PostPocketPro\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\PostPocket"; Filename: "{app}\PostPocketPro.exe"
Name: "{autodesktop}\PostPocket"; Filename: "{app}\PostPocketPro.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PostPocketPro.exe"; Description: "{cm:LaunchProgram,PostPocket}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\.post_pocket"
