import os
import re
import json
import asyncio
import requests
from urllib.parse import urljoin, quote
from playwright.async_api import async_playwright
from rapidfuzz import fuzz
from bs4 import BeautifulSoup

API_BASE = "https://workermatch-config.hs2224008.workers.dev"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
PROXY_URL = os.environ.get("PROXY_URL") # هذا خاص بتشغيل الفيديو فقط

# 📚 القاموس الشامل للفرق
TEAM_DICT = {
    "Man City": "مانشستر سيتي", "Arsenal": "أرسنال", "Liverpool": "ليفربول", "Chelsea": "تشيلسي",
    "Tottenham": "توتنهام", "Man United": "مانشستر يونايتد", "Newcastle": "نيوكاسل", "Aston Villa": "أستون فيلا",
    "Brighton": "برايتون", "West Ham": "وست هام", "Crystal Palace": "كريستال بالاس", "Brentford": "برينتفورد",
    "Fulham": "فولهام", "Everton": "إيفرتون", "Wolves": "وولفرهامبتون", "Bournemouth": "بورنموث",
    "Nottingham Forest": "نوتينغهام فورست", "Leicester": "ليستر سيتي", "Southampton": "ساوثهامبتون",
    "Leeds": "ليدز", "Sunderland": "سندرلاند", "Real Madrid": "ريال مدريد", "Barcelona": "برشلونة",
    "Atletico Madrid": "أتلتيكو مدريد", "Athletic Club": "أتلتيك بلباو", "Real Sociedad": "ريال سوسيداد",
    "Real Betis": "ريال بيتيس", "Villarreal": "فياريال", "Valencia": "فالنسيا", "Sevilla": "إشبيلية",
    "Girona": "جيرونا", "Celta Vigo": "سيلتا فيغو", "Osasuna": "أوساسونا", "Mallorca": "مايوركا",
    "Rayo Vallecano": "رايو فاييكانو", "Getafe": "خيتافي", "Espanyol": "إسبانيول", "Inter": "إنتر",
    "AC Milan": "ميلان", "Juventus": "يوفنتوس", "Napoli": "نابولي", "Roma": "روما", "Lazio": "لاتسيو",
    "Atalanta": "أتالانتا", "Fiorentina": "فيورنتينا", "Bologna": "بولونيا", "Torino": "تورينو",
    "Udinese": "أودينيزي", "Genoa": "جنوى", "Cagliari": "كالياري", "Lecce": "ليتشي", "Monza": "مونزا",
    "Venezia": "فينيسيا", "Bayern Munich": "بايرن ميونخ", "Borussia Dortmund": "دورتموند", "RB Leipzig": "لايبزيغ",
    "Bayer Leverkusen": "ليفركوزن", "Eintracht Frankfurt": "آينتراخت فرانكفورت", "Stuttgart": "شتوتغارت",
    "Freiburg": "فرايبورغ", "Wolfsburg": "فولفسبورغ", "Gladbach": "مونشنغلادباخ", "Hoffenheim": "هوفنهايم",
    "Mainz": "ماينز", "Augsburg": "أوغسبورغ", "Werder Bremen": "فيردر بريمن", "Union Berlin": "يونيون برلين",
    "PSG": "باريس سان جيرمان", "Marseille": "مارسيليا", "Lyon": "ليون", "Monaco": "موناكو", "Lille": "ليل",
    "Nice": "نيس", "Rennes": "رين", "Lens": "لانس", "Reims": "ريمس", "Strasbourg": "ستراسبورغ",
    "Nantes": "نانت", "Toulouse": "تولوز", "Montpellier": "مونبلييه", "Brest": "بريست", "Lorient": "لوريان",
    "Ajax": "أياكس", "PSV": "آيندهوفن", "Feyenoord": "فاينورد", "Benfica": "بنفيكا", "Porto": "بورتو",
    "Sporting CP": "سبورتينغ لشبونة", "Braga": "براغا", "Galatasaray": "غلطة سراي", "Fenerbahce": "فنربخشة",
    "Besiktas": "بشكتاش", "Al Hilal": "الهلال", "Al Nassr": "النصر", "Al Ittihad": "الاتحاد", "Al Ahli": "الأهلي",
    "Al Shorta": "الشرطة", "Al Quwa Al Jawiya": "القوة الجوية", "Al Zawraa": "الزوراء", "Al Talaba": "الطلبة",
    "Al Najaf": "النجف", "Al Ahly": "الأهلي", "Zamalek": "الزمالك", "Pyramids": "بيراميدز", "Wydad": "الوداد",
    "Raja Casablanca": "الرجاء", "Esperance": "الترجي", "TP Mazembe": "تي بي مازيمبي", "Flamengo": "فلامنغو",
    "Palmeiras": "بالميراس", "Corinthians": "كورنثيانز", "Sao Paulo": "ساو باولو", "Santos": "سانتوس",
    "Falamicão": "فلامينغو", "CD Nacional": "ناسيونال", "AZ Alkmaar": "ألكمار", "Parma": "بارما",
    "Casa Pia": "كاسا بيا", "Stoke": "ستوك سيتي", "Preston": "بريستون", "Lincoln City": "لينكولن",
    "Birmingham": "برمنغهام", "Auxerre": "أوكسير", "Le Havre": "لوهافر", "Monza": "مونزا",
    "Sheffield Utd": "شيفيلد يونايتد", "Wrexham": "ريكسهام", "Mainz": "ماينز", "Elversberg": "إلفرسبيرغ",
    "Villarreal": "فياريال", "Espanyol": "إسبانيول", "Norwich": "نورويتش", "Watford": "واتفورد"
}

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

async def extract_stream(page, target_url):
    stream_url = None
    def handle_response(response):
        nonlocal stream_url
        url = response.url
        if any(ext in url for ext in ['.m3u8', '.mpd', '.mp4']):
            if not stream_url: stream_url = url

    page.on("response", handle_response)
    try:
        await page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)
        if not stream_url:
            await page.mouse.click(400, 300)
            await page.wait_for_timeout(5000)
    except Exception:
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
        # ⚠️ تم إزالة البروكسي من هنا لكي لا يحدث خطأ في فتح الصفحة
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-webrtc", "--no-sandbox"]
        )
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()

        print("🌐 جاري سحب كافة الروابط من الصفحة الرئيسية...")
        try:
            await page.goto("https://koora7goal.com/", wait_until="networkidle", timeout=30000)
            html_content = await page.content()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            all_links = []
            for a_tag in soup.find_all('a', href=True):
                link_text = a_tag.get_text(strip=True)
                href = a_tag['href']
                
                if not link_text or len(link_text) < 5: continue
                if "بث مباشر" in link_text or "مباريات اليوم" in link_text: continue
                
                full_url = urljoin("https://koora7goal.com", href)
                all_links.append({'text': link_text, 'href': full_url})
            
            print(f"✅ تم سحب {len(all_links)} رابط من الصفحة.")
        except Exception as e:
            print(f"❌ فشل فتح الموقع: {e}")
            await browser.close()
            return

        links_to_update = {}
        
        for m in active_matches:
            t1_en = m.get("home", {}).get("name", "")
            t2_en = m.get("away", {}).get("name", "")
            if not t1_en or not t2_en: continue

            t1_ar = TEAM_DICT.get(t1_en, t1_en)
            t2_ar = TEAM_DICT.get(t2_en, t2_en)
            match_name_ar = f"{t1_ar} {t2_ar}"
            
            print(f"🔍 البحث عن: {t1_ar} ضد {t2_ar}")

            target_url = None
            best_score = 0
            
            for link in all_links:
                norm_link_text = normalize_arabic(link['text'])
                norm_match_name = normalize_arabic(match_name_ar)
                
                score = fuzz.token_set_ratio(norm_match_name, norm_link_text)
                
                if score > 65 and score > best_score:
                    best_score = score
                    target_url = link['href']

            if target_url:
                print(f"  -> تطابق {round(best_score)}%: {target_url}")
                stream_url = await extract_stream(page, target_url)
                if stream_url:
                    # هنا نستخدم البروكسي لكي يعمل الفيديو بموقعك
                    final_link = f"{PROXY_URL}/?u={quote(stream_url)}" if PROXY_URL else stream_url
                    links_to_update[str(m.get("id"))] = {"link": final_link, "mode": "embed"}
                    print(f"  ✅ تم التقاط الفيديو وتمريره عبر البروكسي!")
                else:
                    print(f"  ⚠️ الصفحة فتحت بس ما لقينا الفيديو.")
            else:
                print(f"  ⚠️ المباراة غير موجودة حالياً في الصفحة الرئيسية.")

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
