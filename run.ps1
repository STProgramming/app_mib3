param([string]$JavaPath, [switch]$Console, [string]$LogDirectory)
$ErrorActionPreference = 'Stop'
$taskJar = Join-Path $PSScriptRoot 'hello-gte.jar'
if (-not (Test-Path -LiteralPath $taskJar)) {
    $taskJar = Join-Path $PSScriptRoot 'dist\hello-gte\hello-gte.jar'
}
if (-not (Test-Path -LiteralPath $taskJar)) { throw 'Eseguire prima: python tools/build.py' }
$taskJava = $JavaPath
if (-not $taskJava -and $env:JAVA_HOME) { $taskJava = Join-Path $env:JAVA_HOME 'bin\java.exe' }
if (-not $taskJava) {
    $taskJavaCommand = Get-Command java -ErrorAction SilentlyContinue
    if ($taskJavaCommand) { $taskJava = $taskJavaCommand.Source }
}
if (-not $taskJava) { $taskJava = 'C:\Program Files\Android\Android Studio\jbr\bin\java.exe' }
if (-not (Test-Path -LiteralPath $taskJava)) { throw 'Specificare -JavaPath percorso\java.exe (Java 8+)' }
$taskArguments = @('-jar', $taskJar, '--demo')
if (-not $LogDirectory) { $LogDirectory = Join-Path $PSScriptRoot 'logs' }
$taskArguments += @('--log-dir', $LogDirectory)
if (-not $Console) { $taskArguments += '--window' }
& $taskJava @taskArguments
exit $LASTEXITCODE
