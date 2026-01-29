#!/bin/bash
# run.sh - 一键启动脚本

set -e  # 遇错即停

echo "========================================"
echo "🚀 巨潮公告爬虫一键启动"
echo "========================================"
echo ""

# 默认参数
STOCK_FILE="stockcodes/codes.txt"
MAX_ITEMS=100
DAYS=""
SAVE_DIR="downloads"

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --stock-code)
            STOCK_CODE="$2"
            shift 2
            ;;
        --stock-file)
            STOCK_FILE="$2"
            shift 2
            ;;
        --max-items-total)
            MAX_ITEMS="$2"
            shift 2
            ;;
        --days)
            DAYS="$2"
            shift 2
            ;;
        --save-dir)
            SAVE_DIR="$2"
            shift 2
            ;;
        --no-convert)
            NO_CONVERT=true
            shift
            ;;
        *)
            echo "未知参数: $1"
            exit 1
            ;;
    esac
done

# 步骤1: 抓取公告
echo "📥 步骤1: 抓取公告..."
echo "----------------------------------------"

CMD="python main_api_1118.py --max-items-total $MAX_ITEMS --save-dir $SAVE_DIR"

if [ -n "$STOCK_CODE" ]; then
    CMD="$CMD --stock-code $STOCK_CODE"
elif [ -f "$STOCK_FILE" ]; then
    CMD="$CMD --stock-file $STOCK_FILE"
fi

if [ -n "$DAYS" ]; then
    CMD="$CMD --days $DAYS"
fi

echo "执行: $CMD"
$CMD

echo ""

# 步骤2: 转换PDF（除非指定跳过）
if [ "$NO_CONVERT" != "true" ]; then
    echo "📄 步骤2: 转换PDF为MD..."
    echo "----------------------------------------"
    echo "执行: python pdf2md.py"
    python pdf2md.py
fi

echo ""
echo "========================================"
echo "✅ 完成！"
echo "========================================"
echo "📁 下载目录: $SAVE_DIR/"
echo "📁 转换目录: processed/"
echo "========================================"