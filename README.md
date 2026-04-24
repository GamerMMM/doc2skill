# doc2skill 项目总览

这个仓库用于把“官方文档入口链接”抽象为可复用的 Skill 生成流程。

你可以把它理解为一个两层结构：
- 外层仓库：承载版本管理、虚拟环境和总入口文档。
- 内层工程（`project/`）：真正可安装、可测试、可执行的 Python 包。

---

## 1. 仓库结构（全局）

```text
doc2skill/
├── .git/                       # Git 元数据
├── .gitattributes              # Git 属性配置
├── .gitignore                  # Git 忽略规则
├── .venv/                      # 本地 Python 虚拟环境
├── LICENSE                     # 许可证
├── README.md                   # 当前文档（仓库级总览）
├── pyrightconfig.json          # 仓库级类型检查配置
└── project/                    # 业务核心工程（可安装包）
```

说明：日常开发与运行主要在 `project/` 内进行。

---

## 2. 核心工程结构（project/）

```text
project/
├── .env.example
├── README.md
├── SKILL.md
├── pyproject.toml
├── pyrightconfig.json
├── skill.manifest.json
├── schema/
│   ├── .gitkeep
│   └── openapi.json
├── src/
│   └── novae_skill/
│       ├── __init__.py
│       ├── cli.py
│       ├── diagnostics.py
│       ├── runtime.py
│       └── spec.py
├── tests/
│   ├── conftest.py
│   ├── notebook_tests.ipynb
│   ├── test_runtime.py
│   └── test_spec.py
└── examples/
		├── zero_shot.py
		├── fine_tune.py
		└── multimodal.py
```

---

## 3. 分层职责与逻辑

### 3.1 契约层（Schema + 规格）
- `src/novae_skill/spec.py`
	- 定义核心数据模型：`PageRecord`、`CapabilityRecord`、`SkillConstraint`、`SkillPackagePlan`。
	- 定义工作流动作集合 `CORE_ACTIONS`（7 个动作）。
	- 提供 `build_openapi_spec()` 生成 OpenAPI 风格契约。
	- 提供 `dump_openapi_spec()` 把契约写入 `schema/openapi.json`。

- `schema/openapi.json`
	- 由 `spec.py` 生成或更新。
	- 是 Agent/调用方可消费的“动作接口说明”。

### 3.2 执行层（Runtime）
- `src/novae_skill/runtime.py`
	- 对外统一入口：`dispatch_action(action_name, payload)`。
	- 内部按动作名路由到对应处理函数。
	- 各动作以“纯数据转换”为核心，不耦合特定第三方产品 API。

### 3.3 诊断层（Diagnostics）
- `src/novae_skill/diagnostics.py`
	- 将常见失败模式映射为结构化诊断与建议。
	- 用于在生成/验证阶段快速定位问题。

### 3.4 命令行层（CLI）
- `src/novae_skill/cli.py`
	- 提供 `docskill-factory` 脚本入口（定义在 `pyproject.toml`）。
	- 支持输出契约、输出默认文件树、写入 schema 文件。

### 3.5 测试与示例层
- `tests/`
	- `test_spec.py`：验证契约与默认常量。
	- `test_runtime.py`：验证运行时动作链。
	- `notebook_tests.ipynb`：Notebook 形态的流程回归检查。

- `examples/`
	- 提供最小可运行样例，展示页面分类、包计划与包验证。

---

## 4. 核心动作链（运行顺序）

项目的逻辑主线是一个 7 步动作流水线：

1. `discover_document_pages`
2. `classify_document_pages`
3. `extract_document_capabilities`
4. `normalize_capabilities`
5. `design_skill_package`
6. `generate_skill_files`
7. `validate_skill_package`

### 4.1 每一步的输入输出关系

1) 页面发现
- 输入：入口链接、候选链接、导航线索。
- 输出：标准化页面目录（page catalog）。

2) 页面分类
- 输入：页面目录。
- 输出：纳入页面 / 排除页面及计数。

3) 能力抽取
- 输入：页面证据、目标语言、约束。
- 输出：能力列表（capabilities）。

4) 能力归一
- 输入：能力列表。
- 输出：去重合并后的能力模型。

5) 包设计
- 输入：入口链接、归一能力、页面集合、构建约束。
- 输出：`SkillPackagePlan`（项目名、文件树、安装说明、校验项等）。

6) 文件生成
- 输入：`SkillPackagePlan`。
- 输出：文件映射（path -> content）。

7) 包校验
- 输入：计划 + 生成文件。
- 输出：`valid`、缺失文件列表、告警列表。

### 4.2 推荐执行方式

在代码中通过 `dispatch_action()` 串联上述步骤；
在命令行中先检查契约与文件树，再进行动作调用与测试回归。

---

## 5. 运行入口与常用命令

以下命令默认在 `project/` 目录执行。

### 5.1 安装

```bash
pip install -e .
```

### 5.2 查看契约与默认文件树

```bash
docskill-factory --spec
docskill-factory --file-tree
docskill-factory --write-spec schema/openapi.json
```

### 5.3 运行测试

```bash
python -m pytest
```

Notebook 校验：执行 `tests/notebook_tests.ipynb` 中代码单元。

---

## 6. 配置项说明

`project/.env.example` 提供常用参数模板：
- `DOC_URL`：文档入口链接。
- `TARGET_LANGUAGE`：目标语言（默认 python）。
- `TARGET_SKILL_FORMAT`：目标技能契约格式（默认 openapi）。
- `ALLOW_THIRD_PARTY_LIBS`：是否允许三方依赖。
- `CACHE_DIR`：缓存目录。
- `OUTPUT_DIR`：输出目录。

---

## 7. 从“开发者视角”的最短路径

如果你要快速上手并改逻辑，按这个顺序读：

1. `project/src/novae_skill/spec.py`
2. `project/src/novae_skill/runtime.py`
3. `project/tests/test_runtime.py`
4. `project/tests/test_spec.py`
5. `project/src/novae_skill/cli.py`

这样能先理解“模型与契约”，再看“动作执行”，最后看“入口与验证”。

---

## 8. 关键设计原则

- 通用化优先：不把任何单一产品 API 硬编码为唯一真相。
- 数据驱动：通过结构化 page/capability/plan 表达流程。
- 可验证：每个阶段都能被单测或 notebook 检查。
- 可扩展：新增动作时优先保持 `dispatch_action` 与 `CORE_ACTIONS` 对齐。

---

## 9. 扩展建议（后续演进）

如果后续要增强项目，建议优先做：

1. 新增真实站点抓取与解析适配层（当前以结构化输入为主）。
2. 补充 `generate_skill_files` 的模板渲染细节，使产物直接可运行。
3. 增加端到端测试：给定真实文档 URL，自动跑完 7 步并产出包目录。

