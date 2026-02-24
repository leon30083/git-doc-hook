# MemOS Sync Command

Sync MemOS records from git-doc-hook pending state to MemOS via MCP.

## When to Use

Run this command after:
- `git-doc-hook update memo` - Creates MemOS records from commits
- `git-doc-hook status` shows "MemOS: N record(s) pending sync"

## Usage

```bash
/memos-sync
```

## What It Does

1. Calls `git-doc-hook check-memos --json` to get pending records
2. Displays a summary of records (count, type, commit message)
3. Asks for user confirmation before syncing
4. Syncs each record to MemOS via `mcp__memos-local__add_message`
5. Clears synced records from pending state

## Output

### No Pending Records

```
没有待同步的 MemOS 记录
```

### Has Pending Records

```
待同步记录: 3 条

1. [troubleshooting] fix: resolve race condition in auth
2. [adr] decision: use Redis for caching layer
3. [practice] refactor: extract service layer

是否同步以上 3 条记录？[y/N]
```

### After Syncing

```
✓ 同步完成: 成功 3 条 / 失败 0 条
```

### MCP Not Available

```
✗ MemOS MCP 工具不可用
请确保 memos-local MCP 服务器已连接
记录保留在 pending.json 中，可在 MCP 可用时重试
```

## Implementation Notes

- Requires `mcp__memos-local__add_message` MCP tool
- Failed records are kept in pending.json for retry
- Records are only cleared after successful MCP sync
- User confirmation is required before any MCP calls

## Deployment Guide

### When memos-local Tool is Unavailable

If the MCP tool is not configured, you'll see:

```
✗ MemOS MCP 工具不可用
请确保 memos-local MCP 服务器已连接
```

### Option A: Local Deployment (Recommended, Private Data)

1. **Run MemOS with Docker**:
   ```bash
   docker run -d \
     --name memos \
     -p 5230:5230 \
     -v ~/.memos/:/var/opt/memos \
     neosmemo/memos:stable
   ```

2. **Initialize**:
   - Visit http://localhost:5230
   - Create your account

3. **Generate API Key**:
   - Go to Settings → Account Security
   - Click "Generate OpenAPI Key"
   - Copy the key

4. **Configure MCP**:
   Add to your MCP settings:
   ```
   MEMOS_BASE_URL=http://localhost:5230
   MEMOS_API_TOKEN=<your-key>
   ```

### Option B: Official Online Version

1. **Register**: Visit https://www.usememos.com/
2. **Get Instance URL**: Your instance URL (e.g., https://your-instance.usememos.com)
3. **Generate API Key**: Settings → Account Security → Generate OpenAPI Key
4. **Configure MCP**:
   ```
   MEMOS_BASE_URL=<your-instance-url>
   MEMOS_API_TOKEN=<your-key>
   ```

### Install MCP Server

After MemOS is running, install the MCP server:

```bash
# Via npx
npx @modelcontextprotocol/create-server memos-local

# Or via pip
pip install mcp-server-memos
```

Restart Claude Code and run `/memos-sync` again.
