"""
PDF公告文本提取脚本
将 downloads/ 目录下的 PDF 提取为 txt/md 文件到 processed/ 目录
"""
import os
import re
from pathlib import Path
from datetime import datetime
import pdfplumber

def extract_text_from_pdf(pdf_path: str) -> str:
    """从PDF中提取文本"""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
    except Exception as e:
        print(f"❌ 提取失败: {pdf_path} - {e}")
    return text

def sanitize_filename(filename: str) -> str:
    """清理文件名，移除非法字符"""
    illegal_chars = r'[<>:"/\\|?*]'
    return re.sub(illegal_chars, '_', filename)

def convert_to_markdown(text: str, pdf_path: str, output_dir: Path) -> str:
    """将文本转换为Markdown格式"""
    # 从PDF路径提取信息
    pdf_name = Path(pdf_path).stem
    # 修复：转为绝对路径后再计算相对路径
    pdf_absolute = Path(pdf_path).resolve()
    pdf_relative = pdf_absolute.relative_to(Path.cwd())
    
    # 清理文本中的多余空行
    lines = text.split('\n')
    cleaned_lines = []
    for i, line in enumerate(lines):
        # 移除页眉页脚（常见的页码格式）
        if re.match(r'^\s*\d+\s*$', line.strip()):
            continue
        # 移除单行的破折号
        if re.match(r'^[-─]{10,}$', line.strip()):
            continue
        cleaned_lines.append(line)
    
    text_clean = '\n'.join(cleaned_lines)
    
    # 构建Markdown
    md_content = f"""---
title: {pdf_name}
source: {pdf_relative}
extracted_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
---

# {pdf_name}

{text_clean}
"""
    return md_content

def process_pdf(pdf_path: Path, output_dir: Path, use_markdown: bool = True):
    """处理单个PDF文件"""
    # 修复：转为绝对路径
    pdf_path = pdf_path.resolve()
    
    # 构建输出路径
    relative_path = pdf_path.relative_to(Path.cwd())
    relative_dir = relative_path.parent
    
    # 构建目标路径
    if use_markdown:
        output_subdir = output_dir / "markdown" / relative_dir
        output_path = output_subdir / f"{pdf_path.stem}.md"
    else:
        output_subdir = output_dir / "text" / relative_dir
        output_path = output_subdir / f"{pdf_path.stem}.txt"
    
    # 创建目录
    output_subdir.mkdir(parents=True, exist_ok=True)
    
    # 提取文本
    print(f"📄 处理: {pdf_path}")
    text = extract_text_from_pdf(str(pdf_path))
    
    if not text.strip():
        print(f"   ⚠️ 警告: {pdf_path} 提取内容为空")
        return False
    
    # 保存
    if use_markdown:
        content = convert_to_markdown(text, str(pdf_path), output_dir)
        output_path = output_subdir / f"{pdf_path.stem}.md"
    else:
        content = text
        output_path = output_subdir / f"{pdf_path.stem}.txt"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"   ✅ 已保存: {output_path}")
    return True

def main():
    """主函数"""
    downloads_dir = Path("downloads")
    output_dir = Path("processed")
    
    if not downloads_dir.exists():
        print("❌ downloads 目录不存在")
        return
    
    # 查找所有PDF文件
    pdf_files = list(downloads_dir.rglob("*.pdf"))
    
    if not pdf_files:
        print("❌ 未找到PDF文件")
        return
    
    print(f"📁 找到 {len(pdf_files)} 个PDF文件")
    print("=" * 50)
    
    # 处理每个PDF
    success = 0
    for pdf_path in pdf_files:
        if process_pdf(pdf_path, output_dir, use_markdown=True):
            success += 1
    
    print("=" * 50)
    print(f"✅ 完成: {success}/{len(pdf_files)} 个文件处理成功")
    print(f"📂 输出目录: {output_dir}/(markdown|text)/")

if __name__ == "__main__":
    main()