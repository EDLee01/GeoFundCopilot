"""
查看 Qdrant 中一条完整数据的所有字段
"""
import sys
sys.path.insert(0, ".")
import json
from geomind_sdk import GeoMindClient

client = GeoMindClient()

# 拉取 3 条完整数据（带所有 payload 字段）
sample, _ = client.qdrant.scroll(
    collection_name=client.collection,
    limit=3,
    with_payload=True,
    with_vectors=False
)

for i, point in enumerate(sample):
    print(f"\n{'='*60}")
    print(f"第 {i+1} 条 | ID: {point.id}")
    print(f"{'='*60}")
    
    payload = point.payload
    print(f"\n字段总数: {len(payload)}")
    print(f"字段列表: {list(payload.keys())}\n")
    
    for key, value in payload.items():
        val_type = type(value).__name__
        val_str = json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else str(value)
        
        if len(val_str) > 200:
            val_str = val_str[:200] + "..."
        
        print(f"  {key} ({val_type}):")
        print(f"    {val_str}")
        print()
