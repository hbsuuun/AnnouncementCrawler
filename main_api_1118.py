import os
import time
import random
import requests
import re
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone
from tqdm import tqdm

BASE_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
PDF_BASE = "https://static.cninfo.com.cn/"
ORGID_MAP_FILE = Path("stockcodes/stock_orgids.json")
with open(ORGID_MAP_FILE, "r", encoding="utf-8") as f:
    STOCK_ORGIDS = json.load(f)
# 交易所映射
EXCHANGE_MAP = {
    'sz': 'SZ',    # 深圳证券交易所
    'sh': 'SH',    # 上海证券交易所
    'szse': 'SZ',  # 深圳证券交易所
    'sse': 'SH',   # 上海证券交易所
}

def get_random_timeout(min_timeout=8, max_timeout=12):
    """返回指定范围内的随机超时时间"""
    return random.uniform(min_timeout, max_timeout)

def load_downloaded_ids(save_dir):
    """从 save_dir 内加载已下载的 announcementId 集合"""
    ids_file = os.path.join(save_dir, ".downloaded_ids.json")
    if not os.path.exists(ids_file):
        return set()
    
    try:
        with open(ids_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("downloaded_ids", []))
    except Exception as e:
        print(f"⚠️ 加载已下载ID列表失败: {e}，将重新开始")
        return set()

def save_downloaded_ids(save_dir, downloaded_ids):
    """保存已下载的 announcementId 集合到 save_dir 内"""
    ids_file = os.path.join(save_dir, ".downloaded_ids.json")
    data = {
        "downloaded_ids": list(downloaded_ids),
        "last_update": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "total_count": len(downloaded_ids)
    }
    try:
        with open(ids_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ 保存已下载ID列表失败: {e}")

def cninfo_stock_param(code):
    """把 000001.SZ / 600000.SH 转成巨潮需要的 sz000001 / sh600000"""
    if not code or '.' not in code:
        return code
    digits, suffix = code.split('.')
    return f"{suffix.lower()}{digits}"

def fetch_announcements(stock_codes=None, page_num=1, page_size=30, timeout_min=8, timeout_max=12, max_retries=3, retry_delay=2, days=None):
    """
    获取公告列表
    :param stock_codes: 股票代码列表（格式：["000001.SZ", "600000.SH"]）
    :param page_num: 页码
    :param page_size: 每页数量
    :param timeout_min: 最小超时时间
    :param timeout_max: 最大超时时间
    :param max_retries: 最大重试次数
    :param retry_delay: 重试延迟（秒）
    :return: 公告列表
    """
    # 计算日期范围
    se_date = ""
    if days is not None and days > 0:
        end_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        start_ts = time.time() - (days * 24 * 60 * 60)
        start_date = datetime.fromtimestamp(start_ts, tz=timezone.utc).strftime('%Y-%m-%d')
        se_date = f"{start_date}~{end_date}"
        print(f"   📅 日期范围: {start_date} ~ {end_date} (近 {days} 天)")
    
    params = {
        "stock": "",
        "pageNum": page_num,
        "pageSize": page_size,
        "tabName": "fulltext",
        "plate": "",
        "seDate": se_date,  # 动态设置日期范围
        "column": "szse",
        "category": "",
        "searchkey": "",
        "secid": "",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }

    if stock_codes and isinstance(stock_codes, list) and len(stock_codes) > 0:
        stock_pairs = []
        for code in stock_codes:
            digits, suffix = code.split(".")
            org_id = STOCK_ORGIDS.get(digits)
            if not org_id:
                print(f"⚠️ 未找到 orgId: {code}，跳过该股票")
                continue
            stock_pairs.append(f"{digits},{org_id}")
        if stock_pairs:
            params["stock"] = ";".join(stock_pairs)

            first_code = stock_codes[0]
            params["column"] = "sse" if first_code.endswith(".SH") else "szse"

    # 重试逻辑
    for attempt in range(max_retries + 1):
        try:
            timeout = get_random_timeout(timeout_min, timeout_max)
            resp = requests.post(BASE_URL, data=params, timeout=timeout)
            resp.raise_for_status()  # 检查HTTP状态码
            data = resp.json()
            return data.get("announcements", [])
        except requests.exceptions.Timeout as e:
            if attempt < max_retries:
                wait_time = retry_delay * (attempt + 1)  # 指数退避
                print(f"⚠️ 请求超时（第 {page_num} 页，尝试 {attempt + 1}/{max_retries + 1}）: timeout={timeout:.2f}秒，{wait_time:.1f}秒后重试...")
                time.sleep(wait_time)
            else:
                print(f"⚠️ 请求超时（第 {page_num} 页）: 已重试 {max_retries} 次仍失败，返回空列表")
                return []
        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                wait_time = retry_delay * (attempt + 1)
                print(f"⚠️ 请求异常（第 {page_num} 页，尝试 {attempt + 1}/{max_retries + 1}）: {str(e)}，{wait_time:.1f}秒后重试...")
                time.sleep(wait_time)
            else:
                print(f"⚠️ 请求异常（第 {page_num} 页）: 已重试 {max_retries} 次仍失败，返回空列表")
                return []
        except Exception as e:
            if attempt < max_retries:
                wait_time = retry_delay * (attempt + 1)
                print(f"⚠️ 未知错误（第 {page_num} 页，尝试 {attempt + 1}/{max_retries + 1}）: {str(e)}，{wait_time:.1f}秒后重试...")
                time.sleep(wait_time)
            else:
                print(f"⚠️ 未知错误（第 {page_num} 页）: 已重试 {max_retries} 次仍失败，返回空列表")
                return []
    
    return []

def sanitize_filename(filename):
    """清理文件名，移除非法字符"""
    illegal_chars = r'[<>:"/\\|?*]'
    filename = re.sub(illegal_chars, '_', filename)
    if len(filename) > 200:
        filename = filename[:200]
    return filename

def normalize_stock_code(stock_code):
    """将输入统一转换成 6 位数字 + .SZ/.SH 的标准格式"""
    stock_code = str(stock_code).strip().upper()

    # 已经是标准格式：000001.SZ / 600000.SH
    if re.match(r'^\d{6}\.(SZ|SH)$', stock_code):
        return stock_code

    # 纯 6 位数字：按首位判断交易所
    if re.match(r'^\d{6}$', stock_code):
        if stock_code.startswith('6'):
            return f"{stock_code}.SH"
        elif stock_code.startswith(('0', '3')):
            return f"{stock_code}.SZ"
        else:
            return f"{stock_code}.SZ"

    # 其他字符串：提取 6 位数字后递归处理
    digits = re.findall(r'\d{6}', stock_code)
    if digits:
        return normalize_stock_code(digits[0])

    raise ValueError(
        f"无效的股票代码格式：{stock_code}（支持格式：600000、000001.SZ、600000.SH）"
    )


def get_announcement_date(item):
    """把 announcementTime 统一转换为 YYYY-MM-DD（公告发布时间），缺省则返回空字符串"""
    raw_time = item.get('announcementTime')
    if raw_time in (None, ''):
        return ''

    # 如果是数字或纯数字字符串 → 当成 Unix 时间戳
    if isinstance(raw_time, (int, float)) or (isinstance(raw_time, str) and raw_time.isdigit()):
        ts = int(raw_time)
        if ts > 1_000_000_000_000:  # 毫秒时间戳
            ts //= 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y-%m-%d')

    # 否则视为已有的日期字符串，取前 10 位（如 '2025-11-14'）
    return str(raw_time)[:10]

def generate_download_report(save_dir, stock_codes, all_items, stock_groups, 
                             success_pdf, success_html, pdf_items, html_items,
                             requested_codes, missing_codes, downloaded_ids_before, downloaded_ids_after,
                             args):
    """在 save_dir 内生成本次下载的详细报告"""
    report_file = os.path.join(save_dir, f"download_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md")
    
    report_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    new_downloads = len(downloaded_ids_after) - downloaded_ids_before
    
    report_content = f"""# 公告下载报告

## 基本信息
- **下载时间**: {report_time}
- **保存目录**: {save_dir}
- **指定股票数量**: {len(requested_codes) if requested_codes else '全部股票'}
- **实际获取公告的股票数**: {len(stock_groups)}

## 运行参数
- **股票代码文件**: {args.stock_file if args.stock_file else '未指定'}
- **股票代码**: {args.stock_code if args.stock_code else '未指定'}
- **最大抓取总数**: {args.max_items_total}
- **每页数量**: {args.page_size}
- **请求超时**: {args.timeout_min}-{args.timeout_max} 秒
- **请求延迟**: {args.delay_min}-{args.delay_max} 秒
- **下载延迟**: {args.download_delay_min}-{args.download_delay_max} 秒
- **仅PDF模式**: {'是' if args.no_html else '否'}

## 下载统计

### 总体情况
- **获取公告总数**: {len(all_items)} 条
- **PDF公告数**: {len(pdf_items)} 条
- **HTML公告数**: {len(html_items)} 条
- **PDF下载成功**: {success_pdf}/{len(pdf_items)} 份
- **HTML下载成功**: {success_html}/{len(html_items)} 份
- **本次新增下载**: {new_downloads} 条（累计已下载: {len(downloaded_ids_after)} 条）

### 各股票公告数量
"""
    
    for sec_code, items in sorted(stock_groups.items()):
        sec_pdf = len([i for i in items if "adjunctUrl" in i and i["adjunctUrl"].lower().endswith(".pdf")])
        sec_html = len(items) - sec_pdf
        report_content += f"- **{sec_code}**: 共 {len(items)} 条（PDF: {sec_pdf}, HTML: {sec_html}）\n"
    
    report_content += f"""
## 下载详情

### 各股票下载统计
"""
    
    for sec_code, items in sorted(stock_groups.items()):
        sec_pdf = len([i for i in items if "adjunctUrl" in i and i["adjunctUrl"].lower().endswith(".pdf")])
        sec_html = len(items) - sec_pdf
        sec_success_pdf = len([i for i in items if "adjunctUrl" in i and i["adjunctUrl"].lower().endswith(".pdf") and os.path.exists(os.path.join(save_dir, sec_code, f"{sec_code}_{get_announcement_date(i)}_{sanitize_filename(i.get('announcementTitle', 'Unknown'))}.pdf"))])
        sec_success_html = 0
        if not args.no_html:
            sec_success_html = len([i for i in items if not ("adjunctUrl" in i and i["adjunctUrl"].lower().endswith(".pdf")) and os.path.exists(os.path.join(save_dir, sec_code, f"{sec_code}_{get_announcement_date(i)}_{sanitize_filename(i.get('announcementTitle', 'Unknown'))}.html"))])
        report_content += f"- **{sec_code}**: PDF {sec_success_pdf}/{sec_pdf} 份, HTML {sec_success_html}/{sec_html} 份\n"
    
    # 股票代码列表（放到最后，使用表格格式）
    report_content += f"""
---

## 附录

### 本次请求的股票代码
"""
    
    if stock_codes:
        # 按每行6个代码的表格格式显示
        codes_per_row = 6
        report_content += "\n| " + " | ".join([f"列{i+1}" for i in range(codes_per_row)]) + " |\n"
        report_content += "|" + "|".join([" --- " for _ in range(codes_per_row)]) + "|\n"
        
        for i in range(0, len(stock_codes), codes_per_row):
            row_codes = stock_codes[i:i + codes_per_row]
            # 补齐空单元格
            while len(row_codes) < codes_per_row:
                row_codes.append("")
            report_content += "| " + " | ".join(row_codes) + " |\n"
    else:
        report_content += "\n- 全部股票（未指定）\n"
    
    # 未获取到公告的股票（放到最后）
    if missing_codes:
        report_content += f"""
### ⚠️ 未获取到公告的股票

"""
        # 同样使用表格格式
        codes_per_row = 6
        report_content += "| " + " | ".join([f"列{i+1}" for i in range(codes_per_row)]) + " |\n"
        report_content += "|" + "|".join([" --- " for _ in range(codes_per_row)]) + "|\n"
        
        for i in range(0, len(missing_codes), codes_per_row):
            row_codes = missing_codes[i:i + codes_per_row]
            while len(row_codes) < codes_per_row:
                row_codes.append("")
            report_content += "| " + " | ".join(row_codes) + " |\n"
    else:
        report_content += "\n### ✅ 所有指定股票均获取到至少一条公告\n"
    
    report_content += f"""
---
*报告生成时间: {report_time}*
"""
    
    try:
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report_content)
        print(f"📄 下载报告已保存: {report_file}")
    except Exception as e:
        print(f"⚠️ 保存下载报告失败: {e}")

def download_pdf(item, save_dir, downloaded_ids, timeout_min=8, timeout_max=12, output_func=print, max_retries=3, retry_delay=1):
    """下载PDF公告"""
    # 检查是否已下载
    announcement_id = item.get('announcementId')
    if announcement_id and announcement_id in downloaded_ids:
        output_func(f"⏭️  跳过已下载: {item.get('announcementTitle', 'Unknown')} (ID: {announcement_id})")
        return False
    
    # 检查adjunctUrl是否存在且是PDF格式（大小写不敏感）
    if "adjunctUrl" not in item:
        output_func(f"⚠️ 缺少adjunctUrl字段: {item.get('announcementTitle', 'Unknown')}")
        return False
    
    if not item["adjunctUrl"].lower().endswith(".pdf"):
        output_func(f"⚠️ 非PDF格式: {item['adjunctUrl']} | 标题: {item.get('announcementTitle', 'Unknown')}")
        return False

    url = PDF_BASE + item["adjunctUrl"]
    sec_code = item.get('secCode', 'unknown')
    # 创建股票代码对应的子目录
    stock_dir = os.path.join(save_dir, sec_code)
    if not os.path.exists(stock_dir):
        os.makedirs(stock_dir)
    
    # 文件名：股票代码_公告标题_日期.pdf（避免重复）
    announcement_time = get_announcement_date(item)
    filename_parts = [sec_code]
    if announcement_time:
        filename_parts.append(announcement_time)
    filename_parts.append(sanitize_filename(item.get('announcementTitle', 'Unknown')))
    filename = "_".join(filename_parts) + ".pdf"
    filepath = os.path.join(stock_dir, filename)
    
    # 重试逻辑
    for attempt in range(max_retries + 1):
        try:
            timeout = get_random_timeout(timeout_min, timeout_max)
            
            pdf_resp = requests.get(url, timeout=timeout)
            
            if pdf_resp.status_code != 200:
                raise ValueError(f"HTTP状态码错误: {pdf_resp.status_code}")
            
            if len(pdf_resp.content) == 0:
                raise ValueError("响应内容为空")
            
            # 检查是否是PDF格式
            if not pdf_resp.content.startswith(b'%PDF'):
                raise ValueError("响应内容不是PDF格式")
            
            # 保存文件
            with open(filepath, "wb") as f:
                f.write(pdf_resp.content)
            
            # 验证文件
            if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                raise IOError("文件保存失败")
            
            file_size = os.path.getsize(filepath)
            output_func(f"✅ 下载成功: {filename} (大小: {file_size} 字节)")
            
            # 下载成功后记录ID
            if announcement_id:
                downloaded_ids.add(announcement_id)
            
            return True
            
        except requests.exceptions.Timeout as e:
            if attempt < max_retries:
                wait_time = retry_delay * (attempt + 1)
                output_func(f"⚠️ 请求超时（尝试 {attempt + 1}/{max_retries + 1}）: {filename}，{wait_time:.1f}秒后重试...")
                time.sleep(wait_time)
            else:
                output_func(f"❌ 请求超时: {filename} | timeout={timeout:.2f}秒（已重试 {max_retries} 次）")
                return False
        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                wait_time = retry_delay * (attempt + 1)
                output_func(f"⚠️ 请求异常（尝试 {attempt + 1}/{max_retries + 1}）: {filename}，{wait_time:.1f}秒后重试...")
                time.sleep(wait_time)
            else:
                output_func(f"❌ 请求异常: {filename} | {str(e)}（已重试 {max_retries} 次）")
                return False
        except (ValueError, IOError) as e:
            # 这些错误通常不需要重试（如格式错误、保存失败等）
            output_func(f"❌ 下载失败: {filename} | {str(e)}")
            return False
        except Exception as e:
            if attempt < max_retries:
                wait_time = retry_delay * (attempt + 1)
                output_func(f"⚠️ 未知错误（尝试 {attempt + 1}/{max_retries + 1}）: {filename}，{wait_time:.1f}秒后重试...")
                time.sleep(wait_time)
            else:
                output_func(f"❌ 未知错误: {filename} | {str(e)}（已重试 {max_retries} 次）")
                return False
    
    return False

def download_html(item, save_dir, timeout_min=8, timeout_max=12):
    """下载网页公告（HTML格式）"""
    if "adjunctUrl" in item and item["adjunctUrl"]:
        url = PDF_BASE + item["adjunctUrl"]
        if item["adjunctUrl"].lower().endswith(".pdf"):
            print(f"⚠️ 跳过PDF文件（应使用download_pdf）: {item.get('announcementTitle', 'Unknown')}")
            return False
    elif "announcementId" in item:
        url = f"https://www.cninfo.com.cn/new/disclosure/detail?plate=&orgId={item.get('orgId', '')}&stock={item.get('secCode', '')}&announcementId={item['announcementId']}&announcementTime={item.get('announcementTime', '')}"
    else:
        print(f"⚠️ 无法获取网页公告URL: {item.get('announcementTitle', 'Unknown')}")
        return False

    sec_code = item.get('secCode', 'unknown')
    # 创建股票代码对应的子目录
    stock_dir = os.path.join(save_dir, sec_code)
    if not os.path.exists(stock_dir):
        os.makedirs(stock_dir)
    
    announcement_time = get_announcement_date(item)
    filename_parts = [sec_code]
    if announcement_time:
        filename_parts.append(announcement_time)
    filename_parts.append(sanitize_filename(item.get('announcementTitle', 'Unknown')))
    filename = "_".join(filename_parts) + ".html"
    filepath = os.path.join(stock_dir, filename)

    try:
        timeout = get_random_timeout(timeout_min, timeout_max)
        html_resp = requests.get(url, timeout=timeout)
        
        if html_resp.status_code != 200:
            print(f"⚠️ HTML下载失败: {filename} (状态码: {html_resp.status_code})")
            return False
        
        # 检查是否是PDF
        content_type = html_resp.headers.get('content-type', '').lower()
        if 'application/pdf' in content_type or html_resp.content.startswith(b'%PDF'):
            print(f"⚠️ 跳过PDF文件（内容检测）: {filename}")
            return False
        
        # 检测编码
        detected_encoding = html_resp.apparent_encoding
        if not detected_encoding or detected_encoding.lower() in ['iso-8859-1', 'ascii']:
            if 'charset=' in content_type:
                detected_encoding = content_type.split('charset=')[-1].strip().lower()
                detected_encoding = detected_encoding.strip('"\'')
            else:
                detected_encoding = 'utf-8'  # 默认为utf-8
        
        html_resp.encoding = detected_encoding
        html_text = html_resp.text
        
        # 添加charset声明
        if '<head>' in html_text and 'charset=' not in html_text[:1000].lower():
            html_text = html_text.replace('<head>', f'<head>\n<meta charset="{detected_encoding}">', 1)
        
        # 保存文件
        with open(filepath, "w", encoding=detected_encoding) as f:
            f.write(html_text)
        
        print(f"✅ HTML下载成功: {filename} (编码: {detected_encoding})")
        return True
        
    except Exception as e:
        print(f"❌ HTML下载错误: {filename} | {str(e)}")
        return False

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="爬取巨潮资讯网公告（支持按股票代码筛选）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
    使用示例:
        # 爬取单个股票（000001 平安银行）的10条公告
        python main_api_1118.py --stock-code 000001 --max-items-total 10
        
        # 爬取多个股票的公告（用逗号分隔）
        python main_api_1118.py --stock-code 000001,600000 --max-items-total 20
        
        # 从文件读取股票代码列表并爬取
        python main_api_1118.py --stock-file stockcodes/codes.txt --max-items-total 300 --save-dir data/announcements
        
        # 只生成爬取计划报告，不实际执行
        python main_api_1118.py --stock-file stockcodes/codes.txt --max-items-total 300 --plan-only
        
        # 只爬取PDF格式，不下载HTML
        python main_api_1118.py --stock-code 000001 --max-items-total 5 --no-html
        
        # 自定义重试次数和延迟（适用于网络不稳定环境）
        python main_api_1118.py --stock-file stockcodes/codes.txt --max-items-total 300 --max-retries 5 --retry-delay 3.0
        
        # 自定义超时时间和请求延迟
        python main_api_1118.py --stock-code 000001,600000 --max-items-total 50 --timeout-min 10 --timeout-max 15 --delay-min 2 --delay-max 5
        
        # 爬取所有股票的公告（默认行为，不指定--stock-code参数）
        python main_api_1118.py --max-items-total 50
        """
    )
    
    parser.add_argument(
        "--stock-file",
        type=str,
        help="包含股票代码的文件路径（每行一个，支持纯数字或带交易所后缀）"
    )

    parser.add_argument(
        "--stock-code",
        type=str,
        help="股票代码（支持单个或多个，用逗号分隔），格式：600000、000001.SZ、600000.SH"
    )

    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="只生成爬取计划报告，不实际请求或下载数据"
    )

    parser.add_argument(
        "--max-items-total",
        type=int,
        default=100,
        help="所有股票最多爬取的公告条数 (默认: 100)"
    )
    
    parser.add_argument(
        "--save-dir",
        type=str,
        default="downloads",
        help="保存目录 (默认: downloads)"
    )
    
    parser.add_argument(
        "--timeout-min",
        type=float,
        default=8.0,
        help="最小超时时间（秒） (默认: 8.0)"
    )
    
    parser.add_argument(
        "--timeout-max",
        type=float,
        default=12.0,
        help="最大超时时间（秒） (默认: 12.0)"
    )
    
    parser.add_argument(
        "--delay-min",
        type=float,
        default=1.0,
        help="请求之间的最小延迟（秒） (默认: 1.0)"
    )
    
    parser.add_argument(
        "--delay-max",
        type=float,
        default=3.0,
        help="请求之间的最大延迟（秒） (默认: 3.0)"
    )
    
    parser.add_argument(
        "--download-delay-min",
        type=float,
        default=0.5,
        help="下载之间的最小延迟（秒） (默认: 0.5)"
    )
    
    parser.add_argument(
        "--download-delay-max",
        type=float,
        default=2.0,
        help="下载之间的最大延迟（秒） (默认: 2.0)"
    )
    
    parser.add_argument(
        "--page-size",
        type=int,
        default=30,
        help="每页获取的公告数量 (默认: 30)"
    )
    
    parser.add_argument(
        "--no-html",
        action="store_true",
        help="不下载HTML格式的网页公告，只下载PDF"
    )
    
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="请求失败时的最大重试次数 (默认: 3)"
    )
    
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=2.0,
        help="重试延迟基数（秒），实际延迟 = 基数 × 重试次数 (默认: 2.0)"
    )

    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="只抓取近 N 天的公告（从今天往前推算），与 --max-items-total 配合使用"
    )
    
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    # 处理股票代码
    stock_codes = []
    if args.stock_code:
        # 分割多个股票代码
        raw_codes = [code.strip() for code in args.stock_code.split(',') if code.strip()]
        try:
            # 标准化所有股票代码
            stock_codes = [normalize_stock_code(code) for code in raw_codes]
            print(f"📋 已解析股票代码: {', '.join(stock_codes)}")
        except ValueError as e:
            print(f"❌ 股票代码格式错误: {e}")
            exit(1)
    # 如果提供了股票文件，则读取文件中的股票代码
    if args.stock_file:
        if not os.path.exists(args.stock_file):
            print(f"❌ 股票文件不存在: {args.stock_file}")
            exit(1)

        with open(args.stock_file, "r", encoding="utf-8") as f:
            file_codes = [line.strip() for line in f if line.strip()]

        if not file_codes:
            print(f"⚠️ 股票文件 {args.stock_file} 为空")
        else:
            try:
                normalized_file_codes = [normalize_stock_code(code) for code in file_codes]
            except ValueError as e:
                print(f"❌ 股票文件中的代码格式错误: {e}")
                exit(1)

            # 合并命令行和文件中的代码，并去重
            merged_codes = stock_codes + normalized_file_codes
            # 保持原有顺序的同时去重
            seen = set()
            stock_codes = []
            for code in merged_codes:
                if code not in seen:
                    seen.add(code)
                    stock_codes.append(code)

            print(f"📋 已从文件加载股票代码: {', '.join(normalized_file_codes)}")
    print(f"stock_codes: {stock_codes}")

    requested_codes = set(stock_codes)
    total_stocks = len(stock_codes) if stock_codes else "全部股票"
    max_items = args.max_items_total
    page_size = args.page_size

    if stock_codes:
        estimated_total_items = total_stocks * max_items
    else:
        estimated_total_items = "未知（需按接口返回计算）"

    estimated_pages = (
        (estimated_total_items + page_size - 1) // page_size
        if isinstance(estimated_total_items, int)
        else "未知"
    )

    print("\n📝 爬取计划报告")
    print(f"   股票数量: {total_stocks}")
    print(f"   总目标: {max_items} 条")
    print(f"   预计总公告: {estimated_total_items}")
    print(f"   预计API页数: {estimated_pages} (page_size={page_size})")
    print(f"   请求延迟: {args.delay_min}-{args.delay_max} 秒")
    if not args.no_html:
        print(f"   下载延迟: {args.download_delay_min}-{args.download_delay_max} 秒 (PDF + HTML)")
    else:
        print(f"   下载延迟: {args.download_delay_min}-{args.download_delay_max} 秒 (仅 PDF)")

    if args.plan_only:
        print("\n📌 plan-only 模式开启，仅输出报告，不执行实际请求。")
        exit(0)

    # 创建保存目录
    if not os.path.exists(args.save_dir):
        os.makedirs(args.save_dir)
        print(f"📁 创建保存目录: {args.save_dir}")
    
    # 加载已下载的ID集合
    downloaded_ids = load_downloaded_ids(args.save_dir)
    downloaded_ids_before = len(downloaded_ids)  # 记录初始数量
    print(f"📋 已加载 {downloaded_ids_before} 个已下载公告ID")
    
    # 打印配置信息
    print("\n📄 开始请求公告数据 ...")
    if stock_codes:
        print(f"   配置: 股票代码={', '.join(stock_codes)}, 总目标{args.max_items_total}条")
    else:
        print(f"   配置: 爬取所有股票，总目标{args.max_items_total}条")
    print(f"   保存到{args.save_dir}, timeout={args.timeout_min}-{args.timeout_max}秒")
    
    all_items = []
    
    # 如果指定了股票代码，分批处理（每批30只）
    if stock_codes:
        batch_size = 30
        total_batches = (len(stock_codes) + batch_size - 1) // batch_size
        print(f"\n📦 将 {len(stock_codes)} 只股票分成 {total_batches} 批处理（每批 {batch_size} 只）")
        
        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(stock_codes))
            batch_codes = stock_codes[start_idx:end_idx]
            
            print(f"\n📄 正在处理第 {batch_idx + 1}/{total_batches} 批（股票: {batch_codes[0]} ~ {batch_codes[-1]}）...")
            
            page = 1
            batch_items = []
            
            # 对当前批次循环翻页
            while len(all_items) < args.max_items_total:
                print(f"   请求第 {page} 页...")
                data = fetch_announcements(
                    stock_codes=batch_codes,
                    page_num=page,
                    page_size=args.page_size,
                    timeout_min=args.timeout_min,
                    timeout_max=args.timeout_max,
                    max_retries=args.max_retries,
                    retry_delay=args.retry_delay,
                    days=args.days 
                )
                
                if not data:
                    print(f"   ⚠️ 第 {batch_idx + 1} 批第 {page} 页没有更多数据")
                    break
                
                # 过滤掉已下载的公告（基于announcementId）
                new_items = []
                skipped_count = 0
                for item in data:
                    announcement_id = item.get('announcementId')
                    if announcement_id and announcement_id in downloaded_ids:
                        skipped_count += 1
                        continue
                    new_items.append(item)
                
                if skipped_count > 0:
                    print(f"   跳过已下载: {skipped_count} 条")
                
                # 计算还能添加多少条（只考虑未下载的）
                remaining = args.max_items_total - len(all_items)
                items_to_add = new_items[:remaining]
                
                batch_items.extend(items_to_add)
                all_items.extend(items_to_add)
                
                print(f"   第 {page} 页获取到 {len(items_to_add)} 条新公告（本批累计: {len(batch_items)}，总计: {len(all_items)}）")
                
                if len(data) < args.page_size:
                    break
                
                if len(all_items) >= args.max_items_total:
                    print(f"   ✅ 已达到总上限 {args.max_items_total} 条，停止请求")
                    break
                
                page += 1
                time.sleep(random.uniform(args.delay_min, args.delay_max))
            
            print(f"   第 {batch_idx + 1} 批完成，获取 {len(batch_items)} 条新公告")
            
            # 批次间延迟
            if batch_idx < total_batches - 1:
                delay = random.uniform(args.delay_min, args.delay_max)
                print(f"   等待 {delay:.1f} 秒后处理下一批...")
                time.sleep(delay)
            
            # 如果已达到总上限，提前结束
            if len(all_items) >= args.max_items_total:
                print(f"\n✅ 已达到总上限，提前结束批次处理")
                break
    else:
        # 未指定股票代码，使用原来的逻辑（全市场）
        page = 1
        while len(all_items) < args.max_items_total:
            print(f"\n📄 正在请求第 {page} 页公告数据 ...")
            data = fetch_announcements(
                stock_codes=None,
                page_num=page,
                page_size=args.page_size,
                timeout_min=args.timeout_min,
                timeout_max=args.timeout_max,
                max_retries=args.max_retries,
                retry_delay=args.retry_delay,
                days=args.days
            )

            if not data:
                print("⚠️ 没有更多数据了")
                break

            # 过滤掉已下载的公告（基于announcementId）
            new_items = []
            skipped_count = 0
            for item in data:
                announcement_id = item.get('announcementId')
                if announcement_id and announcement_id in downloaded_ids:
                    skipped_count += 1
                    continue
                new_items.append(item)
            
            if skipped_count > 0:
                print(f"   跳过已下载: {skipped_count} 条")

            # 计算还能添加多少条（只考虑未下载的）
            remaining = args.max_items_total - len(all_items)
            items_to_add = new_items[:remaining]
            all_items.extend(items_to_add)
            
            print(f"   第 {page} 页获取到 {len(items_to_add)} 条新公告（总计: {len(all_items)}）")
            
            if len(data) < args.page_size:
                break
            
            if len(all_items) >= args.max_items_total:
                print(f"   ✅ 已达到总上限 {args.max_items_total} 条，停止请求")
                break
            
            page += 1
            # 随机延迟
            time.sleep(random.uniform(args.delay_min, args.delay_max))

    print(f"\n✅ 共获取 {len(all_items)} 条公告")
    
    # 按股票代码分组（便于统计）
    stock_groups = {}
    for item in all_items:
        sec_code = item.get('secCode', 'unknown')
        if sec_code not in stock_groups:
            stock_groups[sec_code] = []
        stock_groups[sec_code].append(item)
    
    print(f"📊 各股票公告数量:")
    for sec_code, items in stock_groups.items():
        print(f"   {sec_code}: {len(items)} 条")

    missing_codes = sorted([
        code for code in requested_codes
        if code not in stock_groups or len(stock_groups[code]) == 0
    ])
    if missing_codes:
        print("\n⚠️ 以下股票未获取到任何公告：")
        for code in missing_codes:
            print(f"   {code}")
    else:
        print("\n✅ 所有指定股票均获取到至少一条公告")
    # 分别处理PDF和网页公告
    pdf_items = [i for i in all_items if "adjunctUrl" in i and i["adjunctUrl"].lower().endswith(".pdf")]
    html_items = [] if args.no_html else [i for i in all_items if i not in pdf_items]

    print(f"\n准备下载 {len(pdf_items)} 份PDF公告", end="")
    if not args.no_html:
        print(f" 和 {len(html_items)} 份网页公告", end="")
    print("...")
    
    success_pdf = 0
    success_html = 0
    
    # 下载PDF公告
    print(f"\n开始下载 {len(pdf_items)} 份PDF公告...")
    for item in tqdm(pdf_items, desc="下载PDF", unit="份", ncols=100):
        if download_pdf(item, args.save_dir, downloaded_ids, args.timeout_min, args.timeout_max, output_func=tqdm.write, max_retries=args.max_retries, retry_delay=args.retry_delay):
            success_pdf += 1
        time.sleep(random.uniform(args.download_delay_min, args.download_delay_max))
    print()
    
    # 下载网页公告
    if not args.no_html:
        for item in html_items:
            if download_html(item, args.save_dir, args.timeout_min, args.timeout_max):
                success_html += 1
            time.sleep(random.uniform(args.download_delay_min, args.download_delay_max))
    
    print(f"\n🎯 下载完成！")
    print(f"   PDF: {success_pdf}/{len(pdf_items)} 份")
    if not args.no_html:
        print(f"   HTML: {success_html}/{len(html_items)} 份")
    print(f"   总计: {success_pdf + success_html}/{len(all_items)} 份")

    # 保存已下载ID集合
    save_downloaded_ids(args.save_dir, downloaded_ids)
    print(f"💾 已保存 {len(downloaded_ids)} 个已下载公告ID到 {os.path.join(args.save_dir, '.downloaded_ids.json')}")
    
    # 生成下载报告
    generate_download_report(
        save_dir=args.save_dir,
        stock_codes=stock_codes,
        all_items=all_items,
        stock_groups=stock_groups,
        success_pdf=success_pdf,
        success_html=success_html,
        pdf_items=pdf_items,
        html_items=html_items,
        requested_codes=requested_codes,
        missing_codes=missing_codes,
        downloaded_ids_before=downloaded_ids_before,
        downloaded_ids_after=downloaded_ids,
        args=args
    )
    
    # 打印每个股票的下载统计
    print(f"\n📈 各股票下载统计:")
    for sec_code, items in stock_groups.items():
        sec_pdf = len([i for i in items if "adjunctUrl" in i and i["adjunctUrl"].lower().endswith(".pdf")])
        sec_html = len(items) - sec_pdf if not args.no_html else 0
        sec_success_pdf = len([i for i in items if "adjunctUrl" in i and i["adjunctUrl"].lower().endswith(".pdf") and os.path.exists(os.path.join(args.save_dir, sec_code, f"{sec_code}_{get_announcement_date(i)}_{sanitize_filename(i.get('announcementTitle', 'Unknown'))}.pdf"))])
        sec_success_html = 0
        if not args.no_html:
            sec_success_html = len([i for i in items if not ("adjunctUrl" in i and i["adjunctUrl"].lower().endswith(".pdf")) and os.path.exists(os.path.join(args.save_dir, sec_code, f"{sec_code}_{get_announcement_date(i)}_{sanitize_filename(i.get('announcementTitle', 'Unknown'))}.html"))])
        print(f"   {sec_code}: PDF {sec_success_pdf}/{sec_pdf} 份, HTML {sec_success_html}/{sec_html} 份")