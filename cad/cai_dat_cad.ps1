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

# ---- Tự động đăng ký vào AutoCAD Startup Suite, Applications (.NET autoload) và acaddoc.lsp ----
$sannenLsp = Join-Path $lisp "sannen.lsp"
$binDir = Join-Path $goc "dotnet\bin"
$drawDll = Join-Path $binDir "SanNenDraw.dll"
$palDll = Join-Path $binDir "SanNenPalette.dll"

# 1. Đăng ký vào mọi phiên bản/profile AutoCAD trong HKCU
$acadKeys = Get-ChildItem -Path "HKCU:\Software\Autodesk\AutoCAD" -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.PSChildName -match "^ACAD-" }
foreach ($ak in $acadKeys) {
    $akPath = $ak.PSPath
    # 1a. Đăng ký .NET Demand-Load Applications (LOADCTRLS = 2: tự nạp ngay khi mở AutoCAD)
    $appsKey = Join-Path $akPath "Applications"
    if (Test-Path $drawDll) {
        $kDraw = Join-Path $appsKey "SanNenDraw"
        New-Item -Path $kDraw -Force | Out-Null
        Set-ItemProperty -Path $kDraw -Name "DESCRIPTION" -Value "SAN NEN DrawEngine & Commands (.NET)"
        Set-ItemProperty -Path $kDraw -Name "LOADCTRLS" -Value 2 -Type DWord
        Set-ItemProperty -Path $kDraw -Name "LOADER" -Value $drawDll
        Set-ItemProperty -Path $kDraw -Name "MANAGED" -Value 1 -Type DWord
    }
    if (Test-Path $palDll) {
        $kPal = Join-Path $appsKey "SanNenPalette"
        New-Item -Path $kPal -Force | Out-Null
        Set-ItemProperty -Path $kPal -Name "DESCRIPTION" -Value "SAN NEN Dockable Palette (.NET)"
        Set-ItemProperty -Path $kPal -Name "LOADCTRLS" -Value 2 -Type DWord
        Set-ItemProperty -Path $kPal -Name "LOADER" -Value $palDll
        Set-ItemProperty -Path $kPal -Name "MANAGED" -Value 1 -Type DWord
    }

    # 1b. Đăng ký sannen.lsp vào Appload Startup Suite và thêm TRUSTEDPATHS trong từng Profile
    $profRoot = Join-Path $akPath "Profiles"
    if (Test-Path $profRoot) {
        foreach ($pf in (Get-ChildItem -Path $profRoot -ErrorAction SilentlyContinue)) {
            $stKey = Join-Path $pf.PSPath "Dialogs\Appload\Startup"
            New-Item -Path $stKey -Force | Out-Null
            $props = Get-ItemProperty -Path $stKey -ErrorAction SilentlyContinue
            $n = if ($props -and $null -ne $props.NumStartup) { [int]$props.NumStartup } else { 0 }
            $daCo = $false
            for ($i = 1; $i -le $n; $i++) {
                $v = $props."${i}Startup"
                if ($v -and ($v -ieq $sannenLsp -or $v -match "sannen\.lsp$")) {
                    Set-ItemProperty -Path $stKey -Name "${i}Startup" -Value $sannenLsp
                    $daCo = $true
                }
            }
            if (-not $daCo) {
                $n++
                Set-ItemProperty -Path $stKey -Name "${n}Startup" -Value $sannenLsp
                Set-ItemProperty -Path $stKey -Name "NumStartup" -Value $n -Type DWord
            }

            # Thêm thư mục lisp và dotnet\bin vào TRUSTEDPATHS để AutoCAD không hỏi hộp thoại bảo mật mỗi lần mở
            $varKey = Join-Path $pf.PSPath "Variables"
            if (Test-Path $varKey) {
                $tpObj = Get-ItemProperty -Path $varKey -Name "TRUSTEDPATHS" -ErrorAction SilentlyContinue
                $tp = if ($tpObj -and $tpObj.TRUSTEDPATHS) { [string]$tpObj.TRUSTEDPATHS } else { "" }
                foreach ($dir in @($lisp, $binDir, "$thuMuc\bin")) {
                    if ($tp -notlike "*$dir*") {
                        $tp = if ([string]::IsNullOrWhiteSpace($tp)) { $dir } else { "$tp;$dir" }
                    }
                }
                Set-ItemProperty -Path $varKey -Name "TRUSTEDPATHS" -Value $tp
            }
        }
    }
}

# 2. Ghi vào acaddoc.lsp trong thư mục Support của AutoCAD (tự chạy mỗi khi mở bản vẽ mới/cũ)
$supDirs = Get-ChildItem -Path "$env:APPDATA\Autodesk" -Recurse -Directory -Filter "Support" -ErrorAction SilentlyContinue
$lenhLoad = "(if (findfile `"$($sannenLsp -replace '\\','/')`") (load `"$($sannenLsp -replace '\\','/')`"))"
foreach ($sd in $supDirs) {
    if ($sd.FullName -match "AutoCAD") {
        $acaddoc = Join-Path $sd.FullName "acaddoc.lsp"
        $cu = if (Test-Path $acaddoc) { [IO.File]::ReadAllText($acaddoc, [Text.Encoding]::UTF8) } else { "" }
        if ($cu -notmatch "sannen\.lsp") {
            $moi = ($cu.TrimEnd() + "`n;; Tự động nạp công cụ SAN NỀN khi mở AutoCAD`n" + $lenhLoad + "`n").TrimStart()
            [IO.File]::WriteAllText($acaddoc, $moi, (New-Object Text.UTF8Encoding($false)))
            Write-Host "Đã đăng ký tự động nạp trong: $acaddoc"
        }
    }
}

Write-Host "Đã cài đặt tự động khởi động SAN NỀN (Menu + LISP + .NET Palette + DrawEngine) mỗi khi mở AutoCAD!"
