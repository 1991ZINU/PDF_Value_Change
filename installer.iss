[Setup]
AppName=PDF_Value_Change
AppVersion=1.0.0
DefaultDirName={pf}\PDF_Value_Change
DefaultGroupName=PDF_Value_Change
OutputDir=output
OutputBaseFilename=PDF_Value_Change_Setup
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\PDF_Value_Change.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\PDF_Value_Change"; Filename: "{app}\PDF_Value_Change.exe"
Name: "{commondesktop}\PDF_Value_Change"; Filename: "{app}\PDF_Value_Change.exe"

[Run]
Filename: "{app}\PDF_Value_Change.exe"; Description: "프로그램 실행"; Flags: nowait postinstall skipifsilent