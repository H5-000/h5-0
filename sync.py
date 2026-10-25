import os
import re
import json
import asyncio
import requests
from playwright.async_api import async_playwright
from rapidfuzz import fuzz
from deep_translator import MyMemoryTranslator
from bs4 import BeautifulSoup

API_BASE = "https://workermatch-config.hs2224008.workers.dev"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
PROXY_URL = os.environ.get("PROXY_URL")

# تحميل قاموس الأسماء
TEAMS_FILE = 'teams_ar.json'
if os.path.exists(TEAMS_FILE):
    with open(TEAMS_FILE, 'r', encoding='utf-8') as f:
        TEAM_MAP = json.load(f)
else:
    TEAM_MAP = {}

def save_teams():
    with open(TEAMS_FILE, 'w', encoding='utf-8') as f:
        json.dump(TEAM_MAP, f, ensure_ascii=False, indent=2)

def normalize_arabic(text):
    if not text: return ""
    text = re.sub(r'[\u064B-\u065F\u0670]', '', text)
    text = re.sub(r'[أإآ]', 'ا', text)
    text = re.sub(r'ة', 'ه', text)
    text = re.sub(r'ى', 'ي', text)
    text = re.sub(r'\s+', '', text)
    return text

async def get_matches():
    try:
        r = requests.get(f"{API_BASE}/fixtures")
        if r.ok: return r.json()
    except Exception as e: print(f"Error: {e}")
    return []

# دالة استخراج البث
async def extract_stream(page, target_url):
    stream_url = None
    async def handle_response(response):
        nonlocal stream_url
        url = response.url
        if any(ext in url for ext in ['.m3u8', '.mpd', 'embed', 'player']):
            if not stream_url: stream_url = url

    page.on("response", handle_response)
    try:
        await page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(4000)
        if not stream_url:
            iframe = await page.query_selector("iframe")
            if iframe:
                src = await iframe.get_attribute("src")
                if src:
                    if src.startswith("//"): src = "https:" + src
                    stream_url = src
    except Exception as e:
        print(f"  ❌ خطأ: {e}")
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
        await page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"] else route.continue_())

        print("🌐 جاري سحب وتحليل كود صفحة koora7goal...")
        try:
            # انتظار أطول لضمان تحميل المباريات عبر جافاسكربت
            await page.goto("https://koora7goal.com/", wait_until="networkidle", timeout=30000)
            
            # استخدام BeautifulSoup لتحليل كامل كود الصفحة
            html_content = await page.content()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # استخراج كل الروابط التي تحتوي على نص عربي
            all_links = []
            for a_tag in soup.find_all('a', href=True):
                link_text = a_tag.get_text(strip=True)
                if link_text and len(link_text) > 3:
                    all_links.append({'text': link_text, 'href': a_tag['href']})
            
            print(f"✅ تم سحب {len(all_links)} رابط يحتوي على نص عربي.")
        except Exception as e:
            print(f"❌ فشل تحليل الصفحة: {e}")
            await browser.close()
            return

        links_to_update = {}
        
        for m in active_matches:
            t1_id = str(m.get("home", {}).get("id", ""))
            t2_id = str(m.get("away", {}).get("id", ""))
            t1_en = m.get("home", {}).get("name", "")
            t2_en = m.get("away", {}).get("name", "")

            if not t1_en or not t2_en: continue

            t1_ar = TEAM_MAP.get(t1_id)
            t2_ar = TEAM_MAP.get(t2_id)

            if not t1_ar:
                try: t1_ar = MyMemoryTranslator(source='en-GB', target='ar-SA').translate(t1_en)
                except: t1_ar = t1_en
                TEAM_MAP[t1_id] = t1_ar
            
            if not t2_ar:
                try: t2_ar = MyMemoryTranslator(source='en-GB', target='ar-SA').translate(t2_en)
                except: t2_ar = t2_en
                TEAM_MAP[t2_id] = t2_ar

            print(f"🔍 البحث عن: {t1_ar} ضد {t2_ar}")

            target_url = None
            best_score = 0
            
            # البحث عن أفضل تطابق بين النص المستخرج والاسم العربي
            for link in all_links:
                norm_link = normalize_arabic(link['text'])
                score1 = fuzz.token_set_ratio(normalize_arabic(t1_ar), norm_link)
                score2 = fuzz.token_set_ratio(normalize_arabic(t2_ar), norm_link)
                combined = (score1 + score2) / 2

                # خفضنا العتبة إلى 55% لأننا نبحث الآن في كامل كود الصفحة
                if combined > 55 and combined > best_score:
                    best_score = combined
                    target_url = link['href']

            if target_url:
                print(f"  -> تطابق {round(best_score)}%: {target_url}")
                stream_url = await extract_stream(page, target_url)
                if stream_url:
                    links_to_update[str(m.get("id"))] = {"link": stream_url, "mode": "embed"}
                    print(f"  ✅ تم إيجاد الرابط!")
                else:
                    print(f"  ⚠️ الصفحة فتحت بس الفيديو ما ظهر.")
            else:
                print(f"  ⚠️ لا يوجد تطابق كافٍ (أعلى نسبة: {round(best_score)}%).")

        await browser.close()

    save_teams()

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
