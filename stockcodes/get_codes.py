import re
import glob
from pathlib import Path

# 获取所有 stock_news_urls_part*.txt 文件
url_files = glob.glob('stockcodes/stock_news_urls_part*.txt')

# 用于存储所有股票代码
stock_codes = set()

# 正则表达式匹配股票代码（从 w= 参数中提取）
pattern = r'w=(\d{6})'

# 遍历所有文件
for file_path in sorted(url_files):
    print(f'正在处理: {file_path}')
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                # 使用正则表达式提取股票代码
                match = re.search(pattern, line)
                if match:
                    stock_code = match.group(1)
                    stock_codes.add(stock_code)

# 将股票代码排序并写入文件
sorted_codes = sorted(stock_codes)

# 写入 codes.txt 文件
output_file = 'codes.txt'
with open(output_file, 'w', encoding='utf-8') as f:
    for code in sorted_codes:
        f.write(code + '\n')

print(f'\n提取完成！共提取 {len(sorted_codes)} 个股票代码')
print(f'结果已保存到: {output_file}')