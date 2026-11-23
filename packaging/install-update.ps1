param(
    [Parameter(Mandatory = $true)][string]$Source,
    [Parameter(Mandatory = $true)][string]$Target,
    [int]$ParentProcessId,
    [switch]$Legacy,
    [string]$RestoreGui = 'user'
)

$ErrorActionPreference = 'Stop'
$backup = $null
$stage = $null
$lock = $null
$newProcess = $null
$ready = $null
$installed = $false
$ownsTarget = $false
$managedWorkspace = $false

function Inside([string]$Path, [string]$Directory) {
    return $Path.Equals($Directory, [StringComparison]::OrdinalIgnoreCase) -or
        $Path.StartsWith($Directory.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)
}

try {
    $sourceItem = Get-Item -LiteralPath $Source
    $targetItem = Get-Item -LiteralPath $Target
    $legacyExe = 'LixAssistantLimbusCompany.exe'
    $expectedExe = if ($Legacy) { $legacyExe } else { 'LALC.exe' }
    if (!$sourceItem.PSIsContainer -or !$targetItem.PSIsContainer -or !$targetItem.Parent -or
        (Inside $sourceItem.FullName $targetItem.FullName) -or (Inside $targetItem.FullName $sourceItem.FullName)) {
        throw 'Invalid source or installation directory.'
    }
    $Source = $sourceItem.FullName
    $Target = $targetItem.FullName
    $parent = $targetItem.Parent.FullName
    Set-Location -LiteralPath $parent
    $work = Join-Path $env:LOCALAPPDATA 'LALC\work'
    $scriptDirectory = Get-Item -LiteralPath $PSScriptRoot
    $managedWorkspace = !$Legacy -and $sourceItem.Name -ceq 'LALC' -and
        $sourceItem.Parent.FullName -eq $scriptDirectory.FullName -and $scriptDirectory.Parent.FullName -eq $work -and
        $scriptDirectory.Name -match '^framework-update-[0-9a-f-]{36}$' -and
        !($scriptDirectory.Attributes -band [IO.FileAttributes]::ReparsePoint)
    $dataRoots = @(Join-Path $env:LOCALAPPDATA 'LALC')
    $documents = [Environment]::GetFolderPath('MyDocuments', 'DoNotVerify')
    if ($documents) { $dataRoots += Join-Path $documents 'LALC' }
    foreach ($dataRoot in $dataRoots) {
        if ((Inside $dataRoot $Target) -or (Inside $Target $dataRoot)) { throw 'The installation overlaps a user data directory.' }
    }
    for ($item = $targetItem; $item; $item = $item.Parent) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Installations through directory links require a manual update.' }
    }
    $lock = [IO.FileStream]::new((Join-Path $parent ('.' + $targetItem.Name + '.update.lock')), [IO.FileMode]::OpenOrCreate,
        [IO.FileAccess]::ReadWrite, [IO.FileShare]::None, 1, [IO.FileOptions]::DeleteOnClose)
    $hasBuildInfo = Test-Path -LiteralPath (Join-Path $Target 'build-info.json') -PathType Leaf
    if (!(Test-Path -LiteralPath (Join-Path $Target $expectedExe) -PathType Leaf) -or
        ($Legacy -and $hasBuildInfo) -or (!$Legacy -and !$hasBuildInfo)) {
        throw 'The selected directory is not the expected LALC installation.'
    }
    foreach ($required in @('LALC.exe', 'LALC-console.exe', 'build-info.json', 'install-update.ps1')) {
        if (!(Test-Path -LiteralPath (Join-Path $Source $required) -PathType Leaf)) { throw 'The new package is incomplete.' }
    }
    $build = Get-Content -LiteralPath (Join-Path $Source 'build-info.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($build.version -notmatch '^\d+\.\d+\.\d+$' -or !(Test-Path -LiteralPath (Join-Path $Source '_internal') -PathType Container)) {
        throw 'The new package is missing a framework version or runtime.'
    }
    $stage = Join-Path $parent ('.lalc-update-' + [guid]::NewGuid().ToString('N'))
    Copy-Item -LiteralPath $Source -Destination $stage -Recurse
    $bootstrap = Join-Path $stage 'update_to.bat'
    if (Test-Path -LiteralPath $bootstrap) { Remove-Item -LiteralPath $bootstrap }
    if ($Legacy -or (Test-Path -LiteralPath (Join-Path $Target $legacyExe) -PathType Leaf)) {
        [IO.File]::Copy((Join-Path $stage 'LALC.exe'), (Join-Path $stage $legacyExe))
    }

    if ($ParentProcessId) {
        $oldProcess = Get-Process -Id $ParentProcessId -ErrorAction SilentlyContinue
        if ($oldProcess -and !$oldProcess.WaitForExit(60000)) { throw 'The running application did not exit.' }
    }
    if ($Legacy) {
        $names = @('LixAssistantLimbusCompany', 'lalc_frontend')
        $oldProcesses = Get-Process -Name $names -ErrorAction SilentlyContinue | Where-Object { $_.Path -and (Inside $_.Path $Target) }
        foreach ($oldProcess in $oldProcesses) {
            if (!$oldProcess.WaitForExit(30000)) { throw 'The old application did not exit.' }
        }
    }

    $backup = Join-Path $parent ($targetItem.Name + '.backup-' + [guid]::NewGuid().ToString('N'))
    [IO.Directory]::Move($Target, $backup)
    $ownsTarget = $true
    [IO.Directory]::Move($stage, $Target)
    $installed = $true
    $application = Join-Path $Target 'LALC.exe'
    $nonce = [guid]::NewGuid().ToString('N')
    $ready = [Threading.EventWaitHandle]::new($false, [Threading.EventResetMode]::ManualReset, "Local\LALC-update-$nonce")
    $administrator = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
    $startup = @{ FilePath = $application; WorkingDirectory = $Target; ArgumentList = "--restore-gui=$RestoreGui --update-ready=$nonce"; PassThru = $true }
    if (!$administrator.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { $startup.Verb = 'RunAs' }
    $newProcess = Start-Process @startup
    $deadline = [DateTime]::UtcNow.AddSeconds(45)
    while (!$ready.WaitOne(250)) {
        if ($newProcess.HasExited) { throw 'The new application exited before opening.' }
        if ([DateTime]::UtcNow -ge $deadline) { throw 'The new application did not finish starting.' }
    }
    Write-Host "Update completed. Previous installation: $backup"
} catch {
    Write-Host "Update failed. $($_.Exception.Message)"
    if ($ownsTarget) {
        try {
            if ($newProcess -and !$newProcess.HasExited) {
                $newProcess.Kill()
                if (!$newProcess.WaitForExit(10000)) { throw 'The updated application is still running.' }
            }
            if ($installed) { [IO.Directory]::Move($Target, $stage) }
            [IO.Directory]::Move($backup, $Target)
            Write-Host 'The previous installation has been restored.'
        } catch {
            Write-Host "Automatic recovery failed. The previous installation is available at: $backup"
        }
    }
    if ([Environment]::UserInteractive -and ![Console]::IsInputRedirected) { Read-Host 'Press Enter to close' }
    exit 1
} finally {
    if ($ready) { $ready.Dispose() }
    if ($lock) { $lock.Dispose() }
    if ($stage -and (Test-Path -LiteralPath $stage)) { Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue }
    if ($managedWorkspace) { Remove-Item -LiteralPath $PSScriptRoot -Recurse -Force -ErrorAction SilentlyContinue }
}
