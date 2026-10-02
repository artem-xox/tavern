# PixelLab

Research snapshot: 2026-10-01; connection and 68 px character workflow verified 2026-10-02. PixelLab generates 4- or 8-direction characters, animations, transparent props, and connected terrain tilesets. Characters can be exported as sprite sheets or individual frames for Phaser. Generation runs as background jobs; expect minutes rather than instant results. Review every direction before using it in game. See the [tested character pipeline](../CHARACTER_ART_PIPELINE.md). [MCP tools](https://www.pixellab.ai/mcp) · [Exports](https://www.pixellab.ai/docs/ways-to-use-pixellab)

## Access and pricing

- Official remote MCP: `https://api.pixellab.ai/mcp`, authenticated with a PixelLab bearer token. A REST v2 API is also available. The account is connected and Tier 1 was verified with `get_balance` on 2026-10-02. [MCP guide](https://api.pixellab.ai/mcp/docs)
- At verification, Tier 1 reported 2,000 generations for the cycle ending 2026-11-02. Check `get_balance` before a batch; capacity and tool costs can change. The [68 px character experiment](../CHARACTER_ART_PIPELINE.md) records measured base and state costs. [Current plans](https://www.pixellab.ai/?tier=0) · [API estimates](https://www.pixellab.ai/pixellab-api)

## Connect to Codex

Get a token from [PixelLab's MCP page](https://www.pixellab.ai/mcp), then add this to the user's `~/.codex/config.toml` (never commit the token):

```toml
[mcp_servers.pixellab]
url = "https://api.pixellab.ai/mcp"
http_headers = { Authorization = "Bearer YOUR_PIXELLAB_TOKEN" }
```

Restart Codex and check `/mcp`. The installed Codex CLI supports this remote HTTP endpoint directly. [Codex MCP documentation](https://learn.chatgpt.com/docs/extend/mcp)
