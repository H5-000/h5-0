import os
import asyncio
import requests
from playwright.async_api import async_playwright

API_BASE = "https://workermatch-config.hs2224008.workers.dev"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
PROXY_URL = os.environ.get("PROXY_URL")

async def get_matches():
    try:
        r = requests.get(f"{API_BASE}/fixtures")
        if r.ok: return r.json()
    except Exception as e: print(f"Error: {e}")
    return []

async def extract_stream(page, team1, team2):
    try:
        await page.goto("https://koora7goal.com/", wait_until="networkidle", timeout=60000)
        link = page.locator(f"a:has-text('{team1}')").first
        if await link.count() > 0:
            await link.click()
            await page.wait_for_timeout(5000) 
            iframe = await page.query_selector("iframe")
            if iframe:
                src = await iframe.get_attribute("src")
                if src.startswith("//"): src = "https:" + src
                return src
    except Exception as e:
        print(f"Error extracting {team1} vs {team2}: {e}")
    return None

async def main():
    if not ADMIN_PASSWORD:
        print("❌ خطأ: لم يتم وضع كلمة المرور")
        return

    r = requests.get(f"{API_BASE}/auth", headers={"X-Admin-Password": ADMIN_PASSWORD})
    if not r.ok:
        print("❌ كلمة المرور غير صحيحة")
        return
    token = r.json().get("token")

    fixtures = await get_matches()
    print(f"📊 تم جلب {len(fixtures)} مباراة من موقعك")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            proxy={"server": PROXY_URL} if PROXY_URL else None
        )
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()

        links_to_update = {}
        for m in fixtures:
            t1 = m.get("home", {}).get("name")
            t2 = m.get("away", {}).get("name")
            if not t1 or not t2: continue
            
            print(f"🔍 جاري البحث عن: {t1} ضد {t2}")
            url = await extract_stream(page, t1, t2)
            if url:
                links_to_update[str(m.get("id"))] = {"link": url, "mode": "embed"}
                print(f"✅ تم إيجاد رابط البث لـ {t1}")

        await browser.close()

    if links_to_update:
        print(f"📤 جاري تحديث موقعك بـ {len(links_to_update)} رابط...")
        cfg_res = requests.get(f"{API_BASE}/config")
        cfg = cfg_res.json()
        cfg["links"] = {**cfg.get("links", {}), **links_to_update}
        requests.post(f"{API_BASE}/config", json=cfg, headers={"Authorization": f"Bearer {token}"})
        print("🎉 تم التحديث بنجاح!")
    else:
        print("⚠️ لم يتم العثور على روابط جديدة.")

if __name__ == "__main__":
    asyncio.run(main())
