Write-Output "hammer.rip Automated Windows Server Installation Script";
if ( $args.Length -ne 3 ) {
   Write-Output "Usage: <gameserver_git_repo_url> <webserver_register_access_code> <server_flags>";
   exit 0;
}

function Append-SystemPath {
    param (
        $NewPath
    )
    $CurrentPATH = ([Environment]::GetEnvironmentVariable("PATH")).Split(";")
    $NewPATH = ($CurrentPATH + $newPath) -Join ";"
    [Environment]::SetEnvironmentVariable("PATH", $NewPath, [EnvironmentVariableTarget]::Machine)  
}

$baseDomain = "hammer.rip";

$python312DownloadUrl = "https://www.python.org/ftp/python/3.12.5/python-3.12.5-amd64.exe";
$git246DownloadUrl = "https://github.com/git-for-windows/git/releases/download/v2.46.0.windows.1/Git-2.46.0-64-bit.exe";
$vsBuildToolsDownloadUrl = "https://aka.ms/vs/17/release/vs_BuildTools.exe";

$python312DownloadPath = "$env:USERPROFILE\Downloads\python-3.12.5-amd64.exe";
$git246DownloadPath = "$env:USERPROFILE\Downloads\Git-2.46.0-64-bit.exe";
$vsBuildToolsDownloadPath = "$env:USERPROFILE\Downloads\vs_buildtools.exe";

$pythonInstallationDirectory = "$env:USERPROFILE\AppData\Local\Programs\Python\Python312";
$pythonExecutablePath = "$($pythonInstallationDirectory)\python.exe";
$gitExecutablePath = "C:\Program Files\Git\bin\git.exe";

$gameServerInstallationDirectory = "$env:USERPROFILE\Documents\hammer-gameserver";
$gameServerGitRepoURL = $args[0];

if (!(Test-Path $python312DownloadPath)) {
    Write-Output "Downloading Python from $($python312DownloadUrl) to $($python312DownloadPath)";
    Invoke-WebRequest $python312DownloadUrl -OutFile $python312DownloadPath;
} else {
    Write-Output "Python Installer ($($python312DownloadPath)) already exists, skipping download";
}
if (!(Test-Path $git246DownloadPath)) {
    Write-Output "Downloading Git from $($git246DownloadUrl) to $($git246DownloadPath)";
    Invoke-WebRequest $git246DownloadUrl -OutFile $git246DownloadPath;
} else {
    Write-Output "Git Installer ($($git246DownloadPath)) already exists, skipping download";
}
if (!(Test-Path $vsBuildToolsDownloadPath)) {
    Write-Output "Downloading VS Build Tools from $($vsBuildToolsDownloadUrl) to $($vsBuildToolsDownloadPath)";
    Invoke-WebRequest $vsBuildToolsDownloadUrl -OutFile $vsBuildToolsDownloadPath;
} else {
    Write-Output "VS Build Tools installer ($($vsBuildToolsDownloadPath)) already exists, skipping download";
}

Write-Output "Running Python Installer ($($python312DownloadPath))";
if (!(Test-Path $pythonExecutablePath)) {
    Start-Process -FilePath $python312DownloadPath -ArgumentList "/quiet" -Wait;
    if (!(Test-Path $pythonExecutablePath)) {
        Write-Error "Python executable not found at expected path of $($pythonExecutablePath), exiting";
        exit 1;
    }
    Append-SystemPath -NewPath $pythonInstallationDirectory

} else {
    Write-Output "Python executable ($($pythonExecutablePath)) already exists, skipping installation";
}
if (!(Test-Path $gitExecutablePath)) {
    Write-Output "Running Git Installer ($($git246DownloadPath))";
    Start-Process -FilePath $git246DownloadPath -ArgumentList "/SP- /VERYSILENT /SUPPRESSMSGBOXES /NORESTART" -Wait;
    if (!(Test-Path $gitExecutablePath)) {
        Write-Error "Git executable not found at expected path of $($gitExecutablePath), exiting";
        exit 1;
    }
} else {
    Write-Output "Git executable ($($gitExecutablePath)) already exists, skipping installation";
}

Write-Output "Running VS Build Tools Installer ($($vsBuildToolsDownloadPath))";
Start-Process -FilePath $vsBuildToolsDownloadPath -ArgumentList "--passive --norestart --add Microsoft.VisualStudio.Component.VC.Tools.x86.x64 --add Microsoft.VisualStudio.Component.Windows11SDK.22621" -Wait;

Write-Output "Creating Firewall rules";
New-NetFirewallRule -DisplayName "RCCService" -Direction Inbound -LocalPort 53640-53900 -Protocol UDP -Action Allow
New-NetFirewallRule -DisplayName "Hammer Gameserver Internal" -Direction Inbound -LocalPort 3000 -Protocol TCP -Action Allow

Write-Output "Updating registry";
New-Item -Path "HKLM:\SOFTWARE\WOW6432Node\Roblox Corporation\Roblox" -Force;
Set-ItemProperty -Path "HKLM:\SOFTWARE\WOW6432Node\Roblox Corporation\Roblox" -Name "SettingsKey" -Type String -Value "Cb7GP5SUewA455AHovR3";
Set-ItemProperty -Path "HKLM:\SOFTWARE\WOW6432Node\Roblox Corporation\Roblox" -Name "AccessKey" -Type String -Value "Unset";

Write-Output "Disabling IPv6";
Disable-NetAdapterBinding -Name "*" -ComponentID ms_tcpip6

Write-Output "Cloning Gameserver Git Repository";
Start-Process -FilePath $gitExecutablePath -ArgumentList "clone $($gameServerGitRepoURL) $($gameServerInstallationDirectory)" -Wait;
Copy-Item "$($gameServerInstallationDirectory)\server_config.py.example" -Destination "$($gameServerInstallationDirectory)\server_config.py";

Write-Output "Installing python dependencies";
Start-Process -FilePath $pythonExecutablePath -ArgumentList "-m pip install -r $($gameServerInstallationDirectory)\requirements.txt" -Wait;

Write-Output "Register Gameserver with Master webserver";
cd $gameServerInstallationDirectory
Start-Process -FilePath $pythonExecutablePath -ArgumentList "$($gameServerInstallationDirectory)\server_registration.py $($args[1]) $($args[2])" -Wait;
if ( !(Test-Path -Path "HKLM:\SOFTWARE\HammerArbiter") ) {
    Write-Output "Server registration failed, exiting";
    exit 2;
}
if ( (Get-ItemPropertyValue -Path "HKLM:\Software\HammerArbiter" -Name "IsRegistered") -ne "True" ) {
    Write-Output "Server registration failed, exiting";
    exit 3;
}
Write-Output "Server registered successfully";

Write-Output "Starting Gameserver";
Start-Process -FilePath $pythonExecutablePath -ArgumentList "$($gameServerInstallationDirectory)\main.py";