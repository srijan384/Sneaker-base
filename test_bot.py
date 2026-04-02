import requests

BASE = "http://localhost:5001"

# 1. Hit a normal page
r = requests.get(f"{BASE}/products")
print("Products status:", r.status_code)

# 2. Hit a honeytrap URL — should instantly block you
r = requests.get(f"{BASE}/trap/exclusive-access")
print("Honeytrap URL response:", r.json())

# 3. Now visit a product — should get trap page
r = requests.get(f"{BASE}/product/1")
print("Product page (should be trap):", "Exclusive Drop" in r.text)

# 4. Rapid crawl — hit products 40 times fast
for i in range(40):
    requests.get(f"{BASE}/products")
print("Rapid crawl done — check /api/soc_data")

# 5. Check SOC data to see your IP flagged
soc = requests.get(f"{BASE}/api/soc_data").json()
print("Flagged IPs:", soc["flagged"])
print("Blocked IPs:", soc["blocked"])
print("Trap events:", soc["trap_events"])