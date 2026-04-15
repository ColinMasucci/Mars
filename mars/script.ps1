function Show-Tree($path, $indent = "") {
    Get-ChildItem $path | Where-Object { $_.Name -ne "mars-docs" } | ForEach-Object {
        "$indent$($_.Name)" | Out-File output.txt -Append
        if ($_.PSIsContainer) {
            Show-Tree $_.FullName ("$indent    ")
        }
    }
}

Show-Tree "."