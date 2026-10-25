import os
import re
import json
import asyncio
import requests
from urllib.parse import urljoin
from playwright.async_api import async_playwright

API_BASE = "https://workermatch-config.hs2224008.workers.dev"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
PROXY_URL = os.environ.get("PROXY_URL")

# قاموس ضخم لأشهر الفرق (يمنع الترجمة الغبية)
TEAM_DICT = {
    "Getafe": "خيتافي", "Athletic Club": "أتلتيك بلباو", "Athletic Bilbao": "أتلتيك بلباو",
    "PSV": "آيندهوفن", "Feyenoord": "فاينورد", "Bournemouth": "بورنموث",
    "Manchester United": "مانشستر يونايتد", "Liverpool": "ليفربول", "Brighton": "برايتون",
    "Newcastle": "نيوكاسل", "Crystal Palace": "كريستال بالاس", "Real Madrid": "ريال مدريد",
    "Barcelona": "برشلونة", "Atletico Madrid": "أتلتيكو مدريد", "Sevilla": "إشبيلية",
    "Real Betis": "ريال بيتيس", "Celta Vigo": "سيلتا فيغو", "Valencia": "فالنسيا",
    "Villarreal": "فياريال", "Real Sociedad": "ريال سوسيداد", "Girona": "جيرونا",
    "Man City": "مانشستر سيتي", "Arsenal": "أرسنال", "Chelsea": "تشيلسي", "Tottenham": "توتنهام",
    "Bayern Munich": "بايرن ميونخ", "Borussia Dortmund": "دورتموند", "Bayer Leverkusen": "ليفركوزن",
    "Hoffenheim": "هوفنهايم", "Stuttgart": "شتوتغارت", "RB Leipzig": "لايبزيغ",
    "PSG": "باريس سان جيرمان", "Marseille": "مارسيليا", "Lyon": "ليون", "Monaco": "موناكو",
    "Al Hilal": "الهلال", "Al Nassr": "النصر", "Al Ittihad": "الاتحاد", "Al Ahli": "الأهلي",
    "Inter": "إنتر", "Juventus": "يوفنتوس", "Milan": "ميلان", "Napoli": "نابولي",
    "Roma": "روما", "Lazio": "لاتسيو", "Atalanta": "أتالانتا", "Fiorentina": "فيورنتينا",
    "Al Shorta": "الشرطة", "Al Quwa Al Jawiya": "القوة الجوية", "Al Zawraa": "الزوراء"
}

async def get_matches():
    try:
        r = requests.get(f"{API_BASE}/fixtures")
        if r.ok: return r.json()
    except Exception as e: print(f"Error: {e}")
    return []

async def extract_stream(page, target_url):
    stream_url = None
    def handle_response(response):
        nonlocal stream_url
        url = response.url
        if any(ext in url for ext in ['.m3u8', '.mpd', '.mp4']):
            if not stream_url: 
                stream_url = url

    page.on("response", handle_response)
    try:
        await page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)
        if not stream_url:
            await page.mouse.click(400, 300)
            await page.wait_for_timeout(5000)
    except Exception as e:
        pass
    finally:
        page.remove_listener("response", handle_response)
    return stream_url

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
    active_matches = [m for m in fixtures if m.get("status") in ["live", "soon"]]
    print(f"📊 إجمالي المباريات: {len(fixtures)} | النشطة: {len(active_matches)}")

    if not active_matches: return

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            proxy={"server": PROXY_URL} if PROXY_URL else None,
            args=["--disable-webrtc", "--no-sandbox"]
        )
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()

        links_to_update = {}
        
        for m in active_matches:
            t1_en = m.get("home", {}).get("name", "")
            t2_en = m.get("away", {}).get("name", "")

            if not t1_en or not t2_en: continue

            # 1. استخدام القاموس
            t1_ar = TEAM_DICT.get(t1_en, t1_en)
            t2_ar = TEAM_DICT.get(t2_en, t2_en)

            print(f"🔍 البحث عن: {t1_ar} ضد {t2_ar}")

            target_url = None
            
            try:
                # 2. فتح الصفحة الرئيسية لموقع koora
                await page.goto("https://koora7goal.com/", wait_until="domcontentloaded", timeout=30000)
                
                # 3. البحث الذكي: نبحث عن رابط (a) يحتوي على نص فيه اسم الفريق الأول
                # محرك Playwright يبحث في كل الصفحة عن النص، وياخذ الرابط التابع له
                locator = page.locator(f"a:has-text('{t1_ar}')").first
                
                if await locator.count() > 0:
                    href = await locator.get_attribute("href")
                    if href:
                        target_url = urljoin("https://koora7goal.com", href)
                        print(f"  -> تم العثور على الرابط: {target_url}")
            except Exception as e:
                print(f"  ⚠️ خطأ في البحث: {e}")

            if target_url:
                stream_url = await extract_stream(page, target_url)
                if stream_url:
                    links_to_update[str(m.get("id"))] = {"link": stream_url, "mode": "embed"}
                    print(f"  ✅ تم التقاط رابط الفيديو!")
                else:
                    print(f"  ⚠️ الصفحة فتحت بس ما لقينا الفيديو.")
            else:
                print(f"  ⚠️ المباراة غير موجودة في الصفحة الرئيسية حالياً.")

        await browser.close()

    if links_to_update:
        print(f"📤 جاري تحديث موقعك بـ {len(links_to_update)} رابط...")
        cfg_res = requests.get(f"{API_BASE}/config")
        cfg = cfg_res.json()
        cfg["links"] = {**cfg.get("links", {}), **links_to_update}
        requests.post(f"{API_BASE}/config", json=cfg, headers={"Authorization": f"Bearer {token}"})
        print("🎉 تم التحديث بنجاح!")
    else:
        print("⚠️ لم يتم العثور على روابط جديدة. (قد لا تكون المباريات معروضة في الصفحة الرئيسية).")

if __name__ == "__main__":
    asyncio.run(main())
