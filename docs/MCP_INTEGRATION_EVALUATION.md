# Git-Doc-Hook MCP 集成方案技术评估报告

**评估日期**: 2025-02-24
**评估范围**: memos-local MCP 客户端集成方式
**评估方法**: MCP 官方文档调研、标准客户端库分析、替代方案对比

---

## 执行摘要

**关键发现**：
1. MCP 协议有标准的 Python 客户端库 (`mcp[cli]`)
2. 当前方案的"调用栈检测"非常规，仅在被 Claude Code 调用时有效
3. 存在更标准的替代方案，但需要额外的依赖配置
4. 离线缓存机制是合理的设计模式

**推荐方案**: 保持当前方案（方案 B 改进版），但添加明确的环境检测和日志提示

---

## 一、MCP 协议标准调研

### 1.1 官方 Python SDK

根据搜索结果，MCP 官方提供了 Python SDK：

```bash
pip install "mcp[cli]"
```

**核心组件**：
- `ClientSession` - 会话管理
- `StdioServerParameters` - stdio 传输配置
- `streamablehttp_client` - HTTP 传输支持
- `stdio_client` - 本地进程通信

**标准客户端实现示例**：
```python
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

async def main():
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"],
    )
    async with stdio_client(server_params) as (stdio, write):
        async with ClientSession(stdio, write) as session:
            await session.initialize()
            result = await session.call_tool("tool_name", {"param": "value"})
```

### 1.2 MCP 传输方式

| 传输方式 | 协议 | 适用场景 | 优势 | 局限 |
|---------|------|----------|------|------|
| **stdio** | 标准输入/输出 | 本地进程通信 | 零配置、低延迟 | 只能本地使用 |
| **SSE** | Server-Sent Events | 单向实时推送 | 支持流式响应 | 已被 Streamable HTTP 取代 |
| **Streamable HTTP** | HTTP POST + SSE | 远程/分布式 | 支持远程、多客户端 | 需要网络配置 |

### 1.3 MCP 架构角色

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MCP Host (主机)                              │
│  - Claude Code / Claude Desktop / VS Code / Cursor                 │
│  - 协调和管理 MCP 客户端                                            │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│                    MCP Client (客户端)                              │
│  - 维护与 Server 的 1:1 连接                                         │
│  - 获取工具列表、调用工具、管理会话                                   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                │ stdio / HTTP
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│                    MCP Server (服务器)                              │
│  - 提供工具、资源、提示词                                            │
│  - memos-local, filesystem, github 等                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、当前方案根本性评估

### 2.1 当前实现分析

当前 `src/git_doc_hook/memos/client.py` 使用**调用栈检测**方式：

```python
def _detect_mcp_available(self) -> bool:
    import inspect
    frame = inspect.currentframe()
    while frame:
        frame_locals = frame.f_locals
        if "mcp__memos-local__add_message" in frame_locals:
            return True
        frame = frame.f_back
    return False
```

### 2.2 为什么选择这种方案？

| 原因 | 说明 |
|------|------|
| **零依赖** | 无需安装 `mcp` SDK，保持轻量级 |
| **自动降级** | MCP 不可用时自动使用离线缓存 |
| **简化部署** | 用户无需配置 MCP 服务器地址 |
| **钩子友好** | Git hooks 调用时无需额外配置 |

### 2.3 核心问题

| 问题 | 影响 | 严重程度 |
|------|------|----------|
| **仅在被 Claude Code 调用时有效** | 独立 CLI 运行时无法使用 MCP | 高 |
| **非常规实现** | 难以维护，可能与未来版本不兼容 | 中 |
| **无法测试** | 单元测试中无法模拟 MCP 环境 | 中 |
| **依赖调用栈约定** | 工具函数命名变化会导致失效 | 低 |

### 2.4 运行场景分析

| 场景 | MCP 可用 | 离线缓存 | 当前方案 |
|------|----------|----------|----------|
| Claude Code 中调用 `git-doc-hook` | ✅ | - | ✅ 正常工作 |
| Git hook 触发 `git-doc-hook update` | ❌ | ✅ | ⚠️ 仅缓存 |
| 用户直接运行 `git-doc-hook memos-sync` | ❌ | ✅ | ⚠️ 仅缓存 |
| CI/CD 环境中运行 | ❌ | ✅ | ⚠️ 仅缓存 |

---

## 三、替代方案对比

### 方案 A：使用标准 MCP 客户端库

**实现方式**：
```python
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

class MemOSClient:
    def __init__(self, server_command: str = None):
        if server_command:
            self.server_params = StdioServerParameters(
                command="npx",
                args=["-y", "@memos-local/mcp-server"],
            )

    async def _connect_mcp(self):
        async with stdio_client(self.server_params) as (stdio, write):
            async with ClientSession(stdio, write) as session:
                await session.initialize()
                return session
```

**优点**：
- ✅ 标准实现，可维护性高
- ✅ 独立于调用环境，可独立运行
- ✅ 可编写单元测试
- ✅ 支持远程 MCP 服务器

**缺点**：
- ❌ 需要安装 `mcp[cli]` 依赖（~5MB）
- ❌ 用户需要配置 memos-local 服务器路径
- ❌ 需要异步编程改造
- ❌ 增加部署复杂度

**实现成本**: 中等 (~200 行代码)

---

### 方案 B：保持当前方案，改进检测逻辑

**改进点**：
1. 添加环境变量检测 (`MCP_AVAILABLE=true`)
2. 改进日志提示
3. 添加手动同步命令
4. 文档明确说明使用场景

**实现方式**：
```python
def _detect_mcp_available(self) -> bool:
    # 1. 环境变量优先
    if os.environ.get("GIT_DOC_HOOK_MCP_ENABLED") == "true":
        return True

    # 2. 调用栈检测（现有逻辑）
    if self._detect_mcp_in_stack():
        return True

    return False

def _detect_mcp_in_stack(self) -> bool:
    """检测是否在 Claude Code 环境中运行"""
    try:
        import inspect
        frame = inspect.currentframe()
        while frame:
            if "mcp__memos-local__add_message" in frame.f_locals:
                logger.info("检测到 Claude Code MCP 环境")
                return True
            frame = frame.f_back
    except Exception:
        pass
    return False
```

**优点**：
- ✅ 保持零依赖
- ✅ 保持自动降级能力
- ✅ 改进用户体验（明确提示）
- ✅ 迁移成本低

**缺点**：
- ❌ 仍然非常规实现
- ❌ 独立 CLI 时无法使用 MCP
- ❌ 依赖调用栈约定

**实现成本**: 低 (~50 行代码)

---

### 方案 C：双模式分离

**架构设计**：
```
┌────────────────────────────────────────────────────────────────┐
│                    git-doc-hook CLI                            │
├─────────────────────────────────────┬──────────────────────────┤
│        CLI Mode (默认)              │      MCP Mode            │
│  - 只使用离线缓存                    │  - 尝试连接 MCP          │
│  - `git-doc-hook memos-sync`        │  - 实时同步              │
│  - 适合 Git hooks / CI/CD           │  - 适合 Claude Code      │
└─────────────────────────────────────┴──────────────────────────┘
```

**实现方式**：
```python
class MemOSClient:
    def __init__(self, mode: str = "auto"):
        self.mode = self._detect_mode(mode)

    def _detect_mode(self, mode: str) -> str:
        if mode == "auto":
            return "mcp" if self._detect_mcp_in_stack() else "cli"
        return mode

    def add_record(self, record):
        if self.mode == "mcp" and self._mcp_available:
            return self._mcp_add_message(record)
        else:
            self._offline_cache.append(record)
            logger.info("CLI 模式：记录已缓存，使用 `git-doc-hook memos-sync` 同步")
```

**优点**：
- ✅ 清晰的模式分离
- ✅ 用户可选行为
- ✅ 兼顾两种使用场景

**缺点**：
- ❌ 增加配置复杂度
- ❌ 可能造成用户困惑
- ❌ 需要额外的命令行参数

**实现成本**: 中等 (~100 行代码)

---

### 方案 D：独立同步命令

**设计思路**：
- CLI 主命令只使用离线缓存
- 提供 `git-doc-hook memos-sync` 命令
- 在 Claude Code 中可手动触发同步

**实现方式**：
```python
# CLI 默认行为
def add_record(self, record):
    self._offline_cache.append(record)
    self._save_cache()
    logger.info(f"记录已缓存 (共 {len(self._offline_cache)} 条待同步)")

# 新增同步命令
@click.command()
def memos_sync():
    """同步离线缓存到 MemOS"""
    client = MemOSClient()
    synced = client.sync_offline_cache()
    click.echo(f"已同步 {synced} 条记录到 MemOS")
```

**优点**：
- ✅ 职责清晰，易于理解
- ✅ 用户完全控制同步时机
- ✅ 简化主流程

**缺点**：
- ❌ 需要用户手动操作
- ❌ 丢失自动同步能力
- ❌ 用户体验可能下降

**实现成本**: 低 (~30 行代码)

---

## 四、替代方案对比表

| 维度 | 方案 A (标准库) | 方案 B (改进当前) | 方案 C (双模式) | 方案 D (独立同步) |
|------|----------------|------------------|----------------|------------------|
| **依赖** | mcp[cli] | 无 | 无 | 无 |
| **独立运行** | ✅ | ❌ | ❌ | ❌ |
| **Claude Code 集成** | ✅ | ✅ | ✅ | ⚠️ 手动 |
| **可测试性** | ✅ | ❌ | ❌ | ✅ |
| **实现成本** | 中 | 低 | 中 | 低 |
| **维护成本** | 低 | 中 | 中 | 低 |
| **用户体验** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **技术债务** | 低 | 中 | 中 | 低 |

---

## 五、技术决策建议

### 推荐：方案 B（改进当前方案）

**理由**：

1. **符合项目定位**
   - Git-Doc-Hook 的核心价值是 Git 集成，不是 MCP 客户端
   - MemOS 集成是辅助功能，不应增加主要依赖

2. **用户体验优先**
   - 零配置、自动降级对最终用户最友好
   - 大多数用户只在 Claude Code 中使用 MCP 功能

3. **现实约束**
   - 方案 A 会显著增加依赖和部署复杂度
   - MCP 生态仍在快速演进，过早标准化可能锁定特定实现

### 改进措施

1. **改进检测逻辑**
   ```python
   def _detect_mcp_available(self) -> bool:
       # 1. 环境变量显式控制
       if os.environ.get("GIT_DOC_HOOK_MCP_ENABLED") == "true":
           return True
       if os.environ.get("GIT_DOC_HOOK_MCP_ENABLED") == "false":
           return False

       # 2. 调用栈自动检测
       return self._detect_mcp_in_stack()
   ```

2. **添加明确的日志提示**
   ```python
   if not self._mcp_available:
       logger.info(
           "MCP 未检测到，使用离线缓存模式。"
           "如需同步，运行: git-doc-hook memos-sync"
       )
   ```

3. **改进文档**
   - 明确说明 MCP 功能只在 Claude Code 中可用
   - 提供 memos-sync 命令使用指南
   - 添加故障排除部分

4. **保持向后兼容**
   - 离线缓存机制继续作为核心功能
   - 确保在没有 MCP 的环境中正常工作

---

## 六、迁移路径（如需切换到方案 A）

如果未来需要切换到标准 MCP 客户端：

### 阶段 1：准备（1-2 天）
1. 添加 `mcp[cli]` 到可选依赖
2. 创建新的 `StandardMCPClient` 类
3. 编写单元测试

### 阶段 2：并行运行（1 周）
1. 保持现有调用栈检测
2. 在检测失败时尝试标准客户端
3. 收集性能和兼容性数据

### 阶段 3：完全迁移（1 天）
1. 移除调用栈检测代码
2. 更新文档和配置示例
3. 发布版本说明

### 回滚计划
- 保留离线缓存作为备份
- 通过配置项可快速回退到旧方案

---

## 七、附录

### A. MCP 相关资源

| 资源 | 链接 |
|------|------|
| 官方 Python SDK | https://github.com/modelcontextprotocol/python-sdk |
| MCP 规范 | https://modelcontextprotocol.io/specification/ |
| FastMCP 框架 | https://github.com/jlowin/fastmcp |
| memos-local | Claude Code 内置 MCP 服务器 |

### B. 关键代码位置

| 文件 | 功能 | 关键函数 |
|------|------|----------|
| `src/git_doc_hook/memos/client.py` | MCP 客户端 | `_detect_mcp_available()`, `_mcp_add_message()` |
| `src/git_doc_hook/cli.py` | CLI 入口 | `memos_sync()` 命令 |
| `examples/.git-doc-hook.yml` | 配置示例 | memos 配置节 |

### C. 测试建议

```python
# 测试 MCP 检测逻辑
def test_mcp_detection_in_claude_code():
    """在模拟的 Claude Code 环境中测试"""
    # 模拟调用栈
    client = MemOSClient()
    assert client._detect_mcp_available() == True

def test_mcp_detection_standalone():
    """在独立环境中测试"""
    client = MemOSClient()
    assert client._detect_mcp_available() == False

def test_offline_cache_fallback():
    """测试离线缓存降级"""
    client = MemOSClient(enabled=True)
    record = MemOSRecord(content="test")
    assert client.add_record(record) == False  # 缓存到本地
    assert len(client._offline_cache) == 1
```

---

## 八、结论

**当前 MCP 集成方案是合理的，但需要改进文档和用户提示。**

核心改进方向：
1. 添加环境变量控制机制
2. 改进日志提示，让用户清楚当前工作模式
3. 在文档中明确说明 MCP 功能的使用场景和限制
4. 保持离线缓存作为核心功能，确保在所有场景下可用

**长期考虑**：如果 MCP 生态稳定且用户有独立运行需求，可以考虑迁移到方案 A（标准客户端库），但需要权衡增加的依赖和复杂度。

---

**报告编写**: Claude Opus
**审核建议**: 请项目维护者根据实际使用情况调整决策
