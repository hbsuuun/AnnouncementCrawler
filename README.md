# 上市公司公告爬虫

一键抓取上市公司公告并转换为 Markdown 文本。

## 功能

- 📥 从巨潮资讯网抓取公告（PDF/HTML）
- 📄 将 PDF 提取为 Markdown 文本
- 🔄 支持股票代码筛选
- 📅 支持按天数筛选
- 💾 断点续传（自动跳过已下载）

## 安装
 ```txt
# 创建虚拟环境（conda）
conda create -n crawler python=3.9
conda activate crawler

# 安装依赖
pip install -r requirements.txt**requirements.txt:**
requests>=2.28.0
tqdm>=4.64.0
pdfplumber>=0.10.0
```
**requirements.txt:**
```txt
requests
tqdm
pdfplumber
```

## 使用方法

### 1. 准备股票代码

在 `stockcodes/codes.txt` 中添加股票代码（每行一个）：

```txt
000001
600000
000002
```

或使用带交易所后缀的格式：

```txt
000001.SZ
600000.SH
000002.SZ
```

### 2. 一键运行

```bash
# 添加执行权限
chmod +x run.sh

# 默认运行（从文件读取股票，抓取100条）
./run.sh

# 或指定股票代码
./run.sh --stock-code 000001

# 多个股票
./run.sh --stock-code 000001,600000
```

## 参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `--stock-code` | 股票代码（逗号分隔） | `--stock-code 000001,600000` |
| `--stock-file` | 股票代码文件路径 | `--stock-file stockcodes/codes.txt` |
| `--max-items-total` | 最大抓取数量 | `--max-items-total 50` |
| `--days` | 只抓取近 N 天 | `--days 7` |
| `--save-dir` | 保存目录 | `--save-dir downloads` |
| `--no-convert` | 跳过 PDF 转换 | `--no-convert` |

## 示例

```bash
# 抓取单个股票，近7天，最多10条
./run.sh --stock-code 000001 --days 7 --max-items-total 10

# 从文件读取，近30天，最多100条
./run.sh --stock-file stockcodes/codes.txt --days 30 --max-items-total 100

# 只抓取，不转换
./run.sh --stock-code 000001 --no-convert
```

## 输出

```
downloads/
├── 000001/
│   ├── 000001_2025-11-28_独立董事提名人声明.pdf
│   └── 000001_2025-12-01_年度报告.pdf
└── 600000/
    └── ...

processed/markdown/
├── downloads/000001/000001_2025-11-28_独立董事提名人声明.md
└── ...
```

## 手动运行

如果需要单独运行某个步骤：

```bash
# 只抓取公告
python main_api_1118.py --stock-file stockcodes/codes.txt --max-items-total 100

# 只转换PDF
python pdf2md.py
```

## 注意事项

1. **请求频率**：脚本内置 1-3 秒随机延迟，避免被封
2. **断点续传**：已下载的公告会记录在 `.downloaded_ids.json`，不会重复下载
3. **网络问题**：如遇到 500 错误，可能是巨潮 API 不稳定，稍后重试

## 项目结构

```
Crawler-JuChao/
├── run.sh                 # 一键启动脚本
├── main_api_1118.py       # 公告爬虫
├── pdf2md.py              # PDF转Markdown
├── requirements.txt       # 依赖
├── stockcodes/
│   ├── codes.txt          # 股票代码列表
│   └── stock_orgids.json  # 股票映射
├── downloads/             # 下载的公告
└── processed/             # 转换后的文本
```

## License

MIT

## 免责声明

本项目仅用于**个人学习研究**目的。

使用本项目时，请遵守：
- 相关法律法规
- 巨潮资讯网的使用条款
- robots.txt 规范

**作者不对任何滥用行为承担责任。**