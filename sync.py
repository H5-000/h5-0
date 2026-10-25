import os
import re
import asyncio
import requests
from playwright.async_api import async_playwright
from deep_translator import MyMemoryTranslator
from rapidfuzz import fuzz

API_BASE = "https://workermatch-config.hs2224008.workers.dev"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
PROXY_URL = os.environ.get("PROXY_URL")

# قاموس احتياطي لأشهر الفرق (لأن الترجمة الآلية أحياناً تترجمها غلط)
# مثلاً Athletic تترجم إلى "ألعاب القوى" بدل "أتلتيك"
TEAM_DICT = {
    "Getafe": "خيتافي", "Athletic Bilbao": "أتلتيك بيلباو", "Athletic Club": "أتلتيك بيلباو",
    "PSV": "آيندهوفن", "Feyenoord": "فاينورد", "Bournemouth": "بورنموث",
    "Manchester United": "مانشستر يونايتد", "Man United": "مانشستر يونايتد", "Liverpool": "ليفربول",
    "Brighton": "برايتون", "Newcastle": "نيوكاسل", "Crystal Palace": "كريستال بالاس",
    "Real Madrid": "ريال مدريد", "Barcelona": "برشلونة", "Atletico Madrid": "أتلتيكو مدريد",
    "Man City": "مانشستر سيتي", "Arsenal": "أرسنال", "Chelsea": "تشيلسي", "Tottenham": "توتنهام",
    "Bayern Munich": "بايرن ميونخ", "Borussia Dortmund": "دورتموند", "PSG": "باريس سان جيرمان",
    "Al Hilal": "الهلال", "Al Nassr": "النصر", "Al Ittihad": "الاتحاد", "Al Ahli": "الأهلي",
}

def normalize_arabic(text):
    if not text: return ""
    text = re.sub(r"[أإآا]", "ا", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"ى", "ي", text)
    text = re.sub(r"\s+", "", text)
    return text

def translate_name(name):
    # إذا الفريق موجود بالقاموس الاحتياطي، نستخدمه مباشرة
    if name in TEAM_DICT:
        return TEAM_DICT[name]
    
    # إذا مو موجود، نستخدم مكتبة MyMemory (أكثر استقراراً من جوجل في GitHub)
    try:
        translated = MyMemoryTranslator(source='en-GB', target='ar-SA').translate(name)
        return translated if translated else name
    except:
        return name

async def get_matches():
    try:
        r = requests.get(f"{API_BASE}/fixtures")
        if r.ok: return r.json()
    except Exception as e: print(f"Error: {e}")
    return []

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
            # نسحب الروابط اللي شكلها تبدو كمباريات فقط
            all_links = await page.evaluate('''() => {
                return Array.from(document.querySelectorAll('a')).map(a => ({text: a.innerText.trim(), href: a.href}));
            }''')
            print(f"✅ تم سحب {len(all_links)} رابط من الصفحة الرئيسية.")
        except Exception as e:
            print(f"❌ فشل فتح الصفحة الرئيسية: {e}")
            await browser.close()
            return

        for m in active_matches:
            t1_en = m.get("home", {}).get("name")
            t2_en = m.get("away", {}).get("name")
            if not t1_en or not t2_en: continue
            
            ar_t1 = translate_name(t1_en)
            ar_t2 = translate_name(t2_en)
            
            norm_t1 = normalize_arabic(ar_t1)
            norm_t2 = normalize_arabic(ar_t2)
            
            print(f"🔍 جاري البحث عن: {ar_t1} ضد {ar_t2} (الأصل: {t1_en} vs {t2_en})")
            
            target_url = None
            best_score = 0
            
            for link in all_links:
                if not link['text'] or len(link['text']) < 5: continue
                
                norm_link_text = normalize_arabic(link['text'])
                
                # 1. التطابق المباشر: إذا لقينا اسم الفريقين معاً
                if norm_t1 in norm_link_text and norm_t2 in norm_link_text:
                    target_url = link['href']
                    best_score = 100
                    break
                
                # 2. التطابق الذكي: حساب نسبة التشابه
                score1 = fuzz.token_set_ratio(norm_t1, norm_link_text)
                score2 = fuzz.token_set_ratio(norm_t2, norm_link_text)
                combined_score = (score1 + score2) / 2
                
                if combined_score > 75 and combined_score > best_score:
                    best_score = combined_score
                    target_url = link['href']
            
            if target_url:
                try:
                    print(f"  -> دخول لصفحة المباراة (نسبة التطابق: {round(best_score)}%)...")
                    await page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
                    
                    try:
                        iframe_element = await page.wait_for_selector("iframe", timeout=6000)
                        src = await iframe_element.get_attribute("src")
                        if src:
                            if src.startswith("//"): src = "https:" + src
                            links_to_update[str(m.get("id"))] = {"link": src, "mode": "embed"}
                            print(f"  ✅ تم إيجاد الرابط!")
                    except:
                        print(f"  ⚠️ الصفحة فتحت بس الفيديو ما ظهر (المباراة يمكن ما بدأت).")
                except Exception as e:
                    print(f"  ❌ خطأ بالدخول: {e}")
            else:
                print(f"  ⚠️ لم نجد أي رابط يتطابق ولو بنسبة 75%.")

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
