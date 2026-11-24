<#
.SYNOPSIS
  Ghi cấu hình cho menu SAN NỀN trong AutoCAD (%APPDATA%\SanNen\sannen.cfg).

.DESCRIPTION
  Chỉ ghi MỘT file cấu hình UTF-8 (không BOM) gồm bốn dòng:
      python=<python.exe có cài sannen-core>
      cad=<thư mục chứa gói sannen_cad>
      lisp=<thư mục chứa sannen.lsp và sannen.dcl>
      lot=<thư mục lô hiện tại>          (bỏ trống được; chọn trong AutoCAD bằng lệnh SN_LOT)
  KHÔNG sửa registry, KHÔNG sửa profile AutoCAD, KHÔNG cài gì vào thư mục AutoCAD.

.PARAMETER Python
  Đường dẫn python.exe. Bỏ trống: tự tìm `python` đầu tiên trong PATH có `import sannen`.

.PARAMETER Lot
  Thư mục lô (có lot.yaml). Tùy chọn.

.EXAMPLE
  .\cad\cai_dat_cad.ps1 -Python C:\Python312\python.exe -Lot ..\projects\KDT-DaiThanh\lots\01-CGP
#>
param(
    [string]$Python = "",
    [string]$Lot = ""
)
$ErrorActionPreference = "Stop"

function Tim-Python {
    $ung = @()
    foreach ($c in (Get-Command python -All -ErrorAction SilentlyContinue)) {
        if ($c.Source -and $c.Source -notmatch "WindowsApps") { $ung += $c.Source }   # bỏ phần giả lập của Microsoft Store
    }
    foreach ($p in $ung) {
        & $p -c "import sannen" 2>$null
        if ($LASTEXITCODE -eq 0) { return $p }
    }
    return $null
}

$goc = Split-Path -Parent $MyInvocation.MyCommand.Path          # ...\cad
if ([string]::IsNullOrWhiteSpace($Python)) { $Python = Tim-Python }
if (-not $Python -or -not (Test-Path $Python)) {
    Write-Error "Không tìm thấy python có cài sannen-core. Chạy: cd core; pip install -e `".[dev]`" rồi chạy lại, hoặc truyền -Python <đường dẫn>."
}
& $Python -c "import sannen" 2>$null
if ($LASTEXITCODE -ne 0) { Write-Error "$Python chưa cài sannen-core (cd core; pip install -e `".[dev]`")." }

$lisp = Join-Path $goc "lisp"
foreach ($f in "sannen.lsp", "sannen.dcl") {
    if (-not (Test-Path (Join-Path $lisp $f))) { Write-Error "Thiếu $lisp\$f" }
}
if ($Lot) {
    $Lot = (Resolve-Path $Lot).Path
    if (-not (Test-Path (Join-Path $Lot "lot.yaml"))) { Write-Error "$Lot không có lot.yaml" }
}

$thuMuc = Join-Path $env:APPDATA "SanNen"
New-Item -ItemType Directory -Force $thuMuc | Out-Null
$cfg = Join-Path $thuMuc "sannen.cfg"
$noiDung = "python=$Python`ncad=$goc`nlisp=$lisp`nlot=$Lot`n"
[IO.File]::WriteAllText($cfg, $noiDung, (New-Object Text.UTF8Encoding($false)))

Write-Host "Đã ghi $cfg"
Write-Host $noiDung
Write-Host @"
CÁCH NẠP TRONG AUTOCAD 2022
  1. Gõ APPLOAD → Contents (Startup Suite) → Add → chọn $lisp\sannen.lsp
     (mỗi lần mở AutoCAD menu SAN NỀN tự được nạp). Nếu hỏi "Always load / Load once": chọn Always load.
  2. Hoặc nạp một lần:   (load "$($lisp -replace '\\','/')/sannen.lsp")
  3. Gõ SN_LOT để chọn lô (nếu chưa khai -Lot), rồi gõ SN hoặc dùng menu thả xuống "SAN NỀN".
Kiểm tra nhanh:  SN_TRANGTHAI
"@
