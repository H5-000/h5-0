import os
import asyncio
import requests
from playwright.async_api import async_playwright

API_BASE = "https://workermatch-config.hs2224008.workers.dev"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
PROXY_URL = os.environ.get("PROXY_URL")

TEAM_DICT = {
    "Inter": "إنتر", "Juventus": "يوفنتوس", "Venezia": "فينيسيا", "Genoa": "جنوى", "Monza": "مونزا", "Napoli": "نابولي",
    "Real Madrid": "ريال مدريد", "Barcelona": "برشلونة", "Atletico Madrid": "أتلتيكو مدريد", "Sevilla": "إشبيلية",
    "Man City": "مانشستر سيتي", "Man United": "مانشستر يونايتد", "Liverpool": "ليفربول", "Arsenal": "أرسنال", "Chelsea": "تشيلسي", "Tottenham": "توتنهام",
    "Bayern Munich": "بايرن ميونخ", "Borussia Dortmund": "دورتموند", "PSG": "باريس سان جيرمان", "Marseille": "مارسيليا",
    "Al Hilal": "الهلال", "Al Nassr": "النصر", "Al Ittihad": "الاتحاد", "Al Ahli": "الأهلي",
    "Iraq": "العراق", "Saudi Arabia": "السعودية", "Egypt": "مصر", "Morocco": "المغرب"
}

async def get_matches():
    try:
        r = requests.get(f"{API_BASE}/fixtures")
        if r.ok: return r.json()
    except Exception as e: print(f"Error: {e}")
    return []

async def extract_stream(page, team1, team2):
    ar_t1 = TEAM_DICT.get(team1, team1)
    ar_t2 = TEAM_DICT.get(team2, team2)

    try:
        await page.goto("https://koora7goal.com/", wait_until="networkidle", timeout=60000)
        
        link = page.locator(f"a:has-text('{ar_t1}')").first
        if await link.count() == 0:
            link = page.locator(f"a:has-text('{ar_t2}')").first
            
        if await link.count() > 0:
            await link.click()
            await page.wait_for_timeout(4000) 
            iframe = await page.query_selector("iframe")
            if iframe:
                src = await iframe.get_attribute("src")
                if src and src.startswith("//"): 
                    src = "https:" + src
                return src
    except Exception as e:
        print(f"خطأ في {ar_t1} ضد {ar_t2}: {e}")
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
    
    # 💡 هنا السر: نصفي المباريات وناخذ بس المباشرة أو القادمة (نتجاهل المنتهية)
    active_matches = [m for m in fixtures if m.get("status") in ["live", "soon"]]
    print(f"📊 إجمالي المباريات: {len(fixtures)} | المباريات النشطة (مباشر/قادم): {len(active_matches)}")

    if not active_matches:
        print("⚠️ لا توجد مباريات مباشرة أو قادمة حالياً للتحديث.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            proxy={"server": PROXY_URL} if PROXY_URL else None
        )
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()

        links_to_update = {}
        for m in active_matches:
            t1 = m.get("home", {}).get("name")
            t2 = m.get("away", {}).get("name")
            if not t1 or not t2: continue
            
            ar_t1 = TEAM_DICT.get(t1, t1)
            ar_t2 = TEAM_DICT.get(t2, t2)
            print(f"🔍 جاري البحث عن: {ar_t1} ضد {ar_t2}")
            
            url = await extract_stream(page, t1, t2)
            if url:
                links_to_update[str(m.get("id"))] = {"link": url, "mode": "embed"}
                print(f"✅ تم إيجاد رابط البث لـ {ar_t1} ضد {ar_t2}")

        await browser.close()

    if links_to_update:
        print(f"📤 جاري تحديث موقعك بـ {len(links_to_update)} رابط...")
        cfg_res = requests.get(f"{API_BASE}/config")
        cfg = cfg_res.json()
        cfg["links"] = {**cfg.get("links", {}), **links_to_update}
        requests.post(f"{API_BASE}/config", json=cfg, headers={"Authorization": f"Bearer {token}"})
        print("🎉 تم التحديث بنجاح!")
    else:
        print("⚠️ لم يتم العثور على روابط جديدة. (قد يكون الموقع المصدر محظر الـ IP أو الأسماء مختلفة).")

if __name__ == "__main__":
    asyncio.run(main())
