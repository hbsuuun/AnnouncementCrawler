import json
import time
import requests
from pathlib import Path

CODES_FILE = Path("stockcodes/codes.txt")
OUTPUT_FILE = Path("stockcodes/stock_orgids.json")
CNINFO_SEARCH_URL = "https://www.cninfo.com.cn/new/information/topSearch/query"

def fetch_org_id(code: str) -> str | None:
    """
    通过巨潮搜索接口获取 orgId。
    返回 None 表示未找到。
    """
    payload = {
        "keyWord": code,
        "maxSecNum": 1,
        "maxListNum": 1,
    }
    resp = requests.post(CNINFO_SEARCH_URL, data=payload, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    # 接口有两种返回结构：顶层列表，或者含有 "stock" 键的字典
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("stock", [])
    else:
        items = []

    if not items:
        return None

    item = items[0]
    return item.get("orgId") or item.get("orgid")

def main():
    if not CODES_FILE.exists():
        raise FileNotFoundError(f"{CODES_FILE} 不存在")

    codes = [
        line.strip()
        for line in CODES_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    result = {}
    missing = []

    for idx, code in enumerate(codes, start=1):
        try:
            org_id = fetch_org_id(code)
            if org_id:
                result[code] = org_id
                print(f"[{idx}/{len(codes)}] {code} -> {org_id}")
            else:
                missing.append(code)
                print(f"[{idx}/{len(codes)}] {code} 未找到 orgId")
        except Exception as exc:
            missing.append(code)
            print(f"[{idx}/{len(codes)}] {code} 查询失败: {exc}")
        time.sleep(0.3)  # 轻微限速，避免触发风控

    OUTPUT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已写入 {len(result)} 条记录到 {OUTPUT_FILE}")

    if missing:
        print("以下代码未能获取 orgId，请手动核查：")
        for code in missing:
            print("  -", code)

if __name__ == "__main__":
    main()