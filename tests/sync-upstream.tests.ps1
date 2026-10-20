Set-StrictMode -Version Latest

# No network. The index entries below name https://github.com/fixture-owner/fixture-skills,
# the only form the catalog accepts, and git's url.<base>.insteadOf - set through
# GIT_CONFIG_* for this run only - sends that URL to a repository built in
# $TestDrive. The script under test has no test hook to keep honest.

Describe 'sync-upstream.ps1' {
    BeforeAll {
        $repoRoot = $PSCommandPath | Split-Path -Parent | Split-Path -Parent
        $sync = Join-Path $repoRoot 'scripts/sync-upstream.ps1'
        $upstreamUrl = 'https://github.com/fixture-owner/fixture-skills'

        # Commits are made under a fixed identity and unsigned, so a developer's
        # own commit.gpgsign or missing user.email cannot fail the suite.
        $gitIdentity = @('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.com',
            '-c', 'commit.gpgsign=false', '-c', 'core.autocrlf=false')

        function Invoke-FixtureGit {
            param([string] $Repository, [string[]] $Arguments)
            $output = & git -C $Repository @gitIdentity @Arguments 2>&1
            if ($LASTEXITCODE -ne 0) { throw "git $($Arguments -join ' ') failed: $output" }
            return @($output | Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] } |
                ForEach-Object { [string]$_ })
        }

        function New-FixtureCommit {
            <#
                Writes a commit from a table of path -> content, through the
                object database only. Nothing touches the filesystem under those
                paths, so a tree can hold what Windows cannot create: two names
                differing only in case, or a symbolic link.

                A string value is written as UTF-8 bytes exactly as given (no
                newline conversion); a byte[] as is; a hashtable as
                @{ Mode = '120000'; Content = 'target' }.
            #>
            param([string] $Repository, [System.Collections.IDictionary] $Files, [string] $Ref, [string] $Message = 'fixture')

            $scratch = Join-Path $TestDrive ('blob-' + [guid]::NewGuid().ToString('N'))
            [void](Invoke-FixtureGit -Repository $Repository -Arguments @('read-tree', '--empty'))
            foreach ($path in $Files.Keys) {
                $value = $Files[$path]
                $mode = '100644'
                if ($value -is [hashtable]) { $mode = $value.Mode; $value = $value.Content }
                $bytes = if ($value -is [byte[]]) { $value } else { [System.Text.UTF8Encoding]::new($false).GetBytes([string]$value) }
                [System.IO.File]::WriteAllBytes($scratch, $bytes)
                $blob = @(Invoke-FixtureGit -Repository $Repository -Arguments @('hash-object', '-w', '--no-filters', $scratch))[0]
                [void](Invoke-FixtureGit -Repository $Repository -Arguments @(
                        '-c', 'core.ignorecase=false', 'update-index', '--add', '--cacheinfo', "$mode,$blob,$path"))
            }
            $tree = @(Invoke-FixtureGit -Repository $Repository -Arguments @('write-tree'))[0]
            $commit = @(Invoke-FixtureGit -Repository $Repository -Arguments @('commit-tree', $tree, '-m', $Message))[0]
            [void](Invoke-FixtureGit -Repository $Repository -Arguments @('update-ref', $Ref, $commit))
            return $commit
        }

        # One upstream repository holds every case, each skill under its own
        # path; a test chooses its case through upstream.path.
        $script:binary = [byte[]](0, 1, 2, 13, 10, 255, 254, 13, 10, 0)
        $script:rootLicense = "MIT License`n`nCopyright (c) 2026 Fixture Owner`n"
        $files = @{
            'LICENSE'                               = $rootLicense
            'README.md'                              = "# Fixture skills`n"
            'skills/demo/SKILL.md'                   = "---`nname: demo-skill`ndescription: Researches a demo topic.`n---`n# Demo`n"
            'skills/demo/references/guide.md'        = "Guide.`n"
            'skills/demo/assets/demo.bin'            = $binary
            'skills/demo/assets/nested/clip.bin'     = $binary
            'skills/demo/.skillignore'               = "assets/`n"
            'skills/own-license/SKILL.md'            = "---`nname: own-license`ndescription: x`n---`n"
            'skills/own-license/LICENSE'             = "Apache License`n"
            'skills/no-skill/README.md'              = "No SKILL.md here.`n"
            'skills/scripted/SKILL.md'               = "---`nname: scripted`ndescription: x`n---`n"
            'skills/scripted/scripts/run.py'         = "print('hi')`n"
            'skills/collide/SKILL.md'                = "---`nname: collide`ndescription: x`n---`n"
            'skills/collide/notes.md'                = "lower`n"
            'skills/linked/SKILL.md'                 = "---`nname: linked`ndescription: x`n---`n"
            'skills/linked/elsewhere.md'             = @{ Mode = '120000'; Content = '../../README.md' }
            'skills/crlf/SKILL.md'                   = "---`r`nname: crlf`r`ndescription: x`r`n---`r`n"
        }
        # Keyed case-sensitively: a hashtable literal folds case, and the
        # collision case needs both spellings.
        $script:upstreamFiles = [System.Collections.Hashtable]::new([StringComparer]::Ordinal)
        foreach ($key in $files.Keys) { $upstreamFiles[$key] = $files[$key] }
        $upstreamFiles['skills/collide/NOTES.md'] = "upper`n"

        $upstreamRepo = Join-Path $TestDrive 'upstream'
        [void](New-Item -ItemType Directory -Path $upstreamRepo)
        [void](Invoke-FixtureGit -Repository $upstreamRepo -Arguments @('init', '--quiet', '--initial-branch=main'))
        # What GitHub allows and a bare local repository does not by default:
        # partial clone filters, and fetching a commit by id.
        [void](Invoke-FixtureGit -Repository $upstreamRepo -Arguments @('config', 'uploadpack.allowFilter', 'true'))
        [void](Invoke-FixtureGit -Repository $upstreamRepo -Arguments @('config', 'uploadpack.allowAnySHA1InWant', 'true'))
        $script:mainCommit = New-FixtureCommit -Repository $upstreamRepo -Files $upstreamFiles -Ref 'refs/heads/main'

        # A commit reachable from no branch or tag, so a clone does not bring it
        # down and the script has to fetch it by id.
        $hiddenFiles = $upstreamFiles.Clone()
        $hiddenFiles['skills/demo/SKILL.md'] = "---`nname: demo-skill`ndescription: A later revision.`n---`n"
        $script:hiddenCommit = New-FixtureCommit -Repository $upstreamRepo -Files $hiddenFiles -Ref 'refs/fixture/hidden'

        $script:savedGitConfig = @{
            COUNT = $env:GIT_CONFIG_COUNT; KEY = $env:GIT_CONFIG_KEY_0; VALUE = $env:GIT_CONFIG_VALUE_0
        }
        $env:GIT_CONFIG_COUNT = '1'
        $env:GIT_CONFIG_KEY_0 = "url.file:///$($upstreamRepo.Replace('\', '/').TrimStart('/')).insteadOf"
        $env:GIT_CONFIG_VALUE_0 = $upstreamUrl

        function New-UpstreamEntry {
            param(
                [string] $Id = 'DEMO-RESEARCH',
                [string] $Path = 'skills/demo',
                [string] $Commit = $mainCommit,
                [string] $Repo = $upstreamUrl,
                [object[]] $Exclude = @('assets/'),
                [switch] $NoExclude,
                [switch] $WithRequires
            )
            $upstream = [ordered]@{ repo = $Repo; commit = $Commit; path = $Path; license = 'MIT' }
            if (-not $NoExclude) { $upstream['exclude'] = $Exclude }
            $entry = [ordered]@{
                id = $Id; version = '0.1.0'; source_path = "artifacts/$Id"
                upstream = $upstream
                applies_to = @{}; strength = 'on-demand'; topics = @('research'); scope = 'user'
                presentation = @{ name = 'Research a demo topic'; summary = 'Demo.'; benefits = @('Demo') }
            }
            if ($WithRequires) { $entry['requires'] = @{ tools = @('Python 3.12 or later') } }
            return $entry
        }

        function New-FixtureCatalog {
            <#
                A catalog checkout with one upstream entry, committed, plus a
                sentinel file already in the artifact's directory so a refusal
                can be shown to have left it alone.
            #>
            param([string] $Name, $Entry, [string] $GitAttributes = '')
            $root = Join-Path $TestDrive $Name
            [void](New-Item -ItemType Directory -Path $root)
            [void](Invoke-FixtureGit -Repository $root -Arguments @('init', '--quiet', '--initial-branch=main'))

            $index = [ordered]@{
                schema_version = '2'
                toolset_ref    = 'refs/tags/v0.1.0'
                vocabulary     = @{ languages = @('python'); frameworks = @(); layout = @(); agents = @(); topics = @('research') }
                artifacts      = @($Entry)
            }
            $json = ($index | ConvertTo-Json -Depth 10).Replace("`r`n", "`n")
            [System.IO.File]::WriteAllText((Join-Path $root 'index.json'), $json)
            [System.IO.File]::WriteAllText((Join-Path $root 'NOTICE'), "Upstream: $upstreamUrl`n")
            if ($GitAttributes) {
                [System.IO.File]::WriteAllText((Join-Path $root '.gitattributes'), $GitAttributes)
            }

            $artifactDirectory = Join-Path $root "artifacts/$($Entry.id)"
            [void](New-Item -ItemType Directory -Path $artifactDirectory)
            [System.IO.File]::WriteAllText((Join-Path $artifactDirectory 'SENTINEL.md'), "before`n")

            [void](Invoke-FixtureGit -Repository $root -Arguments @('add', '--all'))
            [void](Invoke-FixtureGit -Repository $root -Arguments @('commit', '--quiet', '-m', 'catalog'))
            return $root
        }

        function Save-Catalog {
            param([string] $Root, [string] $Message = 'sync')
            [void](Invoke-FixtureGit -Repository $Root -Arguments @('add', '--all'))
            [void](Invoke-FixtureGit -Repository $Root -Arguments @('commit', '--quiet', '--allow-empty', '-m', $Message))
        }

        function Get-Bytes {
            param([string] $Value)
            [System.Text.UTF8Encoding]::new($false).GetBytes($Value)
        }
    }

    AfterAll {
        $env:GIT_CONFIG_COUNT = $savedGitConfig.COUNT
        $env:GIT_CONFIG_KEY_0 = $savedGitConfig.KEY
        $env:GIT_CONFIG_VALUE_0 = $savedGitConfig.VALUE
    }

    Context 'syncing an artifact' {
        It 'copies the author files byte for byte, leaves out exclude, and adds UPSTREAM.json and the root LICENSE' {
            $root = New-FixtureCatalog -Name 'sync-ok' -Entry (New-UpstreamEntry)

            $result = & $sync -Id 'DEMO-RESEARCH' -CatalogRoot $root 6>$null

            $artifact = Join-Path $root 'artifacts/DEMO-RESEARCH'
            $result.LicenseAdded | Should -BeTrue
            $result.FileCount | Should -Be 3

            [System.IO.File]::ReadAllBytes((Join-Path $artifact 'SKILL.md')) |
                Should -Be (Get-Bytes $upstreamFiles['skills/demo/SKILL.md'])
            [System.IO.File]::ReadAllBytes((Join-Path $artifact 'references/guide.md')) |
                Should -Be (Get-Bytes $upstreamFiles['skills/demo/references/guide.md'])
            Test-Path -LiteralPath (Join-Path $artifact '.skillignore') | Should -BeTrue
            Test-Path -LiteralPath (Join-Path $artifact 'assets') | Should -BeFalse
            Test-Path -LiteralPath (Join-Path $artifact 'SENTINEL.md') | Should -BeFalse

            [System.IO.File]::ReadAllBytes((Join-Path $artifact 'LICENSE')) | Should -Be (Get-Bytes $rootLicense)

            $provenanceText = [System.IO.File]::ReadAllText((Join-Path $artifact 'UPSTREAM.json'))
            $provenanceText | Should -Not -Match "`r"
            $provenanceText | Should -Match "`n$"
            $provenance = $provenanceText | ConvertFrom-Json
            $provenance.repo | Should -Be $upstreamUrl
            $provenance.commit | Should -Be $mainCommit
            $provenance.path | Should -Be 'skills/demo'
            $provenance.license | Should -Be 'MIT'
            @($provenance.exclude) | Should -Be @('assets/')
            $provenance.synced_by | Should -Be 'scripts/sync-upstream.ps1'
        }

        It 'keeps a binary file byte for byte' {
            # Nothing is excluded here, so the CR, LF and NUL bytes of the binary
            # fixture have to survive the checkout and the copy.
            $root = New-FixtureCatalog -Name 'sync-binary' -Entry (New-UpstreamEntry -NoExclude)

            [void](& $sync -Id 'DEMO-RESEARCH' -CatalogRoot $root 6>$null)

            [System.IO.File]::ReadAllBytes((Join-Path $root 'artifacts/DEMO-RESEARCH/assets/demo.bin')) | Should -Be $binary
            ([System.IO.File]::ReadAllText((Join-Path $root 'artifacts/DEMO-RESEARCH/UPSTREAM.json')) | ConvertFrom-Json).PSObject.Properties['exclude'] |
                Should -BeNullOrEmpty
        }

        It 'keeps line endings exactly as the author committed them' {
            $root = New-FixtureCatalog -Name 'sync-crlf' -Entry (New-UpstreamEntry -Path 'skills/crlf' -NoExclude)

            [void](& $sync -Id 'DEMO-RESEARCH' -CatalogRoot $root 6>$null)

            [System.IO.File]::ReadAllBytes((Join-Path $root 'artifacts/DEMO-RESEARCH/SKILL.md')) |
                Should -Be (Get-Bytes $upstreamFiles['skills/crlf/SKILL.md'])
        }

        It "keeps the author's own LICENSE and adds none" {
            $root = New-FixtureCatalog -Name 'sync-own-license' -Entry (New-UpstreamEntry -Path 'skills/own-license' -NoExclude)

            $result = & $sync -Id 'DEMO-RESEARCH' -CatalogRoot $root 6>$null

            $result.LicenseAdded | Should -BeFalse
            [System.IO.File]::ReadAllBytes((Join-Path $root 'artifacts/DEMO-RESEARCH/LICENSE')) |
                Should -Be (Get-Bytes $upstreamFiles['skills/own-license/LICENSE'])
        }

        It 'fetches a pinned commit that no branch reaches' {
            $root = New-FixtureCatalog -Name 'sync-hidden' -Entry (New-UpstreamEntry -Commit $hiddenCommit)

            [void](& $sync -Id 'DEMO-RESEARCH' -CatalogRoot $root 6>$null)

            [System.IO.File]::ReadAllText((Join-Path $root 'artifacts/DEMO-RESEARCH/SKILL.md')) | Should -Match 'A later revision'
        }
    }

    Context 'refusing to sync' {
        It 'refuses <Case> and leaves the directory unchanged' -TestCases @(
            @{ Case = 'a path with no SKILL.md'; Path = 'skills/no-skill'; Exclude = $null; Expected = 'no SKILL.md at its root' }
            @{ Case = 'shipped scripts with no requires'; Path = 'skills/scripted'; Exclude = $null; Expected = "skills/scripted/scripts/run.py' is code to run" }
            @{ Case = 'a case collision'; Path = 'skills/collide'; Exclude = $null; Expected = "collides with .*Upstream file: 'skills/collide/" }
            @{ Case = 'a symbolic link'; Path = 'skills/linked'; Exclude = $null; Expected = "skills/linked/elsewhere.md' is a symbolic link" }
            @{ Case = 'an exclude that matches nothing'; Path = 'skills/demo'; Exclude = @('asset/'); Expected = "exclude item 'asset/' matches nothing" }
            @{ Case = 'a path that does not exist'; Path = 'skills/missing'; Exclude = $null; Expected = "nothing under 'skills/missing'" }
        ) {
            param($Case, $Path, $Exclude, $Expected)

            $entry = if ($null -eq $Exclude) { New-UpstreamEntry -Path $Path -NoExclude } else { New-UpstreamEntry -Path $Path -Exclude $Exclude }
            $root = New-FixtureCatalog -Name ('refuse-' + [guid]::NewGuid().ToString('N').Substring(0, 8)) -Entry $entry

            { & $sync -Id 'DEMO-RESEARCH' -CatalogRoot $root 6>$null } | Should -Throw -ExpectedMessage "*unchanged*"
            try { & $sync -Id 'DEMO-RESEARCH' -CatalogRoot $root 6>$null } catch { $_.Exception.Message | Should -Match $Expected }

            @(Get-ChildItem -LiteralPath (Join-Path $root 'artifacts/DEMO-RESEARCH') -Force).Name | Should -Be @('SENTINEL.md')
        }

        It 'refuses a commit that is not a full SHA before cloning anything' {
            # The repository does not exist anywhere: a clone attempt would fail
            # with a different message.
            $entry = New-UpstreamEntry -Commit 'main' -Repo 'https://github.com/fixture-owner/does-not-exist'
            $root = New-FixtureCatalog -Name 'refuse-branch' -Entry $entry

            { & $sync -Id 'DEMO-RESEARCH' -CatalogRoot $root 6>$null } |
                Should -Throw -ExpectedMessage "*'main' is not a full 40-character lower-case commit SHA*"
        }

        It 'refuses an artifact that has no upstream object' {
            $entry = New-UpstreamEntry
            $entry.Remove('upstream')
            $root = New-FixtureCatalog -Name 'refuse-not-upstream' -Entry $entry

            { & $sync -Id 'DEMO-RESEARCH' -CatalogRoot $root 6>$null } | Should -Throw -ExpectedMessage '*has no upstream object*'
        }

        It 'refuses an id the index does not have' {
            $root = New-FixtureCatalog -Name 'refuse-unknown' -Entry (New-UpstreamEntry)

            { & $sync -Id 'NOPE' -CatalogRoot $root 6>$null } | Should -Throw -ExpectedMessage '*Artifact NOPE is not in*'
        }
    }

    Context 'verifying committed artifacts' {
        It 'passes a freshly synced and committed artifact' {
            $root = New-FixtureCatalog -Name 'verify-ok' -Entry (New-UpstreamEntry)
            [void](& $sync -Id 'DEMO-RESEARCH' -CatalogRoot $root 6>$null)
            Save-Catalog -Root $root

            $result = & $sync -Verify -CatalogRoot $root 6>$null

            $result.Errors | Should -Be @()
            $result.IsValid | Should -BeTrue
            $result.ArtifactCount | Should -Be 1
        }

        It 'fails on <Case>, naming the file' -TestCases @(
            @{ Case = 'an edited file'; Change = { param($a) [System.IO.File]::AppendAllText((Join-Path $a 'SKILL.md'), "edited`n") }; Expected = 'artifacts/DEMO-RESEARCH/SKILL.md differs from' }
            @{ Case = 'an excluded file put back'; Change = { param($a) [void](New-Item -ItemType Directory -Path (Join-Path $a 'assets')); [System.IO.File]::WriteAllText((Join-Path $a 'assets/demo.bin'), 'x') }; Expected = 'assets/demo.bin is not in' }
            @{ Case = 'a missing file'; Change = { param($a) Remove-Item -LiteralPath (Join-Path $a 'references/guide.md') }; Expected = "skills/demo/references/guide.md' is in the pinned commit but missing" }
            @{ Case = 'a LICENSE nobody published'; Change = { param($a) [System.IO.File]::WriteAllText((Join-Path $a 'LICENSE'), "Our own words`n") }; Expected = "LICENSE differs from 'LICENSE' at the root" }
        ) {
            param($Case, $Change, $Expected)

            $root = New-FixtureCatalog -Name ('verify-' + [guid]::NewGuid().ToString('N').Substring(0, 8)) -Entry (New-UpstreamEntry)
            [void](& $sync -Id 'DEMO-RESEARCH' -CatalogRoot $root 6>$null)
            & $Change (Join-Path $root 'artifacts/DEMO-RESEARCH')
            Save-Catalog -Root $root

            $result = & $sync -Verify -CatalogRoot $root 6>$null

            $result.IsValid | Should -BeFalse
            @($result.Errors) -join "`n" | Should -Match ([regex]::Escape($Expected))
        }

        It 'reads HEAD, so an uncommitted edit does not hide a committed one or fail a clean commit' {
            $root = New-FixtureCatalog -Name 'verify-head' -Entry (New-UpstreamEntry)
            [void](& $sync -Id 'DEMO-RESEARCH' -CatalogRoot $root 6>$null)
            Save-Catalog -Root $root
            [System.IO.File]::AppendAllText((Join-Path $root 'artifacts/DEMO-RESEARCH/SKILL.md'), "uncommitted`n")

            (& $sync -Verify -CatalogRoot $root 6>$null).IsValid | Should -BeTrue
        }

        It "catches the catalog's .gitattributes normalising line endings, and passes once the artifact is -text" {
            # The case the spec names: an author's CRLF file committed under
            # '* text=auto' is stored with LF, so its blob id is no longer the
            # author's. The fix is an attribute, not an edit.
            $root = New-FixtureCatalog -Name 'verify-eol' -Entry (New-UpstreamEntry -Path 'skills/crlf' -NoExclude) `
                -GitAttributes "* text=auto`n"
            [void](& $sync -Id 'DEMO-RESEARCH' -CatalogRoot $root 6>$null)
            Save-Catalog -Root $root

            $before = & $sync -Verify -CatalogRoot $root 6>$null
            $before.IsValid | Should -BeFalse
            @($before.Errors) -join "`n" | Should -Match "add 'artifacts/DEMO-RESEARCH/\*\* -text'"

            [System.IO.File]::AppendAllText((Join-Path $root '.gitattributes'), "artifacts/DEMO-RESEARCH/** -text`n")
            [void](Invoke-FixtureGit -Repository $root -Arguments @('add', '--renormalize', 'artifacts/DEMO-RESEARCH'))
            Save-Catalog -Root $root -Message 'keep upstream bytes'

            $after = & $sync -Verify -CatalogRoot $root 6>$null
            $after.Errors | Should -Be @()
        }

        It 'fails an upstream entry with nothing committed under its directory' {
            $root = New-FixtureCatalog -Name 'verify-empty' -Entry (New-UpstreamEntry -Id 'OTHER-RESEARCH')
            # New-FixtureCatalog committed a sentinel under artifacts/OTHER-RESEARCH;
            # remove it so the directory has no committed files at all.
            [void](Invoke-FixtureGit -Repository $root -Arguments @('rm', '--quiet', '-r', 'artifacts/OTHER-RESEARCH'))
            Save-Catalog -Root $root

            $result = & $sync -Verify -CatalogRoot $root 6>$null

            $result.IsValid | Should -BeFalse
            @($result.Errors) -join "`n" | Should -Match 'has no committed files under artifacts/OTHER-RESEARCH'
        }

        It 'verifies nothing, and passes, when no entry is upstream' {
            $entry = New-UpstreamEntry
            $entry.Remove('upstream')
            $root = New-FixtureCatalog -Name 'verify-none' -Entry $entry

            $result = & $sync -Verify -CatalogRoot $root 6>$null

            $result.IsValid | Should -BeTrue
            $result.ArtifactCount | Should -Be 0
        }
    }
}
