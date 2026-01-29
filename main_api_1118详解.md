
# main_api_1118.py 使用详解

## 1. 脚本概述
- **功能**：调用巨潮资讯网历史公告接口，按指定股票集合获取公告列表，并可自动下载 PDF/HTML 文件。
- **核心流程**：解析参数 → 读取股票及 `orgId` 映射 → 加载已下载ID → 输出爬取计划报告 → (可选) 请求公告数据 → 保存文件并输出统计 → 生成下载报告。
- **支撑数据**：
  - 需要先运行 `stockcodes/build_orgids.py` 生成 `stockcodes/stock_orgids.json`，存放“股票代码 ↔ orgId”映射。
  - 脚本会在 `save_dir` 内自动维护 `.downloaded_ids.json`，记录已下载的公告ID，实现增量下载。

---

## 2. 参数说明
| 参数 | 必填 | 说明 |
| --- | --- | --- |
| `--stock-code` | 否 | 逗号分隔的股票代码，支持 `000001` 或 `000001.SZ` 等。 |
| `--stock-file` | 否 | 股票代码文件路径（每行一个），与 `--stock-code` 合并后去重。 |
| `--max-items-total` | 否 | 所有股票合计最多抓取的公告条数，默认 100。 |
| `--page-size` | 否 | 每页请求数量，默认 30。 |
| `--timeout-min/max` | 否 | 接口请求和下载的随机超时区间（秒）。 |
| `--delay-min/max` | 否 | 翻页请求之间的随机延迟（秒）。 |
| `--download-delay-min/max` | 否 | 文件下载之间的随机延迟（秒）。 |
| `--save-dir` | 否 | 下载根目录，默认 `downloads/`，按 `secCode` 再分子目录。 |
| `--no-html` | 否 | 仅下载 PDF，跳过 HTML 公告。 |
| `--plan-only` | 否 | 只打印计划报告，不执行实际请求和下载。 |

> **注意**：脚本读取 `stock_orgids.json` 后，会为每个股票拼接 “代码,orgId” 格式传给巨潮接口，确保只返回指定股票的公告。

---

## 3. 使用示例

### 3.1 仅生成计划报告
```
python main_api_1118.py --stock-file stockcodes/codes_test.txt --max-items-total 200 --plan-only
```

输出示例：
```
📝 爬取计划报告
   股票数量: 15
   总目标: 200 条
   预计总公告: 3000
   预计API页数: 100 (page_size=30)
   请求延迟: 1.0-3.0 秒
   下载延迟: 0.5-2.0 秒 (PDF + HTML)
📌 plan-only 模式开启，仅输出报告，不执行实际请求。
```

### 3.2 小批量测试（仅 PDF）
```
python main_api_1118.py --stock-code 000001,600519 --max-items-total 20 --no-html
```

### 3.3 读取文件 + 增量下载
```
python main_api_1118.py --stock-file stockcodes/codes.txt --max-items-total 300 --save-dir data/announcements
```

**增量下载说明**：第二次运行相同命令时，脚本会自动跳过已下载的公告（基于 `announcementId`），只下载新增的公告。

---

## 4. 运行流程速览
1. **解析参数**：`argparse` 读取命令行配置。
2. **股票列表 + orgId 准备**：
   - `--stock-code`：标准化成 `000001.SZ` 等格式。
   - `--stock-file`：逐行读取后标准化，与命令行输入合并、顺序去重。
   - 从 `stock_orgids.json` 里加载“代码 → orgId”映射；若某代码缺少 orgId，会在请求前给出警告并跳过。
3. **加载已下载ID**：从 `save_dir/.downloaded_ids.json` 加载已下载的公告ID集合，用于增量下载。
4. **计划报告**：计算股票数量、`max-items-total`、预计页数以及请求/下载延迟。
5. **执行爬取**（未启用 `plan-only` 时）：
   - `fetch_announcements()` 会把 `stock` 参数设置为 `000001,gssz0000001;600000,gssh0600000` 等形式，接口仅返回对应股票公告。
   - 循环翻页直到达到总量或没有更多数据。
   - 按 `secCode` 分组统计，并输出“哪些股票未获取到公告”的列表。
   - 根据 `--no-html` 设置，下载 PDF 或 HTML，并保存到 `save-dir/<secCode>/` 目录下。
   - **增量下载**：下载PDF前检查 `announcementId` 是否已存在，已存在则跳过；下载成功后立即记录ID。
6. **统计与输出**：打印总下载数、各股票成功/失败情况。
7. **保存ID集合**：将更新后的已下载ID集合保存到 `save_dir/.downloaded_ids.json`。
8. **生成下载报告**：在 `save_dir` 内生成带时间戳的 Markdown 报告文件（`download_report_YYYYMMDD_HHMMSS.md`），包含本次下载的详细统计。

---

## 5. 增量下载机制

### 5.1 工作原理
- 脚本在 `save_dir` 内维护 `.downloaded_ids.json` 文件，记录所有已成功下载的公告 `announcementId`。
- 每次下载PDF前，先检查该公告的 `announcementId` 是否已在集合中。
- 如果已存在，跳过下载并提示“⏭️ 跳过已下载”。
- 如果不存在，执行下载，成功后立即将ID加入集合。
- 脚本结束时，将更新后的ID集合保存到文件。

### 5.2 文件结构
```
save_dir/
├── .downloaded_ids.json          # 已下载ID记录（JSON格式）
├── download_report_20250120_103045.md  # 下载报告（每次运行生成一个）
├── 000001/                        # 股票代码子目录
│   ├── 000001_2025-01-20_公告标题1.pdf
│   └── 000001_2025-01-20_公告标题2.pdf
└── 600000/
    └── 600000_2025-01-20_公告标题.pdf
```

### 5.3 增量下载示例
```bash
# 第一次运行：下载300条公告
python main_api_1118.py --stock-file stockcodes/codes.txt --max-items-total 300 --save-dir data/announcements

# 第二天运行相同命令：自动跳过已下载的公告，只下载新增的
python main_api_1118.py --stock-file stockcodes/codes.txt --max-items-total 300 --save-dir data/announcements
```

---

## 6. 下载报告说明

每次下载完成后，脚本会在 `save_dir` 内生成一个 Markdown 格式的报告文件，文件名格式：`download_report_YYYYMMDD_HHMMSS.md`。

### 报告内容包含：
- **基本信息**：下载时间、保存目录、股票数量等
- **股票列表**：本次请求的所有股票代码
- **下载统计**：
  - 总体情况（获取总数、PDF/HTML数量、成功数等）
  - 本次新增下载数量（与历史对比）
  - 累计已下载总数
- **各股票公告数量**：按股票代码统计
- **未获取到公告的股票列表**（如果有）
- **各股票详细下载统计**：PDF/HTML 成功/失败数量

---

## 7. 不足与注意事项
- **orgId 依赖本地文件**：运行前必须保证 `stock_orgids.json` 已包含所需股票，否则该股票会被跳过。可先运行 `stockcodes/build_orgids.py` 生成或更新映射。
- **总量限制**：`--max-items-total` 控制整体抓取条数，不能保证每只股票平均分配。若想每股固定条数，需要额外逻辑。
- **计划报告估算**：当不指定股票（抓全市场）时，预计总条数会显示“未知”；此时建议先用小范围测试。
- **失败处理**：接口或下载失败当前只打印日志，没有自动重试；必要时可扩展重试或失败列表。
- **接口限流**：仅靠随机延迟控制频率，长时间/大规模抓取建议加代理或更严格限速。
- **增量下载仅针对PDF**：HTML 公告不记录ID，每次都会尝试下载（因为HTML通常被视为异常情况）。
- **ID文件维护**：如果手动删除 `.downloaded_ids.json`，下次运行会重新开始记录；已下载的文件不会重复下载（因为文件名相同会覆盖），但ID记录会丢失。

---

## 8. 建议的扩展与测试
- **Dry run**：每次大任务前先加 `--plan-only` 检查参数和耗时估算。
- **小样本验证**：先用少量股票 + 小的 `--max-items-total` 验证流程，再跑全部列表。
- **映射维护**：定期更新 `stock_orgids.json`，或在 `build_orgids.py` 中增加增量更新逻辑。
- **失败记录/重试**：可记录下载失败的公告，支持后续补抓。
- **按股票限额**：如需“每股 N 条”，可以在汇总阶段对 `stock_groups` 做二次筛选。
- **定期清理报告**：下载报告会累积，建议定期归档或删除旧报告。

---

## 9. 常见问题（FAQ）
- **Q:** `max-items-total` 设置为 100，为什么有的股票只有几条？  
  **A:** 接口按照全局时间顺序返回，达到总上限后就停止，无法保证每股都有数据。

- **Q:** `stock_orgids.json` 怎么来的？  
  **A:** 通过 `stockcodes/build_orgids.py` 调用巨潮搜索接口生成，也可以手工维护。

- **Q:** 只下载 PDF 怎么设置？  
  **A:** 加 `--no-html`，脚本只处理 PDF 文件；若只要 HTML，需要自行调整 `pdf_items/html_items` 的筛选逻辑。

- **Q:** 下载文件名的日期是否真实？  
  **A:** `get_announcement_date()` 会把 `announcementTime` 转为 `YYYY-MM-DD`，若接口返回的是 Unix 时间戳会自动转换为对应日期。

- **Q:** 如何实现增量下载？  
  **A:** 脚本自动实现。每次运行时会加载 `save_dir/.downloaded_ids.json`，跳过已下载的公告。无需额外操作。

- **Q:** 如果删除了 `.downloaded_ids.json` 会怎样？  
  **A:** 脚本会重新开始记录，但已存在的同名文件会被覆盖（不会重复下载），只是ID记录丢失。

- **Q:** 下载报告在哪里？  
  **A:** 在 `save_dir` 目录下，文件名格式为 `download_report_YYYYMMDD_HHMMSS.md`，每次运行生成一个。

---
