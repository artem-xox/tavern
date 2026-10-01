# PixelLab

Research snapshot: 2026-10-01. PixelLab is a plausible asset tool for *The Last Inn*'s top-down prototype. It generates 4- or 8-direction characters, animations, transparent props, and connected terrain tilesets. Characters can be exported as sprite sheets or individual frames for Phaser. Generation runs as background jobs; expect minutes rather than instant results. Review and touch up animation frames before using them in game. [MCP tools](https://www.pixellab.ai/mcp) · [Exports](https://www.pixellab.ai/docs/ways-to-use-pixellab) · [Animation workflow](https://www.pixellab.ai/docs/tools/animation)

## Access and pricing

- Official remote MCP: `https://api.pixellab.ai/mcp`, authenticated with a PixelLab bearer token. A REST v2 API is also available. PixelLab is **not yet connected or tested** in this project. [MCP guide](https://api.pixellab.ai/mcp/docs)
- The free trial lists 40 fast generations, then 5 slower daily generations. Apprentice is **$12/month** with a 2,000-image monthly limit and unlocks map and fuller animation tools; Artisan is **$24/month** with a 5,000-image limit. PixelLab's pricing page advertises MCP on the free tier, but its usage guide says MCP needs an active subscription; verify account access before relying on the free tier. [Plans](https://www.pixellab.ai/?tier=0) · [Usage guide](https://www.pixellab.ai/docs/ways-to-use-pixellab)
- For **20 characters × 10 animation types**, assuming 64×64 sprites, four frames, one usable attempt, and PixelLab's v3 API estimates: **$11.14 nominal work for four animated directions** or **$21.46 for eight**. These are API price estimates, not charges to add to a subscription. Retries, larger generated canvases, and more frames raise usage. Pilot one character with all actions before budgeting the batch. [API estimates](https://www.pixellab.ai/pixellab-api) · [Generation rules](https://api.pixellab.ai/mcp/docs)

## Connect to Codex

Get a token from [PixelLab's MCP page](https://www.pixellab.ai/mcp), then add this to the user's `~/.codex/config.toml` (never commit the token):

```toml
[mcp_servers.pixellab]
url = "https://api.pixellab.ai/mcp"
http_headers = { Authorization = "Bearer YOUR_PIXELLAB_TOKEN" }
```

Restart Codex and check `/mcp`. The installed Codex CLI supports this remote HTTP endpoint directly. [Codex MCP documentation](https://learn.chatgpt.com/docs/extend/mcp)
