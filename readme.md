# PaperMiner - AI-Powered Paper Research Assistant

基于 PyQt6 的本地论文管理 + AI 研究助手。

## 项目架构

```
main.py                          # 入口 + 环境配置
config.py                        # 全局配置 (API Keys, 模型选择, 路径)
core/
    database.py                  # SQLite 数据库管理
    models.py                    # 数据模型 (Folder, Paper, Annotation, TextChunk...)
ui/
    main_window.py               # 主窗口 (侧边栏导航 + QStackedWidget)
    manage_view.py               # 管理论文 视图
    mine_view.py                 # 挖掘论文 视图
    pdf_viewer.py                # PDF.js 查看器 (QWebChannel 双向桥接)
    ai_sidebar.py                # 可折叠 AI 对话侧边栏
    components.py                # 可复用 UI 组件 + 全局暗色主题
ai/
    llm_client.py                # 抽象 LLM 客户端 (DeepSeek/智谱/SiliconFlow/OpenAI)
    rag_engine.py                # RAG 引擎 (PDF提取 -> 分块 -> 嵌入 -> 余弦检索)
    chat_handler.py              # 对话管理 (论文对话 / 知识库对话 / 翻译)
discovery/
    arxiv_client.py              # ArXiv API 搜索
    hf_client.py                 # HuggingFace 每日论文 (hf-mirror.com)
    agent.py                     # AI 推荐代理 (查询 -> 搜索 -> 总结)
workers/
    async_workers.py             # QThread 异步线程 (Chat/Index/Search/Download)
resources/
    viewer_bridge.html           # PDF.js 桥接 HTML
    bridge.js                    # QWebChannel <-> PDF.js 通信脚本
```

## 环境准备

```bash
conda create -n paperminer python=3.10
conda activate paperminer
```

## 安装依赖

```bash
pip install PyQt6 PyQt6-WebEngine pymupdf httpx
# 可选: 本地嵌入模型
pip install sentence-transformers
```

## 配置

首次运行自动生成 settings.json，编辑配置 API Key:

```json
{
  "llm": {
    "provider": "deepseek",
    "api_key": "your-api-key",
    "base_url": "https://api.deepseek.com/v1",
    "model_name": "deepseek-chat"
  }
}
```

## 启动

```bash
python main.py
```
