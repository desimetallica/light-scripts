Write-Host "Elaborating antenna data..."

$regex = "*DVM1*"
$file = ".\file.txt"

foreach($line in Get-Content $file) {
  $i = $i + 1
  if($line -like $regex) {
    $line | Out-File -FilePath .\out\$1.txt -encoding ascii -NoNewline
  }
}
