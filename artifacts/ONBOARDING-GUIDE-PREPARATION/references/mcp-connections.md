# Finding MCP servers and proposing connections

Read this while establishing which of the three access states each source is in
(see [What the agent can reach, and what to
propose](../SKILL.md#what-the-agent-can-reach-and-what-to-propose)), before
marking any source "not set up" and before the guide proposes a connection.

## Finding every configured MCP server

The project's own files show only part of what the agent can connect to. A server
installed through a plugin lives in that plugin's directory, and a connector added
to the person's account lives in the account, so neither appears in the
repository's `.mcp.json` or settings. A survey that reads only the project's files
marks such a source "not set up" while the reader already has a working server for
it, and the guide then proposes installing a second one beside it: two servers for
the same tracker, possibly with different access. So look in every place a server
can be declared. For Claude Code these are:

- **Project scope:** `.mcp.json` at the repository root, and in
  `.claude/settings.json` and `.claude/settings.local.json` which of its servers
  are approved or disabled (`enableAllProjectMcpServers`, `enabledMcpjsonServers`,
  `disabledMcpjsonServers`). An unapproved server is configured but not connected.
- **User and local scope:** `~/.claude.json`, where `mcpServers` at the top level
  is the user scope and `projects["<path>"].mcpServers` is the local scope for this
  repository only. `~/.claude/settings.json` holds the user's approvals.
- **Plugins:** the plugins enabled in `enabledPlugins` in any of the three settings
  files above. Look each up in `~/.claude/plugins/installed_plugins.json`, which
  gives its install path, and read the `.mcp.json` at that path or the
  `mcpServers` entry in its `.claude-plugin/plugin.json`, which is either the
  servers themselves or a path to a file holding them. Read the installed path
  only: the plugin cache keeps old versions beside it, and their servers are not
  loaded. A plugin that is installed but not enabled contributes nothing.
- **Managed settings** an administrator deploys, such as `managed-mcp.json`, which
  the person cannot change and the guide reports as fixed.

If `CLAUDE_CONFIG_DIR` is set, the user-level files are there instead of in
`~/.claude`. Where the CLI is available, `claude mcp list` gives the merged result
of all of these, plus account connectors, with each server's status. It starts each
approved server to check its health, so run it with the person's agreement, and
use it to confirm the file survey rather than replace it: it does not say where a
server was declared. Other agents have the same layers under their own names, such
as `.cursor/mcp.json` and `~/.cursor/mcp.json`, `.codex/config.toml` and
`~/.codex/config.toml`, and `.vscode/mcp.json`.

These files often hold tokens in `env` or `headers`. Read the server names, types,
commands and URLs; never print or copy the values of environment variables or
headers.

## Proposing a connection

For the second and third states, the guide proposes the connection. State what it
would give, in terms of this project: "with the tracker connected, the agent can
read the ticket behind a branch and the acceptance criteria before a change". Name
the least access that achieves it, which for onboarding is read-only: browse the
project, read pages. Then say how the connection is made for the agent in use, an
MCP server or a connector, depending on the agent.

Prefer a server that is already configured, in the project's files, the person's
settings or an enabled plugin: fixing its sign-in is one step, and a second server
for the same source is one more thing to keep apart. Among new ones, prefer what
the project's configuration already declares, because the team has agreed to it.
Next comes the server or connector published by the vendor of the source. Do not
name a third-party package from memory. A newcomer follows an onboarding guide
literally, so a wrong or look-alike package name in one is an
installation waiting to happen. If the right one is not known, write "ask the team
which integration is approved".

Setting it up is the reader's action, sometimes their lead's. Tokens are personal,
and on client projects whether a tracker or wiki may be connected to an agent at
all is a decision somebody has already made or needs to make. Put that question in
the guide where it is open.
