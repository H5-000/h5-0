import os
import re
import json
import asyncio
import requests
from playwright.async_api import async_playwright
from deep_translator import MyMemoryTranslator
from rapidfuzz import fuzz, process

API_BASE = "https://workermatch-config.hs2224008.workers.dev"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
PROXY_URL = os.environ.get("PROXY_URL")

# ملف ذاكرة التطابق (يتم إنشاؤه تلقائياً)
MAPPING_FILE = "mapping.json"
mapping = {}
if os.path.exists(MAPPING_FILE):
    with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
        mapping = json.load(f)

def save_mapping():
    with open(MAPPING_FILE, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

def normalize_arabic(text):
    if not text: return ""
    text = re.sub(r"[أإآا]", "ا", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"ى", "ي", text)
    text = re.sub(r"\s+", "", text)
    return text

def translate_name(name):
    # 1. البحث في ذاكرة التطابق
    if name in mapping:
        return mapping[name]
    # 2. الترجمة الآلية كخيار أخير
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

async def extract_stream_from_page(page, url):
    """زيارة صفحة المباراة واستخراج رابط البث (iframe)"""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        # انتظار ظهور iframe (بحد أقصى 8 ثواني)
        try:
            iframe_element = await page.wait_for_selector("iframe", timeout=8000)
            src = await iframe_element.get_attribute("src")
            if src:
                if src.startswith("//"): src = "https:" + src
                return src
        except:
            # محاولة البحث في الإطارات المتداخلة
            for frame in page.frames:
                if frame.url and frame.url != "about:blank":
                    try:
                        video = await frame.query_selector("video source")
                        if video:
                            return await video.get_attribute("src")
                    except: pass
        return None
    except Exception as e:
        print(f"  ❌ خطأ في فتح الصفحة: {e}")
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
    active_matches = [m for m in fixtures if m.get("status") in ["live", "soon"]]
    print(f"📊 إجمالي المباريات: {len(fixtures)} | المباريات النشطة: {len(active_matches)}")

    if not active_matches:
        print("⚠️ لا توجد مباريات مباشرة أو قادمة حالياً.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            proxy={"server": PROXY_URL} if PROXY_URL else None,
            args=["--disable-webrtc", "--no-sandbox"]
        )
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()
        await page.route("**/*", block_heavy_resources)

        # 1. سحب جميع روابط المباريات من الصفحة الرئيسية
        print("🌐 جاري سحب روابط المباريات من koora7goal...")
        try:
            await page.goto("https://koora7goal.com/", wait_until="domcontentloaded", timeout=30000)
            all_links = await page.evaluate('''() => {
                return Array.from(document.querySelectorAll('a')).map(a => ({
                    text: a.innerText.trim(),
                    href: a.href
                })).filter(l => l.text.length > 3 && l.href.includes('koora7goal'));
            }''')
            print(f"✅ تم سحب {len(all_links)} رابط.")
        except Exception as e:
            print(f"❌ فشل فتح الصفحة الرئيسية: {e}")
            await browser.close()
            return

        links_to_update = {}
        matched_count = 0

        for m in active_matches:
            t1_en = m.get("home", {}).get("name")
            t2_en = m.get("away", {}).get("name")
            if not t1_en or not t2_en: continue

            # الحصول على الاسم العربي (من الذاكرة أو الترجمة)
            ar_t1 = translate_name(t1_en)
            ar_t2 = translate_name(t2_en)
            norm_t1 = normalize_arabic(ar_t1)
            norm_t2 = normalize_arabic(ar_t2)

            print(f"🔍 البحث عن: {ar_t1} ضد {ar_t2} (الأصل: {t1_en} vs {t2_en})")

            target_url = None
            best_score = 0
            best_link_text = ""

            for link in all_links:
                norm_link_text = normalize_arabic(link['text'])

                # المطابقة المباشرة
                if norm_t1 in norm_link_text and norm_t2 in norm_link_text:
                    target_url = link['href']
                    best_score = 100
                    best_link_text = link['text']
                    break

                # المطابقة الضبابية
                score1 = fuzz.token_set_ratio(norm_t1, norm_link_text)
                score2 = fuzz.token_set_ratio(norm_t2, norm_link_text)
                combined_score = (score1 + score2) / 2

                if combined_score > 60 and combined_score > best_score:
                    best_score = combined_score
                    target_url = link['href']
                    best_link_text = link['text']

            if target_url:
                print(f"  -> دخول لصفحة المباراة (تطابق: {round(best_score)}%): {best_link_text}")
                stream_url = await extract_stream_from_page(page, target_url)
                if stream_url:
                    links_to_update[str(m.get("id"))] = {"link": stream_url, "mode": "embed"}
                    print(f"  ✅ تم إيجاد الرابط!")
                    # حفظ التعيين في الذاكرة إذا كانت المطابقة نصية
                    if best_score == 100:
                        mapping[t1_en] = ar_t1
                        mapping[t2_en] = ar_t2
                        matched_count += 1
                else:
                    print(f"  ⚠️ لم يتم العثور على iframe في الصفحة.")
            else:
                print(f"  ⚠️ لا يوجد رابط مطابق.")

        await browser.close()

    if matched_count > 0:
        save_mapping()
        print(f"💾 تم حفظ {matched_count} تعيين جديد في mapping.json")

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
