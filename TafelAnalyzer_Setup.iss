; =========================
; 可修改的基础信息
; =========================
; 软件名称：安装向导标题、开始菜单名称、桌面快捷方式名称都会用到
#define MyAppName "TAFSQ"
; 软件版本号：会显示在安装包和“应用和功能”里
#define MyAppVersion "1.0.9"
; 发布者名称：会显示在安装信息里
#define MyAppPublisher "JXSQ"
; 主程序 EXE 文件名：必须和 dist\TafelAnalyzer 里的实际文件一致
#define MyAppExeName "TAFSQ.exe"
; 打包后的发布目录：安装包会把这里面的内容全部打进去
#define MyAppSourceDir "dist\TAFSQ"
; 安装包图标文件：Inno Setup 这里必须使用 .ico，不能直接用 .png
#define MyAppIconFile "icons\ico.ico"
; 安装后图标文件名（去掉路径前缀，复制到安装目录后就是纯文件名）
#define MyAppIconName "ico.ico"

[Setup]
; 安装包的唯一标识：已安装后不要随意改，否则会被当成另一个软件
AppId={{8D1A6A52-16CC-4C5D-BBC7-FE603E14C8D2}
; 安装包显示的软件名
AppName={#MyAppName}
; 安装包显示的软件版本
AppVersion={#MyAppVersion}
; 发布者
AppPublisher={#MyAppPublisher}
; 默认安装目录
DefaultDirName={autopf}\{#MyAppName}
; 开始菜单程序组名称
DefaultGroupName={#MyAppName}
; 允许用户选择“不创建快捷方式”
AllowNoIcons=yes
; 安装到 Program Files 通常需要管理员权限
PrivilegesRequired=admin
; 安装包输出目录
OutputDir=installer_output
; 安装包输出文件名（不含 .exe 后缀）
OutputBaseFilename=TAFSQ-1.0.9-setup
; 安装包自身显示的图标
SetupIconFile={#MyAppIconFile}
; 压缩方式，通常不用改
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; 仅允许 64 位兼容系统安装
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; 控制面板卸载列表中显示的图标
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
; 安装界面语言
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl"

[Tasks]
; 可选任务：创建桌面快捷方式
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
; 主程序及其依赖：把整个 dist\TafelAnalyzer 目录安装到 {app}
Source: "{#MyAppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; 额外安装图标文件，供快捷方式使用（放到 {app} 根目录）
Source: "{#MyAppIconFile}"; DestDir: "{app}"; DestName: "{#MyAppIconName}"; Flags: ignoreversion

[Icons]
; 开始菜单主程序快捷方式
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppIconName}"
; 开始菜单卸载入口
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
; 桌面快捷方式
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\{#MyAppIconName}"

[Run]
; 安装完成后可勾选立即启动软件
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
