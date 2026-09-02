<#
    Validates the catalog's index.json against the matching contract the
    installer enforces.

    The failure this exists to prevent is specific. If the catalog writes
    'lang:ts' where the installer looks for 'lang:typescript', nothing breaks
    loudly - the artifact simply never gets selected, and the developer who
    wrote it has no way to know. That is a success with missing content, which
    the transport spike identified as the dangerous outcome on this system.
    Every check below exists to turn that silence into a CI failure.

    This validator and the installer's Read-AcceleratorCatalogIndex are one rule
    expressed twice. Where the installer is strict, this is strict - notably the
    case-sensitive vocabulary comparison. Being more permissive here would let an
    artifact pass CI and then install nowhere; being stricter would fail an
    artifact that installs fine.

    The one deliberate divergence is the reporting shape. The installer throws on
    the first problem because it must not proceed with a catalog it does not
    understand. CI has no such constraint, and an author who fixes one typo per
    push soon stops trusting the check - so every fault is collected and
    reported together.

    The second half of the contract is about paths rather than tags. TASK-001
    measured which repository paths break a Git checkout on Windows, and those
    findings were written into README.md as a table enforced by review alone.
    Pass -CatalogRoot to have them enforced here instead: a reserved device name
    or a trailing dot fails the checkout outright, so the user cannot install
    anything at all, and a case collision is worse - the clone succeeds and one
    file silently disappears from the worktree.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string] $IndexPath,

    # The catalog checkout whose file paths are checked against the Windows path
    # rules. Opt-in rather than derived from $IndexPath: the test suite writes
    # dozens of index fixtures into one directory, and a scan that switched
    # itself on would report faults about a neighbouring test's files.
    [string] $CatalogRoot,

    # The same check driven from a list of paths instead of a directory. This is
    # how the rules are tested at all: 'CON.md' and 'trailing.' cannot be created
    # on Windows, so a fixture on disk could only ever be built on Linux - for
    # rules that exist to describe Windows. It also lets a caller narrow the scan,
    # e.g. to `git ls-files` output.
    [string[]] $PathList
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# The five dimensions the installer knows. Deliberately wider than the set
# matching actually filters on, which stops at 'agents': topics is a *selection*
# dimension, not a filter - an artifact's topics decide whether a developer who
# already matched the filter actually wants it. But the vocabulary still
# publishes topics, and this validator still has to check them.
$VocabularyDimensions = @('languages', 'frameworks', 'layout', 'agents', 'topics')

$SupportedSchemaVersions = @('1', '2')

# The Windows path rules, as TASK-001 measured them by cloning deliberately
# invalid trees: a reserved device name and a trailing dot both failed the
# checkout with 'invalid path' and exit 128, and a case collision cloned clean
# with one file missing from the worktree.
#
# 240 is the spike's conservative maximum, not an observed limit: a
# 244-character path worked there only because that machine had
# core.longpaths=true, which must not be assumed of every developer.
$ReservedDeviceNames = @('CON', 'PRN', 'AUX', 'NUL') +
    (1..9 | ForEach-Object { "COM$_" }) +
    (1..9 | ForEach-Object { "LPT$_" })

$MaximumPathLength = 240

$errors = [System.Collections.Generic.List[string]]::new()

function Add-CatalogError {
    <#
        Records one fault and writes it to the host as it is found, so a CI log
        reads top to bottom instead of only at the summary.
    #>
    param(
        [Parameter(Mandatory)]
        [string] $Message
    )

    $errors.Add($Message)
    Write-Host "ERROR: $Message"
}

function Get-ArtifactId {
    <#
        Resolves an artifact's id for use in diagnostics, falling back to its
        position when the id itself is missing.

        Called before any other property is read, because every message below
        interpolates the id - reading it unguarded under strict mode would kill
        the error path with a bare "property cannot be found" naming nothing.
        The position is the only handle an author has on an artifact that has no
        id, so an error must never come back naming neither.
    #>
    param(
        [Parameter(Mandatory)]
        [AllowNull()]
        $Artifact,

        [Parameter(Mandatory)]
        [int] $Index
    )

    if ($null -ne $Artifact -and
        $Artifact -isnot [string] -and
        $null -ne $Artifact.PSObject.Properties['id'] -and
        -not [string]::IsNullOrWhiteSpace($Artifact.id)) {
        return $Artifact.id
    }

    return "<artifact at index $Index>"
}

function Get-CatalogPathLabel {
    <#
        How a path is named in a diagnostic: by the artifact that owns it where
        one does, and as a catalog path otherwise.

        The owning id is quoted as the *index* spells it rather than as the
        directory does, because the two can differ in case - and when they do,
        the author needs to see both spellings to understand which one to change.
    #>
    param(
        [Parameter(Mandatory)]
        [string] $Path,

        [Parameter(Mandatory)]
        [AllowNull()]
        [hashtable] $DeclaredIds
    )

    $segments = $Path.Split('/')
    if ($segments.Count -ge 2 -and $segments[0] -eq 'artifacts') {
        $directory = $segments[1]
        $key = $directory.ToUpperInvariant()
        if ($null -ne $DeclaredIds -and $DeclaredIds.ContainsKey($key)) {
            return "Artifact $($DeclaredIds[$key]) path '$Path'"
        }

        return "Artifact directory '$directory' path '$Path'"
    }

    return "Catalog path '$Path'"
}

function Test-CatalogPathComponent {
    <#
        The two rules that fail a Windows checkout outright, applied to every
        component of one path.

        Both are per-component rather than per-path: 'artifacts/CON/skill.md'
        breaks on the directory, and Git reports neither more precisely than
        'invalid path', so the message has to name the component itself.
    #>
    param(
        [Parameter(Mandatory)]
        [string] $Path,

        [Parameter(Mandatory)]
        [string] $Label
    )

    foreach ($component in $Path.Split('/')) {
        if ([string]::IsNullOrEmpty($component)) { continue }

        # '.' and '..' are dot segments, not names that happen to end in a dot.
        # Test-CatalogSourcePath reports them as what they are; reporting them
        # here as well would hand the author two errors for one fault, one of
        # them naming the wrong rule.
        if ($component -eq '.' -or $component -eq '..') { continue }

        # Compared on the part before the first dot, and case-insensitively:
        # Windows resolves 'CON', 'CON.md' and 'con.txt' all to the console
        # device, while 'CONTRIBUTING.md' and 'NULL.md' are ordinary files.
        $deviceCandidate = $component.Split('.')[0].ToUpperInvariant()
        if ($ReservedDeviceNames -contains $deviceCandidate) {
            Add-CatalogError "$Label uses the Windows reserved device name '$deviceCandidate' in component '$component'. Checkout fails on Windows with 'invalid path'; rename it."
        }

        if ($component -ne $component.TrimEnd(@('.', ' '))) {
            Add-CatalogError "$Label ends component '$component' with a dot or a space. Checkout fails on Windows with 'invalid path'; rename it."
        }
    }
}

function Test-CatalogPathRule {
    <#
        The TASK-001 path rules over one list of repository-relative paths.

        Paths arrive as data rather than being discovered here, for the same
        reason the id collision check below folds ids by hand instead of asking
        the filesystem: what is being modelled is Windows, and the runner is not
        Windows. The caller decides where the list came from.
    #>
    param(
        [Parameter(Mandatory)]
        [AllowEmptyCollection()]
        [string[]] $Paths,

        [Parameter(Mandatory)]
        [AllowNull()]
        [hashtable] $DeclaredIds
    )

    $seenPaths = @{}
    foreach ($path in ($Paths | Sort-Object)) {
        if ([string]::IsNullOrWhiteSpace($path)) { continue }

        $normalized = $path.Replace('\', '/')
        $label = Get-CatalogPathLabel -Path $normalized -DeclaredIds $DeclaredIds

        Test-CatalogPathComponent -Path $normalized -Label $label

        if ($normalized.Length -gt $MaximumPathLength) {
            Add-CatalogError "$label is $($normalized.Length) characters long, over the $MaximumPathLength-character maximum. Longer paths need core.longpaths=true, which not every developer has."
        }

        # Folded to upper case explicitly, the same way artifact ids are below:
        # this states which filesystem behaviour is being modelled rather than
        # leaning on a comparer that happens to be case-insensitive.
        $key = $normalized.ToUpperInvariant()
        if ($seenPaths.ContainsKey($key)) {
            Add-CatalogError "$label collides with '$($seenPaths[$key])' on a case-insensitive filesystem. On Windows the clone succeeds and one of the two files silently disappears from the worktree."
            continue
        }

        $seenPaths[$key] = $normalized
    }
}

function Test-CatalogSourcePath {
    <#
        The same rules over a declared source_path, plus the three that only a
        declared string can break: an absolute path, a '\' separator, and a '.'
        or '..' segment. A path walked out of a checkout is relative and
        '/'-separated by construction; one typed into index.json is whatever the
        author typed.

        Still not resolved against the filesystem - an artifact whose
        source_path names a directory that does not exist remains a documented
        gap, and closing it is a separate decision about fixtures.
    #>
    param(
        [Parameter(Mandatory)]
        [string] $Id,

        [Parameter(Mandatory)]
        [string] $SourcePath
    )

    $label = "Artifact $Id declares source_path '$SourcePath', which"

    if ($SourcePath.Contains('\')) {
        Add-CatalogError "$label uses '\' separators. Catalog paths are repository-relative with '/' separators."
    }

    if ($SourcePath.StartsWith('/') -or $SourcePath -match '^[A-Za-z]:') {
        Add-CatalogError "$label is absolute. Catalog paths are repository-relative."
    }

    $segments = $SourcePath.Replace('\', '/').Split('/')
    if ($segments -contains '.' -or $segments -contains '..') {
        Add-CatalogError "$label contains a '.' or '..' segment. Catalog paths may not point outside their own subtree."
    }

    Test-CatalogPathComponent -Path $SourcePath.Replace('\', '/') -Label "Artifact $Id source_path '$SourcePath'"

    if ($SourcePath.Length -gt $MaximumPathLength) {
        Add-CatalogError "Artifact $Id source_path '$SourcePath' is $($SourcePath.Length) characters long, over the $MaximumPathLength-character maximum."
    }
}

function Get-CatalogCheckoutPath {
    <#
        Every file under a catalog checkout, as repository-relative
        forward-slash paths.

        The working tree is walked rather than `git ls-files` asked, so the same
        code path serves a fixture directory in the test suite and a real clone,
        and so a file that is present but untracked - the state a half-finished
        artifact is in - is still checked. .git is skipped: its own contents are
        not what any consumer checks out.
    #>
    param(
        [Parameter(Mandatory)]
        [string] $Root
    )

    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        throw "Catalog root not found: $Root"
    }

    $resolved = (Resolve-Path -LiteralPath $Root).ProviderPath.TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar)

    # -Force because a dot-prefixed name is hidden to PowerShell on every
    # platform, and .github/ is exactly the kind of directory a bad path lands in.
    return @(Get-ChildItem -LiteralPath $resolved -Recurse -File -Force |
        ForEach-Object { $_.FullName.Substring($resolved.Length + 1).Replace('\', '/') } |
        Where-Object { $_ -ne '.git' -and -not $_.StartsWith('.git/') })
}

function Test-CatalogArtifact {
    <#
        Validates one artifact against the catalog vocabulary, recording every
        problem it finds rather than returning at the first.
    #>
    param(
        [Parameter(Mandatory)]
        [AllowNull()]
        $Artifact,

        [Parameter(Mandatory)]
        [AllowNull()]
        $Vocabulary,

        [Parameter(Mandatory)]
        [string] $SchemaVersion,

        [Parameter(Mandatory)]
        [int] $Index
    )

    $id = Get-ArtifactId -Artifact $Artifact -Index $Index

    if ($null -eq $Artifact -or $Artifact -is [string] -or $Artifact -is [ValueType]) {
        Add-CatalogError "Catalog artifact at index $Index is not an object. Each entry in the artifacts list must be a JSON object with an id."
        return
    }

    # Fixtures are transport test data, not catalog content. The flag suppresses
    # every check below it, so who may claim it is constrained: a typo'd
    # fixture:true on a real artifact would make that artifact vanish from every
    # install with no error anywhere.
    #
    # -eq $true rather than a truthiness test. The string 'false' is truthy in
    # PowerShell, so "fixture": "false" would otherwise read as a fixture and
    # silently hide a real artifact - the precise shape of the failure this
    # whole validator exists to prevent.
    if ($null -ne $Artifact.PSObject.Properties['fixture'] -and $Artifact.fixture -eq $true) {
        if ($id -notlike 'AS-SPIKE-*') {
            Add-CatalogError "Artifact $id declares fixture: true, but only AS-SPIKE-* artifacts may. The flag exempts an artifact from all matching validation and hides it from every install."
        }
        return
    }

    $hasAppliesTo = $null -ne $Artifact.PSObject.Properties['applies_to'] -and $null -ne $Artifact.applies_to
    $hasStrength = $null -ne $Artifact.PSObject.Properties['strength'] -and $null -ne $Artifact.strength

    if (-not $hasAppliesTo) {
        # Absent is not the same as {}. Requiring it explicitly means "applies
        # everywhere" can never be confused with "the author forgot".
        Add-CatalogError "Artifact $id is missing required field 'applies_to'. Write applies_to as {} for a universally applicable artifact."
    }

    if (-not $hasStrength) {
        Add-CatalogError "Artifact $id is missing required field 'strength'. Expected 'always' or 'on-demand'."
    }

    if ($hasStrength -and $Artifact.strength -cne 'always' -and $Artifact.strength -cne 'on-demand') {
        Add-CatalogError "Artifact $id has unknown strength '$($Artifact.strength)'. Expected 'always' or 'on-demand'."
    }

    $hasScope = $null -ne $Artifact.PSObject.Properties['scope'] -and
        -not [string]::IsNullOrWhiteSpace($Artifact.scope)
    if ($SchemaVersion -ceq '2' -and -not $hasScope) {
        Add-CatalogError "Artifact $id is missing required field 'scope'. Catalog schema 2 requires 'project' or 'user'."
    }
    if ($hasScope -and $Artifact.scope -cnotin @('project', 'user')) {
        Add-CatalogError "Artifact $id has unknown scope '$($Artifact.scope)'. Expected 'project' or 'user'."
    }
    if ($hasScope -and $Artifact.scope -ceq 'user' -and
        $hasStrength -and $Artifact.strength -ceq 'always') {
        Add-CatalogError "Artifact $id is always but has user scope. User artifacts require explicit consent and must be on-demand."
    }

    if ($hasAppliesTo) {
        # A scalar applies_to - "applies_to": "typescript" - has no properties to
        # walk, so the loop below would pass it silently and the installer would
        # then treat the artifact as applying to every profile.
        if ($Artifact.applies_to -is [string] -or $Artifact.applies_to -is [ValueType] -or $Artifact.applies_to -is [array]) {
            Add-CatalogError "Artifact $id declares applies_to as the scalar '$($Artifact.applies_to)' rather than an object. Write applies_to as {} for a universally applicable artifact."
        } else {
            foreach ($declared in $Artifact.applies_to.PSObject.Properties) {
                # Case-sensitive throughout: the vocabulary is a closed lower-case
                # set and the installer compares with -ccontains. Being more
                # permissive here means an artifact passes CI and then matches
                # nothing.
                if ($VocabularyDimensions -cnotcontains $declared.Name) {
                    Add-CatalogError "Artifact $id declares unknown dimension '$($declared.Name)'. Known dimensions: $($VocabularyDimensions -join ', ')."
                    continue
                }

                # A dimension the artifact references but the vocabulary omits
                # leaves the allowed set empty, which would report the value as
                # merely "not allowed" and send the author hunting in the
                # artifact when the vocabulary is at fault.
                if ($null -eq $Vocabulary -or $null -eq $Vocabulary.PSObject.Properties[$declared.Name]) {
                    Add-CatalogError "Artifact $id declares dimension '$($declared.Name)', which the catalog vocabulary does not publish."
                    continue
                }

                $allowed = @($Vocabulary.($declared.Name))
                foreach ($value in @($declared.Value)) {
                    if ($allowed -cnotcontains $value) {
                        Add-CatalogError "Artifact $id declares '$value' in dimension '$($declared.Name)', which is not in the catalog vocabulary. Allowed: $($allowed -join ', ')."
                    }
                }
            }
        }
    }

    $topics = @()
    if ($null -ne $Artifact.PSObject.Properties['topics'] -and $null -ne $Artifact.topics) {
        $topics = @($Artifact.topics)
    }

    if ($topics.Count -gt 0 -and ($null -eq $Vocabulary -or $null -eq $Vocabulary.PSObject.Properties['topics'])) {
        Add-CatalogError "Artifact $id declares topics, which the catalog vocabulary does not publish."
    } else {
        foreach ($topic in $topics) {
            if (@($Vocabulary.topics) -cnotcontains $topic) {
                Add-CatalogError "Artifact $id declares topic '$topic', which is not in the catalog vocabulary. Allowed: $(@($Vocabulary.topics) -join ', ')."
            }
        }
    }

    # An on-demand artifact with no topics can never be selected by any profile,
    # so it is dead catalog content rather than an artifact that merely happens
    # not to match today.
    if ($hasStrength -and $Artifact.strength -ceq 'on-demand' -and $topics.Count -eq 0) {
        Add-CatalogError "Artifact $id is on-demand but declares no topics, so no profile could ever select it."
    }

    $hasPresentation = $null -ne $Artifact.PSObject.Properties['presentation'] -and
        $null -ne $Artifact.presentation
    if ($SchemaVersion -ceq '2' -and $hasStrength -and
        $Artifact.strength -ceq 'on-demand' -and -not $hasPresentation) {
        Add-CatalogError "Artifact $id is on-demand but has no presentation card. Catalog schema 2 requires name, summary and benefits."
    }
    if ($hasPresentation) {
        if ($Artifact.presentation -is [string] -or $Artifact.presentation -is [ValueType] -or
            $Artifact.presentation -is [array]) {
            Add-CatalogError "Artifact $id declares presentation as a scalar rather than an object."
        } else {
            foreach ($field in @('name', 'summary', 'benefits')) {
                if ($null -eq $Artifact.presentation.PSObject.Properties[$field] -or
                    $null -eq $Artifact.presentation.$field) {
                    Add-CatalogError "Artifact $id presentation is missing required field '$field'."
                }
            }

            if ($null -ne $Artifact.presentation.PSObject.Properties['name'] -and
                ($Artifact.presentation.name -isnot [string] -or
                    [string]::IsNullOrWhiteSpace($Artifact.presentation.name))) {
                Add-CatalogError "Artifact $id presentation name must be non-empty."
            }
            if ($null -ne $Artifact.presentation.PSObject.Properties['summary'] -and
                ($Artifact.presentation.summary -isnot [string] -or
                    [string]::IsNullOrWhiteSpace($Artifact.presentation.summary))) {
                Add-CatalogError "Artifact $id presentation summary must be non-empty."
            }
            if ($null -ne $Artifact.presentation.PSObject.Properties['benefits']) {
                $benefits = @($Artifact.presentation.benefits)
                if ($Artifact.presentation.benefits -is [string] -or
                    $Artifact.presentation.benefits -is [ValueType] -or
                    $benefits.Count -eq 0 -or
                    @($benefits | Where-Object { $_ -isnot [string] -or [string]::IsNullOrWhiteSpace($_) }).Count -gt 0) {
                    Add-CatalogError "Artifact $id presentation benefits must be a non-empty list of non-empty strings."
                }
            }
        }
    }
}

# A missing or malformed file is a broken invocation, not catalog content that
# failed validation, so these throw rather than joining the error list. There is
# nothing here for an author to fix in the catalog.
if (-not (Test-Path -LiteralPath $IndexPath -PathType Leaf)) {
    throw "Catalog index not found: $IndexPath"
}

try {
    # ConvertFrom-Json's own parse error quotes the offending token but never the
    # file, and a catalog can hold many index files across many refs.
    $index = Get-Content -LiteralPath $IndexPath -Raw | ConvertFrom-Json -ErrorAction Stop
} catch {
    throw "Catalog index at $IndexPath is not valid JSON: $($_.Exception.Message)"
}

if ($null -eq $index) {
    throw "Catalog index at $IndexPath is empty."
}

# Checked before anything else reads the index: a version this contract does not
# cover makes every field below it a guess, and "the contract moved" is more
# useful than a vocabulary complaint about a field that was renamed.
if ($null -eq $index.PSObject.Properties['schema_version'] -or
    $SupportedSchemaVersions -cnotcontains $index.schema_version) {
    $declaredVersion = if ($null -ne $index.PSObject.Properties['schema_version']) { $index.schema_version } else { '<missing>' }
    Add-CatalogError "Catalog index schema_version '$declaredVersion' is not covered by this validator (supports '$($SupportedSchemaVersions -join ', ')')."
}

$vocabulary = $null
if ($null -eq $index.PSObject.Properties['vocabulary'] -or $null -eq $index.vocabulary) {
    Add-CatalogError "Catalog index at $IndexPath has no vocabulary block. No artifact tag can be validated without it."
} else {
    $vocabulary = $index.vocabulary
}

# An index with no artifacts key at all is a different fault from one that
# publishes an empty list: the first is a malformed file, the second is a
# catalog that legitimately has nothing to offer yet.
$artifacts = @()
if ($null -eq $index.PSObject.Properties['artifacts']) {
    Add-CatalogError "Catalog index at $IndexPath has no artifacts list. Write an empty list for a catalog with no artifacts."
} elseif ($null -ne $index.artifacts) {
    $artifacts = @($index.artifacts)
}

# Duplicate ids are checked across the whole index because this is the only
# place the whole index is visible. Two ids differing only in case become the
# same directory on Windows and default macOS - the clone succeeds and one
# artifact quietly overwrites the other.
#
# The fold to upper case is explicit rather than left to the hashtable's own
# comparer, which is already case-insensitive. Folding here states which
# filesystem behaviour is being modelled instead of leaning on a property of the
# container, and keeps the key stable if the table is ever swapped.
$seenIds = @{}
for ($i = 0; $i -lt $artifacts.Count; $i++) {
    $artifact = $artifacts[$i]

    # A bare string in the artifacts array answers PSObject.Properties['id'] with
    # nothing, so this also catches "artifacts": ["AS-0001"].
    if ($null -eq $artifact -or
        $artifact -is [string] -or
        $null -eq $artifact.PSObject.Properties['id'] -or
        [string]::IsNullOrWhiteSpace($artifact.id)) {
        Add-CatalogError "Catalog index at $IndexPath contains an artifact with no id (at index $i)."
        continue
    }

    # Upper-cased rather than compared case-insensitively so the message can
    # quote both ids exactly as the catalog wrote them.
    $key = $artifact.id.ToUpperInvariant()
    if ($seenIds.ContainsKey($key)) {
        Add-CatalogError "Catalog index declares '$($seenIds[$key])' and '$($artifact.id)', which collide on a case-insensitive filesystem. Artifact ids must be unique."
        continue
    }

    $seenIds[$key] = $artifact.id
}

for ($i = 0; $i -lt $artifacts.Count; $i++) {
    $schemaVersion = if ($null -ne $index.PSObject.Properties['schema_version']) { [string]$index.schema_version } else { '<missing>' }
    Test-CatalogArtifact -Artifact $artifacts[$i] -Vocabulary $vocabulary `
        -SchemaVersion $schemaVersion -Index $i
}

# --------------------------------------------------------------------------
# The TASK-001 path rules. Two inputs, because a catalog names paths in two
# places: index.json declares a source_path per artifact, and the checkout holds
# the files themselves. A rule enforced on one and not the other is a rule an
# author can still break.
# --------------------------------------------------------------------------
for ($i = 0; $i -lt $artifacts.Count; $i++) {
    $artifact = $artifacts[$i]
    if ($null -eq $artifact -or $artifact -is [string] -or $artifact -is [ValueType]) { continue }
    if ($null -eq $artifact.PSObject.Properties['source_path'] -or
        [string]::IsNullOrWhiteSpace($artifact.source_path)) {
        continue
    }

    Test-CatalogSourcePath -Id (Get-ArtifactId -Artifact $artifact -Index $i) `
        -SourcePath ([string]$artifact.source_path)
}

# Reported so a caller can tell a scan that found nothing from a scan that never
# ran - the cost of making the checkout scan opt-in.
$checkoutPaths = @()
if ($PSBoundParameters.ContainsKey('PathList')) {
    $checkoutPaths = @($PathList)
} elseif (-not [string]::IsNullOrWhiteSpace($CatalogRoot)) {
    $checkoutPaths = Get-CatalogCheckoutPath -Root $CatalogRoot
}

if ($checkoutPaths.Count -gt 0) {
    Test-CatalogPathRule -Paths $checkoutPaths -DeclaredIds $seenIds
}

return [pscustomobject]@{
    IsValid       = ($errors.Count -eq 0)
    Errors        = $errors.ToArray()
    ArtifactCount = $artifacts.Count
    PathCount     = $checkoutPaths.Count
}
