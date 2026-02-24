# 🔬 GeoFund Copilot

> 地球科学基金申请智能文献助手  
> Intelligent Literature Assistant for Earth Science Grant Applications

[![Python](https://img.shields.io/badge/python-≥3.9-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

GeoFund Copilot 帮助地球科学研究人员快速找到高质量参考文献，检查创新点新颖度。

## ✨ 核心功能

| 功能 | 说明 |
|------|------|
| **📚 智能文献推荐** | 输入研究方向 → 按"必引经典/前沿进展/方法借鉴/潜在评审人"四类推荐 |
| **🔬 创新点查重** | 输入创新点 → 4 维度重叠分析 + 新颖度评分 + 改写建议 |
| **📎 引用格式化** | GB/T 7714 / BibTeX / APA 一键输出 |

## 🔧 技术特点

- **127 万篇论文** — OpenAlex 地球科学全量数据，BGE 向量语义检索
- **双源检索** — Qdrant 语义匹配 + CrossRef 实时补充，覆盖最新论文
- **Critic Agent** — CrossRef DOI 验证，杜绝 LLM 编造文献

## 📦 快速开始

### 独立 CLI（开发调试）

```bash
# 安装依赖
pip install -r requirements.txt

# 设置 DeepSeek API Key
export DEEPSEEK_API_KEY=sk-xxx

# 文献推荐
python scripts/recommend.py "用图神经网络预测珠江流域溶解氧浓度"

# 创新点查重
python scripts/novelty_check.py "结合GATCN和GNNExplainer实现可解释的溶解氧预测"

# 引用格式化
python scripts/format_refs.py --doi "10.1016/j.watres.2023.120001" --style gbt7714

# 交互式 Demo
python scripts/copilot_demo.py
```

## 📁 项目结构

```
geofund/
├── geomind_sdk/                  # 核心 SDK
│   ├── client.py                 # Qdrant Cloud 连接
│   ├── search.py                 # BGE 语义检索 + 过滤
│   ├── crossref.py               # CrossRef API (检索 + DOI 验证)
│   ├── copilot.py                # 文献推荐 Agent
│   ├── novelty.py                # 创新点查重
│   ├── formatter.py              # 引用格式化
│   └── metadata.py               # 元数据查询
│
├── scripts/                      # 可执行脚本
│   ├── recommend.py              # 文献推荐入口
│   ├── novelty_check.py          # 创新点查重入口
│   ├── format_refs.py            # 引用格式化入口
│   ├── copilot_demo.py           # 交互式 Demo
│   ├── create_indexes.py         # Qdrant 索引创建
│   └── inspect_data.py           # 数据检查
│
├── config/                       # 配置模板
│   └── config.example.json       # SDK 配置
│
├── tests/                        # 测试
├── requirements.txt              # 依赖
└── README.md
```

## 🏗️ 架构

```
用户输入 (CLI / API)
    │
    ▼
GeoFund SDK
    │
    ├── Planner (DeepSeek) → 4-6 条检索策略
    ├── Retriever → Qdrant (127万) + CrossRef (实时)
    ├── Ranker (DeepSeek) → 4 类分类 + 拒绝能力
    └── Critic → CrossRef DOI 验证
```

## 📊 数据源

| 来源 | 论文数 | 用途 |
|------|--------|------|
| Qdrant (OpenAlex) | 1,272,896 | 语义向量检索，覆盖历史论文 |
| CrossRef | 全网实时 | 补充最新论文 + DOI 验证 |

论文包含 17 个字段：标题、摘要、作者、期刊、年份、引用数、CAS/JCR 分区、概念标签等。

## ⚙️ 配置

| 服务 | 获取方式 | 说明 |
|------|---------|------|
| **DeepSeek API** | https://platform.deepseek.com | LLM 推理（Planner/Ranker/Evaluator） |
| **Qdrant Cloud** | 内置公共 Key | 体验期至 2026-03-15 |
| **CrossRef** | 无需 Key | Polite Pool 自动生效 |

## 🗺️ 路线图

- [x] **v0.1** — SDK 核心
- [ ] **v0.2** — Memory 利用 + 研究趋势分析
- [ ] **v0.3** — 每周新论文推送 (Cron + CrossRef)
- [ ] **v0.4** — 投稿选刊建议 + 综述段落生成

## 📜 License

MIT

## 🔗 相关项目

- [Ai4earthscience](https://mp.weixin.qq.com/s/xxx) — 微信公众号 (3000+ 关注)
- [GeoMind](https://github.com/xxx) — AI 地球科学研究助手
