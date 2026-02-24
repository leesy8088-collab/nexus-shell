[Setup]
AppName=Nexus Shell
AppVersion=1.0.0
AppPublisher=Nexus Shell
DefaultDirName={autopf}\NexusShell
DefaultGroupName=Nexus Shell
UninstallDisplayIcon={app}\NexusShell.exe
OutputDir=dist
OutputBaseFilename=NexusShellSetup
Compression=lzma2
SolidCompression=yes
SetupIconFile=assets\icon.ico
PrivilegesRequired=lowest
DisableProgramGroupPage=yes

[Files]
Source: "dist\NexusShell\NexusShell.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\NexusShell\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\Nexus Shell"; Filename: "{app}\NexusShell.exe"
Name: "{group}\Nexus Shell"; Filename: "{app}\NexusShell.exe"
Name: "{group}\Nexus Shell 제거"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\NexusShell.exe"; Description: "Nexus Shell 실행"; Flags: nowait postinstall skipifsilent
