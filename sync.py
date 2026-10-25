import os
import re
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

# دالة تنظيف النصوص العربية (تتجاهل الهمزات والمسافات والتاء المربوطة)
def normalize_arabic(text):
    if not text: return ""
    text = re.sub(r"[أإآا]", "ا", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"ى", "ي", text)
    text = re.sub(r"\s+", "", text) # حذف كل المسافات
    return text

async def get_matches():
    try:
        r = requests.get(f"{API_BASE}/fixtures")
        if r.ok: return r.json()
    except Exception as e: print(f"Error: {e}")
    return []

# دالة تسريع المتصفح (تمنع تحميل الصور والإعلانات)
async def block_heavy_resources(route):
    if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
        await route.abort()
    else:
        await route.continue_()

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
    print(f"📊 إجمالي المباريات: {len(fixtures)} | المباريات النشطة: {len(active_matches)}")

    if not active_matches:
        print("⚠️ لا توجد مباريات مباشرة أو قادمة حالياً.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            proxy={"server": PROXY_URL} if PROXY_URL else None
        )
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()
        
        await page.route("**/*", block_heavy_resources)

        links_to_update = {}
        
        print("🌐 جاري فتح الصفحة الرئيسية وسحب الروابط...")
        try:
            await page.goto("https://koora7goal.com/", wait_until="domcontentloaded", timeout=30000)
            all_links = await page.evaluate('''() => {
                return Array.from(document.querySelectorAll('a')).map(a => ({text: a.innerText, href: a.href}));
            }''')
            print(f"✅ تم سحب {len(all_links)} رابط من الصفحة الرئيسية.")
        except Exception as e:
            print(f"❌ فشل فتح الصفحة الرئيسية: {e}")
            await browser.close()
            return

        for m in active_matches:
            t1 = m.get("home", {}).get("name")
            t2 = m.get("away", {}).get("name")
            if not t1 or not t2: continue
            
            ar_t1 = TEAM_DICT.get(t1, t1)
            ar_t2 = TEAM_DICT.get(t2, t2)
            
            # تنظيف الأسماء للبحث الدقيق
            norm_t1 = normalize_arabic(ar_t1)
            norm_t2 = normalize_arabic(ar_t2)
            
            print(f"🔍 جاري البحث عن رابط: {ar_t1} ضد {ar_t2}")
            
            target_url = None
            for link in all_links:
                # السر هنا: نطلب وجود اسم الفريقين معاً في الرابط
                norm_link_text = normalize_arabic(link['text'])
                if norm_t1 in norm_link_text and norm_t2 in norm_link_text:
                    target_url = link['href']
                    break
            
            if target_url:
                try:
                    print(f"  -> دخول لصفحة المباراة...")
                    await page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
                    
                    try:
                        # ننتظر ظهور الـ iframe (شاشة البث)
                        iframe_element = await page.wait_for_selector("iframe", timeout=5000)
                        src = await iframe_element.get_attribute("src")
                        if src:
                            if src.startswith("//"): src = "https:" + src
                            links_to_update[str(m.get("id"))] = {"link": src, "mode": "embed"}
                            print(f"  ✅ تم إيجاد الرابط وتخصيصه بدقة!")
                    except:
                        print(f"  ⚠️ الصفحة فتحت بس الفيديو ما ظهر.")
                except Exception as e:
                    print(f"  ❌ خطأ بالدخول: {e}")
            else:
                print(f"  ⚠️ لم نجد رابط يطابق الفريقين معاً.")

        await browser.close()

    if links_to_update:
        print(f"📤 جاري تحديث موقعك بـ {len(links_to_update)} رابط...")
        cfg_res = requests.get(f"{API_BASE}/config")
        cfg = cfg_res.json()
        cfg["links"] = {**cfg.get("links", {}), **links_to_update}
        requests.post(f"{API_BASE}/config", json=cfg, headers={"Authorization": f"Bearer {token}"})
        print("🎉 تم التحديث بنجاح! الروابط مخصصة بدقة.")
    else:
        print("⚠️ لم يتم العثور على روابط جديدة.")

if __name__ == "__main__":
    asyncio.run(main())
