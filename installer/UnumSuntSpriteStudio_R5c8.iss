#define MyAppName "Unum Sunt Sprite Studio"
#define MyAppVersion "R5c8"
#define MyAppPublisher "GVibeDev"
#define MyAppExeName "UnumSuntSpriteStudio.exe"

[Setup]
AppId={{5F2F2D9A-6C3C-4D0A-A0D4-2D9EF36D5D42}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
VersionInfoCompany=GVibeDev
VersionInfoDescription=Unum Sunt Sprite Studio Windows Setup
VersionInfoProductName=Unum Sunt Sprite Studio
VersionInfoProductVersion=5.8.0.0
VersionInfoVersion=5.8.0.0
DefaultDirName={userpf}\Unum Sunt Sprite Studio
DefaultGroupName=Unum Sunt Sprite Studio
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\release\installer
OutputBaseFilename=UnumSunt_Sprite_Studio_R5c8_Setup_x64
SetupIconFile=..\assets\branding\app_icon.ico
WizardImageFile=..\assets\branding\installer_wizard.bmp
WizardSmallImageFile=..\assets\branding\installer_wizard_small.bmp
InfoBeforeFile=..\OPEN_SOURCE_LICENSE_NOTICE.txt
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UsePreviousAppDir=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Types]
Name: "core"; Description: "Core · editor and pipeline without local AI runtime"
Name: "complete"; Description: "Complete R5c8 · Core + AI runtime + Wan Animate + Krea 2 Turbo"
Name: "custom"; Description: "Custom"; Flags: iscustom

[Components]
Name: "core"; Description: "Sprite Studio Core"; Types: core complete custom; Flags: fixed
Name: "ai"; Description: "Local WanGP AI Runtime"; Types: complete custom
Name: "ai\animate"; Description: "Wan Animate 14B"; Types: complete custom
Name: "ai\krea2"; Description: "Krea 2 Turbo · WanGP Quanto BF16 INT8 (~13.5 GB)"; Types: complete custom

[Tasks]
Name: "desktopicon"; Description: "Create a Desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\UnumSuntSpriteStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: core

[Icons]
Name: "{group}\Unum Sunt Sprite Studio"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Unum Sunt Sprite Studio"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Unum Sunt Sprite Studio"; Flags: nowait postinstall skipifsilent

[Code]
var
  RuntimePathsPage: TInputDirWizardPage;
  RuntimeOptionsPage: TInputOptionWizardPage;
  RuntimeSummaryPage: TOutputMsgMemoWizardPage;
  UninstallChoicesDone: Boolean;
  RemoveRuntimeOnUninstall: Boolean;
  RemoveModelsOnUninstall: Boolean;
  RemoveUserDataOnUninstall: Boolean;

function Quote(const Value: String): String;
begin
  Result := '"' + Value + '"';
end;


function YesNo(const Value: Boolean): String;
begin
  if Value then
    Result := 'Yes'
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

function KreaSelected: Boolean;
begin
  Result := WizardIsComponentSelected('ai\krea2');
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
    'AI Runtime Paths',
    'Choose where the runtime and models will be stored.',
    'The Core does not depend on these paths. For models, prefer a drive with plenty of free disk space.',
    False,
    ''
  );
  RuntimePathsPage.Add('AI Runtime:');
  RuntimePathsPage.Add('AI Models:');
  RuntimePathsPage.Values[0] := GetPreviousData('RuntimeRoot', ExpandConstant('{localappdata}\UnumSuntSpriteStudio\ai_runtime'));
  RuntimePathsPage.Values[1] := GetPreviousData('ModelRoot', ExpandConstant('{localappdata}\UnumSuntSpriteStudio\ai_models'));

  RuntimeOptionsPage := CreateInputOptionPage(
    RuntimePathsPage.ID,
    'Existing AI Runtime',
    'Reuse and Installation',
    'Sprite Studio can adopt an existing WanGP installation without moving or downloading it again.',
    True,
    False
  );
  RuntimeOptionsPage.Add('Automatically detect and adopt an existing WanGP runtime');
  RuntimeOptionsPage.Add('If no valid runtime is found, automatically install the managed runtime');
  RuntimeOptionsPage.Add('I accept the Miniconda/Anaconda terms for an optional managed installation');
  RuntimeOptionsPage.Add('I accept the Krea 2 Community License + AUP if I install Krea 2 Turbo');
  RuntimeOptionsPage.Values[0] := GetPreviousData('AutoAdopt', '1') = '1';
  RuntimeOptionsPage.Values[1] := GetPreviousData('ManagedFallback', '1') = '1';
  { Legal acceptance is deliberately never persisted across installer runs. }
  RuntimeOptionsPage.Values[2] := False;
  RuntimeOptionsPage.Values[3] := False;

  RuntimeSummaryPage := CreateOutputMsgMemoPage(
    RuntimeOptionsPage.ID,
    'AI Runtime Summary',
    'Planned Operations',
    'No AI download starts before preflight.',
    ''
  );
end;

procedure RegisterPreviousData(PreviousDataKey: Integer);
begin
  SetPreviousData(PreviousDataKey, 'RuntimeRoot', RuntimeRootValue);
  SetPreviousData(PreviousDataKey, 'ModelRoot', ModelRootValue);
  if RuntimeOptionsPage.Values[0] then
    SetPreviousData(PreviousDataKey, 'AutoAdopt', '1')
  else
    SetPreviousData(PreviousDataKey, 'AutoAdopt', '0');
  if RuntimeOptionsPage.Values[1] then
    SetPreviousData(PreviousDataKey, 'ManagedFallback', '1')
  else
    SetPreviousData(PreviousDataKey, 'ManagedFallback', '0');
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
        'Models: ' + ModelRootValue + #13#10 +
        'Existing runtime adoption: ' + YesNo(RuntimeOptionsPage.Values[0]) + #13#10 +
        'Managed installation fallback: ' + YesNo(RuntimeOptionsPage.Values[1]) + #13#10 +
        'Wan Animate: ' + YesNo(AnimateSelected) + #13#10 +
        'Krea 2 Turbo: ' + YesNo(KreaSelected) + '.';
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
      MsgBox('To install Miniconda automatically, you must accept its terms. Otherwise disable the managed installation fallback and use only an existing runtime.', mbError, MB_OK);
      Result := False;
    end;
    if KreaSelected and (not RuntimeOptionsPage.Values[3]) then
    begin
      MsgBox('To install Krea 2 Turbo, you must accept the Krea 2 Community License and AUP.', mbError, MB_OK);
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
  PreflightReport := SetupReportDir + '\runtime_preflight_R5c8.json';
  AdoptionReport := SetupReportDir + '\runtime_adoption_R5c8.json';
  InstallReport := SetupReportDir + '\runtime_install_R5c8.json';
  HealthReport := SetupReportDir + '\runtime_health_R5c8.json';

  Params := '--runtime-preflight ' + Quote(PreflightReport) +
            ' --runtime-root ' + Quote(RuntimeRootValue) +
            ' --model-root ' + Quote(ModelRootValue);
  if (not ExecAndWait(Params, ExitCode)) or (ExitCode = 2) then
  begin
    MsgBox('AI runtime preflight did not pass. The Core is installed correctly; open File → AI Runtime Manager for details. Report: ' + PreflightReport, mbError, MB_OK);
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

  if Adopted and KreaSelected then
  begin
    MsgBox(
      'An external WanGP runtime was adopted. For safety, Setup does not modify external runtimes or models. ' +
      'Krea 2 will be reused automatically only if a compatible WanGP checkpoint is already present; ' +
      'otherwise install it later from File → AI Runtime Manager into a managed runtime.',
      mbInformation, MB_OK);
  end;

  if (not Adopted) and RuntimeOptionsPage.Values[1] then
  begin
    Params := '--runtime-install ' + Quote(InstallReport) +
              ' --runtime-root ' + Quote(RuntimeRootValue) +
              ' --model-root ' + Quote(ModelRootValue) +
              ' --accept-anaconda-tos';
    if KreaSelected then
      Params := Params + ' --accept-krea-license'
    else
      Params := Params + ' --skip-krea2';
    if not AnimateSelected then
      Params := Params + ' --skip-animate';

    if (not ExecAndWait(Params, ExitCode)) or (ExitCode <> 0) then
    begin
      MsgBox('AI runtime installation was not completed. The Core remains installed and functional. You can resume from File → AI Runtime Manager. Report: ' + InstallReport, mbError, MB_OK);
      Exit;
    end;
  end;

  Params := '--runtime-health ' + Quote(HealthReport) +
            ' --runtime-root ' + Quote(RuntimeRootValue) +
            ' --model-root ' + Quote(ModelRootValue);
  if (not ExecAndWait(Params, ExitCode)) or (ExitCode <> 0) then
  begin
    MsgBox('The Core is installed, but the AI runtime requires attention. Open File → AI Runtime Manager. Report: ' + HealthReport, mbInformation, MB_OK);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    RunAIRuntimeBootstrap;
end;

function InitializeUninstall: Boolean;
begin
  UninstallChoicesDone := False;
  RemoveRuntimeOnUninstall := False;
  RemoveModelsOnUninstall := False;
  RemoveUserDataOnUninstall := False;
  Result := True;
end;

procedure CollectUninstallChoices;
begin
  if UninstallChoicesDone then
    Exit;
  UninstallChoicesDone := True;

  RemoveRuntimeOnUninstall := MsgBox(
    'Do you also want to remove the AI runtime MANAGED by Sprite Studio?' + #13#10 + #13#10 +
    'Choose No to keep it for a future reinstall. External/adopted runtimes are never deleted.',
    mbConfirmation, MB_YESNO) = IDYES;

  RemoveModelsOnUninstall := MsgBox(
    'Do you also want to remove the managed AI checkpoints/models?' + #13#10 + #13#10 +
    'Choose No to avoid downloading Wan Animate/Krea 2 again in the future. Only the wangp_ckpts folder managed by Sprite Studio is affected.',
    mbConfirmation, MB_YESNO) = IDYES;

  RemoveUserDataOnUninstall := MsgBox(
    'Do you also want to delete Sprite Studio settings, profiles, logs, cache, and temporary jobs?' + #13#10 + #13#10 +
    'Projects saved by the user outside application folders are NOT removed.',
    mbConfirmation, MB_YESNO) = IDYES;
end;

procedure RunMaintenanceCleanup;
var
  ExitCode: Integer;
  Params: String;
  ReportPath: String;
begin
  if not (RemoveRuntimeOnUninstall or RemoveModelsOnUninstall or RemoveUserDataOnUninstall) then
    Exit;

  ReportPath := ExpandConstant('{tmp}\UnumSunt_R5c8_uninstall_cleanup.json');
  Params := '--maintenance-cleanup ' + Quote(ReportPath);
  if RemoveRuntimeOnUninstall then
    Params := Params + ' --remove-managed-runtime';
  if RemoveModelsOnUninstall then
    Params := Params + ' --remove-managed-models';
  if RemoveUserDataOnUninstall then
    Params := Params + ' --remove-user-data';

  if (not ExecAndWait(Params, ExitCode)) or (ExitCode <> 0) then
    MsgBox(
      'Optional runtime/model/data cleanup was not completed. The Core will still be uninstalled. Report: ' + ReportPath,
      mbInformation, MB_OK);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    CollectUninstallChoices;
    RunMaintenanceCleanup;
  end;
end;

