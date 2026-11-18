$base = "https://hakimkononi.onrender.com"

$scenarios = @(
    @{
        name  = "SCENARIO 1 - Land TRANSACTION (English)"
        story = "I want to buy a plot in Kiambu. The seller showed me title deed KIAMBU/001/234. Is this land clean?"
        lang  = "en"
    },
    @{
        name  = "SCENARIO 2 - Land DISPUTE (English)"
        story = "My neighbour has grabbed my land and built a fence on my property. I have a title deed."
        lang  = "en"
    },
    @{
        name  = "SCENARIO 3 - Land TRANSACTION (Swahili)"
        story = "Nataka kununua kiwanja Nairobi. Muuzaji ananipa hati nambari NAIROBI/BLOCK24/123. Ardhi iko safi?"
        lang  = "sw"
    },
    @{
        name  = "SCENARIO 4 - Mode switch (transaction->dispute)"
        story = "I already paid the deposit but the seller has disappeared with my money and won't give me the title deed."
        lang  = "en"
    },
    @{
        name  = "SCENARIO 5 - Employment (non-land)"
        story = "My employer fired me without notice after 3 years and refused to pay my salary."
        lang  = "en"
    },
    @{
        name  = "SCENARIO 6 - Landlord DISPUTE (not a purchase)"
        story = "My landlord locked me out of my house without notice and kept my belongings."
        lang  = "en"
    }
)

foreach ($s in $scenarios) {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host $s.name
    Write-Host "============================================================"

    # POST /api/submit/
    $body = @{ story = $s.story; lang = $s.lang } | ConvertTo-Json -Compress
    try {
        $submitResp = Invoke-RestMethod -Uri "$base/api/submit/" `
            -Method Post `
            -ContentType "application/json" `
            -Body $body `
            -ErrorAction Stop
        $jobId = $submitResp.job_id
        Write-Host "Submit HTTP OK  job_id: $jobId"
    } catch {
        Write-Host "Submit FAILED: $($_.Exception.Message)"
        if ($_.Exception.Response) {
            $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
            Write-Host "Response body: $($reader.ReadToEnd())"
        }
        continue
    }

    # Poll /api/status/{job_id}/ every 5 s, max 90 s
    $maxWait  = 90
    $elapsed  = 0
    $interval = 5
    $result   = $null

    while ($elapsed -lt $maxWait) {
        Start-Sleep -Seconds $interval
        $elapsed += $interval
        try {
            $statusResp = Invoke-RestMethod -Uri "$base/api/status/$jobId/" `
                -Method Get `
                -ErrorAction Stop
        } catch {
            Write-Host "  Poll error at ${elapsed}s: $($_.Exception.Message)"
            continue
        }

        $st = $statusResp.status
        Write-Host "  [${elapsed}s] status=$st"

        if ($st -eq "done" -or $st -eq "error") {
            $result = $statusResp
            break
        }
    }

    if ($null -eq $result) {
        Write-Host "FINAL STATUS: TIMEOUT after ${maxWait}s"
        continue
    }

    Write-Host "FINAL STATUS: $($result.status)"

    # land_subtype
    $ls = $result.land_subtype
    if ($null -eq $ls) { $ls = "(null/missing)" }
    Write-Host "land_subtype: '$ls'"

    # Check the 4 answer boxes
    $boxes = @("sheria_inasema", "hatua_za_kuchukua", "tafsiri_rahisi", "rasilimali")
    foreach ($box in $boxes) {
        $val = $result.$box
        if ($null -eq $val) { $val = "" }
        $empty = [string]::IsNullOrWhiteSpace($val)
        $status = if ($empty) { "[EMPTY]" } else { "[NON-EMPTY]" }
        Write-Host "  $box : $status (len=$($val.Length))"
    }

    # First N chars of key fields
    $sheria = if ($null -ne $result.sheria_inasema) { $result.sheria_inasema } else { "" }
    $tafsiri = if ($null -ne $result.tafsiri_rahisi) { $result.tafsiri_rahisi } else { "" }
    Write-Host "sheria_inasema first 120: '$($sheria.Substring(0, [Math]::Min(120, $sheria.Length)))'"
    Write-Host "tafsiri_rahisi first  80: '$($tafsiri.Substring(0, [Math]::Min(80,  $tafsiri.Length)))'"

    if ($result.error) { Write-Host "ERROR FIELD: $($result.error)" }
}

Write-Host ""
Write-Host "=== ALL SCENARIOS COMPLETE ==="
