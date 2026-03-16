import os
import re
import asyncio
import aiohttp
from time import time
from datetime import datetime, timedelta
import requests
import statistics

# 输出文件
outfile = os.path.join(os.getcwd(), "cmlive.txt")

with open(outfile, "w", encoding="utf-8") as f:
    f.write("")
print(f"📄 输出文件: {outfile}")

# 数据源 URL
url = "https://raw.githubusercontent.com/q1017673817/iptvz/refs/heads/main/zubo_all.txt"

print("📡 正在下载直播源...")
try:
    res = requests.get(url, timeout=60)
    res.encoding = 'utf-8'
    lines = [i.strip() for i in res.text.splitlines() if i.strip()]
    print(f"✅ 成功下载源文件，共 {len(lines)} 条")
except Exception as e:
    print(f"❌ 下载失败: {e}")
    raise SystemExit(1)

# 省份关键词
provinces = ["湖南","北京","河北","山西","内蒙古","辽宁","吉林","黑龙江","上海","江苏","浙江",
             "安徽","福建","江西","山东","河南","湖北","天津","广东","广西","海南","重庆","四川",
             "贵州","云南","西藏","陕西","甘肃","青海","宁夏","新疆","港澳台"]

# 分类逻辑
groups = {}
current_group = None

for line in lines:
    if line.endswith(",#genre#"):
        current_group = line.replace(",#genre#", "")
        continue
    if "," not in line:
        continue
    name, link = line.split(",", 1)

    group = None
    if re.search(r"CCTV|CETV", name):
        group = "央视频道"
    elif "卫视" in name:
        group = "卫视频道"
        name = re.match(r"(.*?卫视)", name).group(1)
    else:
        matched = False
        if current_group:
            for prov in provinces:
                if prov in current_group:
                    group = f"{prov}频道"
                    matched = True
                    break
        if not matched:
            for prov in provinces:
                if prov in name:
                    group = f"{prov}频道"
                    matched = True
                    break
        if not matched:
            group = "其他频道"

    groups.setdefault(group, []).append({"name": name, "link": link})

# 异步测速函数（延迟 + 实测下载速度）
async def test_stream(session, item):
    start = time()
    try:
        async with session.get(item["link"], timeout=8) as resp:
            chunk = await resp.content.read(300 * 1024)  # 读取300KB
            elapsed = time() - start
            size_kb = len(chunk) / 1024
            speed_kbps = size_kb / elapsed if elapsed > 0 else 0
            item["time"] = elapsed
            item["speed"] = round(speed_kbps, 2)
            return item
    except:
        item["time"] = float("inf")
        item["speed"] = 0
        return item

# 异步批量测速
async def test_group(items):
    timeout = aiohttp.ClientTimeout(total=10)
    connector = aiohttp.TCPConnector(limit=800)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        tasks = [asyncio.create_task(test_stream(session, item)) for item in items]
        results = await asyncio.gather(*tasks)
    return results

# 执行测速
print("⏱ 开始异步并行测速（延迟 + 下载速度）...")
for group_name, items in groups.items():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    items = loop.run_until_complete(test_group(items))
    loop.close()

    # 排序：先速度后延迟
    if group_name == "央视频道":
        cctv_order = [
            "CCTV-1综合","CCTV-2财经","CCTV-3综艺","CCTV-4中文国际","CCTV-5体育",
            "CCTV-5+体育赛事","CCTV-6电影","CCTV-7国防军事","CCTV-8电视剧",
            "CCTV-9纪录","CCTV-10科教","CCTV-11戏曲","CCTV-12社会与法",
            "CCTV-13新闻","CCTV-14少儿","CCTV-15音乐","CCTV-16奥林匹克",
            "CCTV-17农业农村","CCTV-4K超高清","CCTV-兵器科技","CCTV-第一剧场",
            "CCTV-电视指南","CCTV-风云剧场","CCTV-风云音乐","CCTV-风云足球",
            "CCTV-高尔夫·网球","CCTV-怀旧剧场","CCTV-女性时尚","CCTV-世界地理",
            "CCTV-央视台球","CCTV-文化精品"
        ]
        cctv_groups = {}
        for item in items:
            cctv_groups.setdefault(item['name'], []).append(item)
        sorted_items = []
        for name in cctv_order:
            if name in cctv_groups:
                sorted_items.extend(sorted(cctv_groups[name], key=lambda x: (-x["speed"], x["time"])))
        groups[group_name] = sorted_items
    elif group_name == "卫视频道":
        name_groups = {}
        for item in items:
            name_groups.setdefault(item['name'], []).append(item)
        sorted_items = []
        for name, group_items in name_groups.items():
            sorted_items.extend(sorted(group_items, key=lambda x: (-x["speed"], x["time"])))
        groups[group_name] = sorted_items
    else:
        groups[group_name] = sorted(items, key=lambda x: (-x["speed"], x["time"]))

    # 📊 输出测速统计信息
    speeds = [i["speed"] for i in items if i["speed"] > 0]
    if speeds:
        avg_speed = round(statistics.mean(speeds), 1)
        max_speed = round(max(speeds), 1)
        print(f"✅ {group_name} 测速完成，共 {len(items)} 条｜平均速度 {avg_speed} KB/s｜最快 {max_speed} KB/s")
    else:
        print(f"⚠️ {group_name} 测速完成，但全部失败")

# 获取北京时间
now = datetime.utcnow() + timedelta(hours=8)
update_time = now.strftime("%Y%m%d %H:%M")

# 写入文件
with open(outfile, "w", encoding="utf-8") as f:
    f.write("更新时间,#genre#\n")
    f.write(f"{update_time},https://d.kstore.dev/download/8880/%E5%85%AC%E5%91%8A.mp4\n")
    f.write("关于本源(塔利班维护),https://v.cdnlz12.com/20250131/18183_a5e8965b/index.m3u8\n\n")
    
    for g, items in groups.items():
        f.write(f"{g},#genre#\n")
        for i in items:
            f.write(f"{i['name']},{i['link']}\n")
        f.write("\n")

total = sum(len(v) for v in groups.values())
print(f"✅ 已生成 {outfile}，共 {total} 条直播源（测速+排序完成，北京时间）")
