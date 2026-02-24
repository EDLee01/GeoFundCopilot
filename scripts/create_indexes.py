"""
创建 Qdrant Payload 索引
首次运行一次即可，127万数据约1-3分钟
"""

import sys
sys.path.insert(0, ".")

from geomind_sdk import GeoMindClient

client = GeoMindClient()

print(f"📊 集合: {client.collection}")
info = client.info()
print(f"   数据量: {info['points_count']:,}")
print()

INDEXES = [
    ("publication_year", "integer"),
    ("cited_by_count", "integer"),
    ("journal_name", "keyword"),
    ("cas_zone", "integer"),
    ("jcr_zone", "keyword"),
    ("field", "keyword"),
    ("primary_topic", "keyword"),
    ("authors_count", "integer"),
    ("doi_verified", "bool"),
]

for field, schema in INDEXES:
    print(f"🔧 创建索引: {field} ({schema})...", end=" ", flush=True)
    try:
        client.qdrant.create_payload_index(
            collection_name=client.collection,
            field_name=field,
            field_schema=schema,
        )
        print("✅")
    except Exception as e:
        if "already exists" in str(e).lower():
            print("⏭️  已存在")
        else:
            print(f"❌ {e}")

print("\n✅ 索引创建完成！")
