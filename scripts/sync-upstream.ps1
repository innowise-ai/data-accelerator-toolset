<#
    Brings a third party's skill into the catalog unchanged, or checks that the
    ones already here are still exactly what their index entries pin.

    An upstream artifact is an index entry with an 'upstream' object: the
    author's GitHub repository, a full commit SHA, the skill's directory in that
    repository, its licence, and optionally files to leave out. Its directory
    under artifacts/ is the author's files byte for byte, minus 'exclude', plus
    two files of ours: UPSTREAM.json (where the files came from) and LICENSE
    (only when the author's directory has none).

    -Id <id>   fetches the pinned commit and replaces artifacts/<id>/ with it.
               Every catalog rule the result could break is checked against the
               author's tree first; on any fault the directory is left alone and
               the author's file at fault is named.

    -Verify    the CI half. Compares the git blob ids of each upstream
               artifact's files in the catalog's HEAD with the author's tree at
               the pinned commit. Equal blob ids mean equal bytes, and no blob
               has to be downloaded to know it. This is also what catches the
               catalog's own .gitattributes normalising an author's line
               endings on commit: the blob id changes, and the fix is a -text
               attribute for that artifact, never an edit.

    The author's repository is fetched at catalog build time, never at install
    time; the installer reads source_path and ignores 'upstream' entirely. See
    the "Upstream artifacts" section of docs/authoring-artifacts.md.
#>
[CmdletBinding(DefaultParameterSetName = 'Sync')]
param(
    [Parameter(Mandatory, ParameterSetName = 'Sync')]
    [Parameter(ParameterSetName = 'Verify')]
    [string] $Id,

    [Parameter(Mandatory, ParameterSetName = 'Verify')]
    [switch] $Verify,

    # The catalog checkout. Defaults to the repository this script lives in;
    # the test suite points it at a fixture catalog.
    [string] $CatalogRoot = (Split-Path -Parent $PSScriptRoot),

    [string] $IndexPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ProvenanceFile = 'UPSTREAM.json'
$LicenseFile = 'LICENSE'
$SyncedBy = 'scripts/sync-upstream.ps1'

# Where an author's repository-wide licence usually lives, in the order tried.
# Compared case-insensitively.
$RootLicenseNames = @('LICENSE', 'LICENSE.md', 'LICENSE.txt', 'COPYING')

# The same check the validator makes, repeated here so a malformed pin is
# refused before anything is cloned with it.
$CommitPattern = '^[0-9a-f]{40}$'

$ValidatorPath = Join-Path $PSScriptRoot 'validate-catalog.ps1'

function New-PathTable {
    <#
        An ordered table keyed by path, case-sensitively. [ordered]@{} folds
        case, which would merge 'notes.md' and 'NOTES.md' into one entry - the
        exact collision the path rules exist to report.
    #>
    return [System.Collections.Specialized.OrderedDictionary]::new([StringComparer]::Ordinal)
}

function Invoke-UpstreamGit {
    <#
        Runs git and returns its standard output as strings. A non-zero exit
        throws with git's own standard error in the message, because "git
        failed" names neither the repository nor the reason.
    #>
    param(
        [Parameter(Mandatory)]
        [string[]] $Arguments,

        [Parameter(Mandatory)]
        [string] $WorkingDirectory
    )

    $output = & git -C $WorkingDirectory @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    $standardOutput = @($output | Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] } |
        ForEach-Object { [string]$_ })
    if ($exitCode -ne 0) {
        $standardError = @($output | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] } |
            ForEach-Object { $_.ToString() }) -join "`n"
        throw "git $($Arguments -join ' ') failed with exit code $exitCode. $standardError"
    }

    return $standardOutput
}

function Get-GitTree {
    <#
        Every blob under one path of a commit, keyed by its path relative to
        that path, with its mode and blob id. Trees only: nothing here needs a
        blob, so a --filter=blob:none clone answers it.

        -z because a path git would otherwise quote, or one holding a newline,
        must come back as the path it is.
    #>
    param(
        [Parameter(Mandatory)]
        [string] $Repository,

        [Parameter(Mandatory)]
        [string] $Treeish,

        [Parameter(Mandatory)]
        [AllowEmptyString()]
        [string] $Path,

        [switch] $NonRecursive
    )

    $arguments = @('--literal-pathspecs', 'ls-tree', '-z', '--full-tree')
    if (-not $NonRecursive) { $arguments += '-r' }
    $arguments += $Treeish
    if (-not [string]::IsNullOrEmpty($Path)) { $arguments += @('--', $Path) }

    $prefix = if ([string]::IsNullOrEmpty($Path)) { '' } else { "$Path/" }
    $entries = New-PathTable
    $raw = (Invoke-UpstreamGit -Arguments $arguments -WorkingDirectory $Repository) -join "`n"
    foreach ($record in $raw.Split([char]0)) {
        $record = $record.Trim("`n")
        if ([string]::IsNullOrEmpty($record)) { continue }

        $tab = $record.IndexOf("`t")
        $meta = $record.Substring(0, $tab).Split(' ')
        $fullPath = $record.Substring($tab + 1)
        if (-not $fullPath.StartsWith($prefix, [StringComparison]::Ordinal)) { continue }

        $entries[$fullPath.Substring($prefix.Length)] = [pscustomobject]@{
            Mode = $meta[0]
            Type = $meta[1]
            Blob = $meta[2]
        }
    }

    return $entries
}

function New-UpstreamClone {
    <#
        The author's repository at the pinned commit, with no blobs. The same
        transport shape as the installer's Copy-AcceleratorCatalog: a SHA cannot
        go to `clone --branch`, so the default ref is cloned at full depth and
        the commit resolved afterwards, fetched by id if no branch reaches it.
    #>
    param(
        [Parameter(Mandatory)]
        [string] $Repo,

        [Parameter(Mandatory)]
        [string] $Commit
    )

    $temp = [System.IO.Path]::GetTempPath()
    $directory = Join-Path $temp ('upstream-' + [guid]::NewGuid().ToString('N').Substring(0, 12))

    try {
        [void](Invoke-UpstreamGit -Arguments @('clone', '--quiet', '--filter=blob:none', '--no-checkout', '--', $Repo, $directory) `
            -WorkingDirectory $temp)
    } catch {
        throw "Could not clone $Repo. $($_.Exception.Message)"
    }

    # GIT_NO_LAZY_FETCH so asking whether the commit is here cannot itself go
    # and fetch it from the promisor remote, which would hide the answer.
    $previous = $env:GIT_NO_LAZY_FETCH
    $env:GIT_NO_LAZY_FETCH = '1'
    try {
        $present = $true
        try {
            [void](Invoke-UpstreamGit -Arguments @('rev-parse', '--verify', '--quiet', "$Commit^{commit}") -WorkingDirectory $directory)
        } catch {
            $present = $false
        }
    } finally {
        $env:GIT_NO_LAZY_FETCH = $previous
    }

    if (-not $present) {
        try {
            [void](Invoke-UpstreamGit -Arguments @('fetch', '--quiet', '--filter=blob:none', 'origin', $Commit) -WorkingDirectory $directory)
        } catch {
            Remove-UpstreamClone -Directory $directory
            throw "Commit $Commit is not in $Repo. Check the SHA in upstream.commit. $($_.Exception.Message)"
        }
    }

    return $directory
}

function Remove-UpstreamClone {
    param(
        [Parameter(Mandatory)]
        [string] $Directory
    )

    if (Test-Path -LiteralPath $Directory) {
        Remove-Item -LiteralPath $Directory -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Test-Excluded {
    <#
        Whether a path relative to upstream.path is left out. An item names a
        file, or a directory and everything under it; a trailing '/' says it
        must be a directory.
    #>
    param(
        [Parameter(Mandatory)]
        [string] $RelativePath,

        [Parameter(Mandatory)]
        [AllowEmptyCollection()]
        [string[]] $Exclude
    )

    foreach ($item in $Exclude) {
        if ($item.EndsWith('/')) {
            if ($RelativePath.StartsWith($item, [StringComparison]::Ordinal)) { return $true }
        } elseif ($RelativePath -ceq $item -or
            $RelativePath.StartsWith("$item/", [StringComparison]::Ordinal)) {
            return $true
        }
    }

    return $false
}

function Get-UpstreamEntry {
    <#
        The index entries that carry an upstream object, read with only as much
        checking as this script needs to act safely. Everything else about the
        entry is the validator's.
    #>
    param(
        [Parameter(Mandatory)]
        [string] $Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Catalog index not found: $Path"
    }

    $index = Get-Content -LiteralPath $Path -Raw -Encoding utf8 | ConvertFrom-Json
    $result = @()
    foreach ($artifact in @($index.artifacts)) {
        if ($null -eq $artifact -or $artifact -is [string]) { continue }
        if ($null -eq $artifact.PSObject.Properties['id']) { continue }
        $hasUpstream = $null -ne $artifact.PSObject.Properties['upstream'] -and $null -ne $artifact.upstream
        $result += , [pscustomobject]@{
            Id          = [string]$artifact.id
            Artifact    = $artifact
            HasUpstream = $hasUpstream
        }
    }

    return $result
}

function Get-UpstreamPin {
    <#
        The upstream object as plain values, or a thrown message naming what is
        wrong with it. Refused before anything is fetched: a branch name in
        'commit' would otherwise clone happily and pin nothing.
    #>
    param(
        [Parameter(Mandatory)]
        [string] $Id,

        [Parameter(Mandatory)]
        $Upstream
    )

    foreach ($field in @('repo', 'commit', 'path', 'license')) {
        if ($null -eq $Upstream.PSObject.Properties[$field] -or $Upstream.$field -isnot [string] -or
            [string]::IsNullOrWhiteSpace($Upstream.$field)) {
            throw "Artifact $Id upstream has no '$field'."
        }
    }

    if ($Upstream.commit -cnotmatch $CommitPattern) {
        throw "Artifact $Id upstream.commit '$($Upstream.commit)' is not a full 40-character lower-case commit SHA. A branch or tag can move; pin the commit."
    }

    $exclude = @()
    if ($null -ne $Upstream.PSObject.Properties['exclude'] -and $null -ne $Upstream.exclude) {
        $exclude = @($Upstream.exclude | ForEach-Object { [string]$_ })
    }

    return [pscustomobject]@{
        Repo    = [string]$Upstream.repo
        Commit  = [string]$Upstream.commit
        Path    = ([string]$Upstream.path).TrimEnd('/')
        License = [string]$Upstream.license
        Exclude = [string[]]$exclude
        Raw     = $Upstream
    }
}

function Get-UpstreamSelection {
    <#
        Splits the author's tree at upstream.path into what the catalog keeps
        and what 'exclude' leaves out, and finds the repository-root licence to
        add when the kept files carry none. Shared by sync and verify, so the two
        cannot disagree about which files an artifact should hold.
    #>
    param(
        [Parameter(Mandatory)]
        [string] $Clone,

        [Parameter(Mandatory)]
        $Pin,

        [Parameter(Mandatory)]
        [AllowEmptyCollection()]
        [System.Collections.Generic.List[string]] $Faults
    )

    $tree = Get-GitTree -Repository $Clone -Treeish $Pin.Commit -Path $Pin.Path
    $where = "$($Pin.Repo) at $($Pin.Commit)"
    if ($tree.Count -eq 0) {
        $Faults.Add("$where has nothing under '$($Pin.Path)'. Check upstream.path.")
        return $null
    }

    $kept = New-PathTable
    $matchedExcludes = @{}
    foreach ($relative in $tree.Keys) {
        $isExcluded = $false
        foreach ($item in $Pin.Exclude) {
            if (Test-Excluded -RelativePath $relative -Exclude @($item)) {
                $matchedExcludes[$item] = $true
                $isExcluded = $true
            }
        }
        if (-not $isExcluded) { $kept[$relative] = $tree[$relative] }
    }

    # An exclude that matches nothing is a typo, or a file the author has since
    # moved - either way the files it was written to keep out may now be in.
    foreach ($item in $Pin.Exclude) {
        if (-not $matchedExcludes.ContainsKey($item)) {
            $Faults.Add("upstream.exclude item '$item' matches nothing under '$($Pin.Path)' in $where. Remove it or correct it.")
        }
    }

    $licenseSource = $null
    $hasOwnLicense = @($kept.Keys | Where-Object { $_ -ieq $LicenseFile }).Count -gt 0
    if (-not $hasOwnLicense) {
        $root = Get-GitTree -Repository $Clone -Treeish $Pin.Commit -Path '' -NonRecursive
        foreach ($candidate in $RootLicenseNames) {
            $found = @($root.Keys | Where-Object { $_ -ieq $candidate -and $root[$_].Type -eq 'blob' })
            if ($found.Count -gt 0) {
                $licenseSource = [pscustomobject]@{ Path = $found[0]; Blob = $root[$found[0]].Blob }
                break
            }
        }
    }

    return [pscustomobject]@{
        Kept          = $kept
        HasOwnLicense = $hasOwnLicense
        LicenseSource = $licenseSource
    }
}

function Write-ProvenanceFile {
    <#
        UPSTREAM.json, in the field order of the index entry so the two read
        side by side. LF and a trailing newline whatever the platform, matching
        how .gitattributes checks JSON out.
    #>
    param(
        [Parameter(Mandatory)]
        [string] $Path,

        [Parameter(Mandatory)]
        $Pin
    )

    $provenance = [ordered]@{
        repo    = $Pin.Repo
        commit  = $Pin.Commit
        path    = [string]$Pin.Raw.path
        license = $Pin.License
    }
    if ($null -ne $Pin.Raw.PSObject.Properties['exclude']) {
        $provenance['exclude'] = [object[]]@($Pin.Exclude)
    }
    $provenance['synced_by'] = $SyncedBy

    $json = ($provenance | ConvertTo-Json -Depth 5).Replace("`r`n", "`n") + "`n"
    [System.IO.File]::WriteAllText($Path, $json, [System.Text.UTF8Encoding]::new($false))
}

function Invoke-UpstreamSync {
    param(
        [Parameter(Mandatory)]
        $Entry
    )

    $id = $Entry.Id
    $artifact = $Entry.Artifact
    if (-not $Entry.HasUpstream) {
        throw "Artifact $id has no upstream object in the index. Only an upstream artifact is synced."
    }

    $pin = Get-UpstreamPin -Id $id -Upstream $artifact.upstream
    $sourcePath = "artifacts/$id"
    $target = Join-Path $CatalogRoot $sourcePath
    $where = "$($pin.Repo) at $($pin.Commit)"

    $clone = New-UpstreamClone -Repo $pin.Repo -Commit $pin.Commit
    try {
        $faults = [System.Collections.Generic.List[string]]::new()
        $selection = Get-UpstreamSelection -Clone $clone -Pin $pin -Faults $faults
        if ($null -eq $selection) {
            throw "Refusing to sync $id; artifacts/$id is unchanged. $($faults -join ' ')"
        }

        # Everything below is decided from the tree, before a single blob is
        # fetched or a file in the catalog is touched.
        foreach ($relative in $selection.Kept.Keys) {
            $entry = $selection.Kept[$relative]
            if ($entry.Type -ne 'blob' -or $entry.Mode -eq '120000') {
                $faults.Add("'$($pin.Path)/$relative' is a $(if ($entry.Mode -eq '120000') { 'symbolic link' } else { $entry.Type }). An artifact carries files only; exclude it or adapt the skill instead.")
            }
        }

        if ($selection.Kept.Keys -ccontains $ProvenanceFile) {
            $faults.Add("'$($pin.Path)/$ProvenanceFile' exists upstream, and the catalog writes its own provenance under that name.")
        }

        if ($selection.Kept.Keys -cnotcontains 'SKILL.md') {
            $faults.Add("'$($pin.Path)' has no SKILL.md at its root. An artifact is a skill directory.")
        }

        $shipsCode = @($selection.Kept.Keys | Where-Object {
                $_.StartsWith('scripts/', [StringComparison]::Ordinal) -or $_ -ceq 'requirements.txt' })
        if ($shipsCode.Count -gt 0 -and $null -eq $artifact.PSObject.Properties['requires']) {
            $faults.Add("'$($pin.Path)/$($shipsCode[0])' is code to run, and the index entry declares no requires. Declare what a user must install to run it.")
        }

        if (-not $selection.HasOwnLicense -and $null -eq $selection.LicenseSource) {
            $faults.Add("Neither '$($pin.Path)' nor the repository root has a licence file ($($RootLicenseNames -join ', ')). The licence must travel with every installed copy.")
        }

        # The path rules, by the validator itself, over the paths the artifact
        # would have. The index is the real one, so an error elsewhere in it
        # also stops the sync: a sync that leaves the catalog invalid is not
        # finished.
        $proposed = @($selection.Kept.Keys | ForEach-Object { "$sourcePath/$_" }) + @("$sourcePath/$ProvenanceFile")
        if (-not $selection.HasOwnLicense) { $proposed += "$sourcePath/$LicenseFile" }
        $validation = & $ValidatorPath -IndexPath $IndexPath -PathList $proposed 6>$null
        $catalogPathPattern = "'" + [regex]::Escape("$sourcePath/") + "(?<relative>[^']+)'"
        foreach ($message in @($validation.Errors)) {
            if ($message -match $catalogPathPattern) {
                $message += " Upstream file: '$($pin.Path)/$($Matches.relative)'."
            }
            $faults.Add($message)
        }

        if ($faults.Count -gt 0) {
            throw "Refusing to sync $id from $where; artifacts/$id is unchanged.`n- $($faults -join "`n- ")"
        }

        # Byte for byte: the author's .gitattributes and this machine's
        # core.autocrlf must not touch what is checked out. info/attributes
        # outranks every in-tree .gitattributes.
        $infoDirectory = Join-Path $clone '.git/info'
        [void](New-Item -ItemType Directory -Path $infoDirectory -Force)
        [System.IO.File]::WriteAllText((Join-Path $infoDirectory 'attributes'),
            "* -text -eol -ident -filter -working-tree-encoding`n")

        [void](Invoke-UpstreamGit -Arguments @('sparse-checkout', 'init', '--cone') -WorkingDirectory $clone)
        [void](Invoke-UpstreamGit -Arguments @('sparse-checkout', 'set', $pin.Path) -WorkingDirectory $clone)
        [void](Invoke-UpstreamGit -Arguments @('-c', 'advice.detachedHead=false', 'checkout', '--quiet', $pin.Commit) `
            -WorkingDirectory $clone)

        $sourceRoot = Join-Path $clone $pin.Path

        # Hashed as raw bytes and compared with the tree: proof that what is
        # about to be copied is the author's content, not what a checkout made
        # of it.
        $relatives = @($selection.Kept.Keys)
        $hashes = @($relatives | ForEach-Object { Join-Path $sourceRoot $_ } |
            & git -C $clone hash-object --no-filters --stdin-paths)
        if ($LASTEXITCODE -ne 0 -or $hashes.Count -ne $relatives.Count) {
            throw "Could not hash the checked-out files of $where; artifacts/$id is unchanged."
        }
        for ($n = 0; $n -lt $relatives.Count; $n++) {
            if ($hashes[$n] -ne $selection.Kept[$relatives[$n]].Blob) {
                throw "Checked-out '$($pin.Path)/$($relatives[$n])' does not match its blob in $where; artifacts/$id is unchanged."
            }
        }

        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Recurse -Force
        }
        [void](New-Item -ItemType Directory -Path $target -Force)

        foreach ($relative in $relatives) {
            $destination = Join-Path $target $relative
            [void][System.IO.Directory]::CreateDirectory((Split-Path -Parent $destination))
            [System.IO.File]::Copy((Join-Path $sourceRoot $relative), $destination, $true)
        }

        if (-not $selection.HasOwnLicense) {
            [System.IO.File]::Copy((Join-Path $clone $selection.LicenseSource.Path), (Join-Path $target $LicenseFile), $true)
        }

        Write-ProvenanceFile -Path (Join-Path $target $ProvenanceFile) -Pin $pin

        return [pscustomobject]@{
            Id            = $id
            Commit        = $pin.Commit
            FileCount     = $relatives.Count
            ExcludedCount = @($pin.Exclude).Count
            LicenseAdded  = -not $selection.HasOwnLicense
        }
    } finally {
        Remove-UpstreamClone -Directory $clone
    }
}

function Test-UpstreamArtifact {
    <#
        One artifact's committed files against its pin. Returns the faults; an
        empty list means the catalog holds exactly the author's bytes.
    #>
    param(
        [Parameter(Mandatory)]
        $Entry
    )

    $id = $Entry.Id
    $faults = [System.Collections.Generic.List[string]]::new()
    try {
        $pin = Get-UpstreamPin -Id $id -Upstream $Entry.Artifact.upstream
    } catch {
        $faults.Add($_.Exception.Message)
        return $faults
    }

    # HEAD, not the working tree: what CI verifies is what was committed, after
    # .gitattributes had its say.
    $catalog = Get-GitTree -Repository $CatalogRoot -Treeish 'HEAD' -Path "artifacts/$id"
    if ($catalog.Count -eq 0) {
        $faults.Add("Artifact $id has no committed files under artifacts/$id. Run scripts/sync-upstream.ps1 -Id $id and commit the result.")
        return $faults
    }

    try {
        $clone = New-UpstreamClone -Repo $pin.Repo -Commit $pin.Commit
    } catch {
        $faults.Add("Artifact ${id}: $($_.Exception.Message)")
        return $faults
    }

    try {
        $selectionFaults = [System.Collections.Generic.List[string]]::new()
        $selection = Get-UpstreamSelection -Clone $clone -Pin $pin -Faults $selectionFaults
        foreach ($fault in $selectionFaults) { $faults.Add("Artifact ${id}: $fault") }
        if ($null -eq $selection) { return $faults }

        $actual = New-PathTable
        foreach ($relative in $catalog.Keys) {
            if ($relative -ceq $ProvenanceFile) { continue }
            $actual[$relative] = $catalog[$relative]
        }

        # The LICENSE the catalog added must be the author's root licence, byte
        # for byte, or it is a licence text nobody published.
        if (-not $selection.HasOwnLicense -and $actual.Contains($LicenseFile)) {
            if ($null -eq $selection.LicenseSource) {
                $faults.Add("Artifact ${id}: artifacts/$id/$LicenseFile has no upstream counterpart: neither '$($pin.Path)' nor the repository root has a licence file.")
            } elseif ($actual[$LicenseFile].Blob -ne $selection.LicenseSource.Blob) {
                $faults.Add("Artifact ${id}: artifacts/$id/$LicenseFile differs from '$($selection.LicenseSource.Path)' at the root of $($pin.Repo) at $($pin.Commit).")
            }
            $actual.Remove($LicenseFile)
        }

        foreach ($relative in $selection.Kept.Keys) {
            if (-not $actual.Contains($relative)) {
                $faults.Add("Artifact ${id}: '$($pin.Path)/$relative' is in the pinned commit but missing from artifacts/$id.")
            } elseif ($actual[$relative].Blob -ne $selection.Kept[$relative].Blob) {
                $faults.Add("Artifact ${id}: artifacts/$id/$relative differs from '$($pin.Path)/$relative' at $($pin.Commit). If only line endings differ, the catalog's .gitattributes rewrote it: add 'artifacts/$id/** -text' and re-add the file; never edit it.")
            }
        }

        foreach ($relative in $actual.Keys) {
            if (-not $selection.Kept.Contains($relative)) {
                $faults.Add("Artifact ${id}: artifacts/$id/$relative is not in '$($pin.Path)' at $($pin.Commit), or upstream.exclude leaves it out.")
            }
        }
    } finally {
        Remove-UpstreamClone -Directory $clone
    }

    return $faults
}

if ([string]::IsNullOrWhiteSpace($IndexPath)) {
    $IndexPath = Join-Path $CatalogRoot 'index.json'
}

# Paths from git arrive as UTF-8; the console's code page on Windows would turn
# a non-ASCII file name into something no file is called.
$previousEncoding = [Console]::OutputEncoding
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
try {
    $entries = @(Get-UpstreamEntry -Path $IndexPath)

    if ($PSCmdlet.ParameterSetName -eq 'Sync') {
        $entry = @($entries | Where-Object { $_.Id -ceq $Id })
        if ($entry.Count -eq 0) {
            throw "Artifact $Id is not in $IndexPath."
        }

        $result = Invoke-UpstreamSync -Entry $entry[0]
        Write-Host "Synced $($result.Id) at $($result.Commit): $($result.FileCount) file(s)$(if ($result.LicenseAdded) { ', LICENSE added from the repository root' })."
        return $result
    }

    $targets = @($entries | Where-Object { $_.HasUpstream })
    if ($PSBoundParameters.ContainsKey('Id')) {
        $targets = @($targets | Where-Object { $_.Id -ceq $Id })
        if ($targets.Count -eq 0) {
            throw "Artifact $Id is not an upstream artifact in $IndexPath."
        }
    }

    $errors = [System.Collections.Generic.List[string]]::new()
    foreach ($target in $targets) {
        foreach ($fault in (Test-UpstreamArtifact -Entry $target)) {
            $errors.Add($fault)
            Write-Host "ERROR: $fault"
        }
    }

    return [pscustomobject]@{
        IsValid       = ($errors.Count -eq 0)
        Errors        = $errors.ToArray()
        ArtifactCount = $targets.Count
    }
} finally {
    [Console]::OutputEncoding = $previousEncoding
}
