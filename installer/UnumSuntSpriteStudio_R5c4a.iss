#define MyAppName "Unum Sunt Sprite Studio"
#define MyAppVersion "R5c4a"
#define MyAppPublisher "GVibeDev"
#define MyAppExeName "UnumSuntSpriteStudio.exe"

[Setup]
AppId={{5F2F2D9A-6C3C-4D0A-A0D4-2D9EF36D5D42}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
VersionInfoVersion=5.4.1.0
DefaultDirName={userpf}\Unum Sunt Sprite Studio
DefaultGroupName=Unum Sunt Sprite Studio
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\release\installer
OutputBaseFilename=UnumSunt_Sprite_Studio_R5c4a_Setup_x64
SetupIconFile=..\assets\branding\app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UsePreviousAppDir=yes

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Types]
Name: "core"; Description: "Core · editor e pipeline senza runtime AI locale"
Name: "complete"; Description: "Completa R5c4a · Core + runtime AI + Wan Animate (Krea 2 da R5c5)"
Name: "custom"; Description: "Personalizzata"; Flags: iscustom

[Components]
Name: "core"; Description: "Sprite Studio Core"; Types: core complete custom; Flags: fixed
Name: "ai"; Description: "Runtime AI locale WanGP"; Types: complete custom
Name: "ai\animate"; Description: "Wan Animate 14B"; Types: complete custom

[Tasks]
Name: "desktopicon"; Description: "Crea collegamento sul Desktop"; GroupDescription: "Collegamenti:"; Flags: unchecked

[Files]
Source: "..\dist\UnumSuntSpriteStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: core

[Icons]
Name: "{group}\Unum Sunt Sprite Studio"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Unum Sunt Sprite Studio"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Avvia Unum Sunt Sprite Studio"; Flags: nowait postinstall skipifsilent

[Code]
var
  RuntimePathsPage: TInputDirWizardPage;
  RuntimeOptionsPage: TInputOptionWizardPage;
  RuntimeSummaryPage: TOutputMsgMemoWizardPage;

function Quote(const Value: String): String;
begin
  Result := '"' + Value + '"';
end;


function YesNo(const Value: Boolean): String;
begin
  if Value then
    Result := 'Sì'
  else
    Result := 'No';
end;

function AISelected: Boolean;
begin
  Result := WizardIsComponentSelected('ai');
end;

function AnimateSelected: Boolean;
begin
  Result := WizardIsComponentSelected('ai\animate');
end;

function SetupReportDir: String;
begin
  Result := ExpandConstant('{localappdata}\UnumSuntSpriteStudio\setup');
end;

function RuntimeRootValue: String;
begin
  Result := RuntimePathsPage.Values[0];
end;

function ModelRootValue: String;
begin
  Result := RuntimePathsPage.Values[1];
end;

procedure InitializeWizard;
begin
  RuntimePathsPage := CreateInputDirPage(
    wpSelectComponents,
    'Percorsi runtime AI',
    'Scegli dove mantenere runtime e modelli.',
    'Il Core non dipende da questi percorsi. Per i modelli scegli preferibilmente un disco con molto spazio libero.',
    False,
    ''
  );
  RuntimePathsPage.Add('Runtime AI:');
  RuntimePathsPage.Add('Modelli AI:');
  RuntimePathsPage.Values[0] := ExpandConstant('{localappdata}\UnumSuntSpriteStudio\ai_runtime');
  RuntimePathsPage.Values[1] := ExpandConstant('{localappdata}\UnumSuntSpriteStudio\ai_models');

  RuntimeOptionsPage := CreateInputOptionPage(
    RuntimePathsPage.ID,
    'Runtime AI esistente',
    'Riutilizzo e installazione',
    'Sprite Studio può adottare un WanGP già presente senza spostare o riscaricare nulla.',
    True,
    False
  );
  RuntimeOptionsPage.Add('Cerca e adotta automaticamente un runtime WanGP esistente');
  RuntimeOptionsPage.Add('Se non viene trovato un runtime valido, installa automaticamente il runtime gestito');
  RuntimeOptionsPage.Add('Accetto i termini Miniconda/Anaconda per l''eventuale installazione gestita');
  RuntimeOptionsPage.Values[0] := True;
  RuntimeOptionsPage.Values[1] := True;
  RuntimeOptionsPage.Values[2] := False;

  RuntimeSummaryPage := CreateOutputMsgMemoPage(
    RuntimeOptionsPage.ID,
    'Riepilogo runtime AI',
    'Operazioni previste',
    'Nessun download AI parte prima del preflight.',
    ''
  );
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if Assigned(RuntimePathsPage) and (PageID = RuntimePathsPage.ID) then
    Result := not AISelected
  else if Assigned(RuntimeOptionsPage) and (PageID = RuntimeOptionsPage.ID) then
    Result := not AISelected
  else if Assigned(RuntimeSummaryPage) and (PageID = RuntimeSummaryPage.ID) then
  begin
    Result := not AISelected;
    if not Result then
    begin
      RuntimeSummaryPage.RichEditViewer.RTFText := '';
      RuntimeSummaryPage.RichEditViewer.Lines.Text :=
        'Runtime: ' + RuntimeRootValue + #13#10 +
        'Modelli: ' + ModelRootValue + #13#10 +
        'Adozione runtime esistente: ' + YesNo(RuntimeOptionsPage.Values[0]) + #13#10 +
        'Fallback installazione gestita: ' + YesNo(RuntimeOptionsPage.Values[1]) + #13#10 +
        'Wan Animate: ' + YesNo(AnimateSelected) + #13#10 +
        'Krea 2: non installato dal Setup R5c4a; verrà completato in R5c5.';
    end;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if Assigned(RuntimeOptionsPage) and (CurPageID = RuntimeOptionsPage.ID) and AISelected then
  begin
    if RuntimeOptionsPage.Values[1] and (not RuntimeOptionsPage.Values[2]) then
    begin
      MsgBox('Per installare automaticamente Miniconda devi accettare i relativi termini. In alternativa disattiva il fallback di installazione gestita e usa solo un runtime esistente.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

function ExecAndWait(const Params: String; var ResultCode: Integer): Boolean;
begin
  Result := Exec(
    ExpandConstant('{app}\{#MyAppExeName}'),
    Params,
    ExpandConstant('{app}'),
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  );
end;

procedure RunAIRuntimeBootstrap;
var
  ExitCode: Integer;
  Params: String;
  PreflightReport: String;
  AdoptionReport: String;
  InstallReport: String;
  HealthReport: String;
  Adopted: Boolean;
begin
  if not AISelected then
    Exit;

  ForceDirectories(SetupReportDir);
  PreflightReport := SetupReportDir + '\runtime_preflight_R5c4a.json';
  AdoptionReport := SetupReportDir + '\runtime_adoption_R5c4a.json';
  InstallReport := SetupReportDir + '\runtime_install_R5c4a.json';
  HealthReport := SetupReportDir + '\runtime_health_R5c4a.json';

  Params := '--runtime-preflight ' + Quote(PreflightReport) +
            ' --runtime-root ' + Quote(RuntimeRootValue) +
            ' --model-root ' + Quote(ModelRootValue);
  if (not ExecAndWait(Params, ExitCode)) or (ExitCode = 2) then
  begin
    MsgBox('Il preflight del runtime AI non è stato superato. Il Core è installato correttamente; apri File → Gestione runtime AI per i dettagli. Report: ' + PreflightReport, mbError, MB_OK);
    Exit;
  end;

  Adopted := False;
  if RuntimeOptionsPage.Values[0] then
  begin
    Params := '--runtime-auto-adopt ' + Quote(AdoptionReport) +
              ' --runtime-root ' + Quote(RuntimeRootValue) +
              ' --model-root ' + Quote(ModelRootValue);
    if ExecAndWait(Params, ExitCode) and (ExitCode = 0) then
      Adopted := True;
  end;

  if (not Adopted) and RuntimeOptionsPage.Values[1] then
  begin
    Params := '--runtime-install ' + Quote(InstallReport) +
              ' --runtime-root ' + Quote(RuntimeRootValue) +
              ' --model-root ' + Quote(ModelRootValue) +
              ' --accept-anaconda-tos --skip-krea2';
    if not AnimateSelected then
      Params := Params + ' --skip-animate';

    if (not ExecAndWait(Params, ExitCode)) or (ExitCode <> 0) then
    begin
      MsgBox('Installazione del runtime AI non completata. Il Core rimane installato e funzionante. Puoi riprendere da File → Gestione runtime AI. Report: ' + InstallReport, mbError, MB_OK);
      Exit;
    end;
  end;

  Params := '--runtime-health ' + Quote(HealthReport) +
            ' --runtime-root ' + Quote(RuntimeRootValue) +
            ' --model-root ' + Quote(ModelRootValue);
  if (not ExecAndWait(Params, ExitCode)) or (ExitCode <> 0) then
  begin
    MsgBox('Il Core è installato, ma il runtime AI richiede attenzione. Apri File → Gestione runtime AI. Report: ' + HealthReport, mbInformation, MB_OK);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    RunAIRuntimeBootstrap;
end;
