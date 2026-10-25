import os
import re
import json
import asyncio
import requests
from urllib.parse import urljoin, quote
from playwright.async_api import async_playwright

API_BASE = "https://workermatch-config.hs2224008.workers.dev"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
PROXY_URL = os.environ.get("PROXY_URL") # رابط البروكسي مالتك

# 📚 القاموس الشامل للفرق (أكثر من 150 فريق)
TEAM_DICT = {
    # الدوري الإنجليزي
    "Man City": "مانشستر سيتي", "Manchester City": "مانشستر سيتي", "Arsenal": "أرسنال",
    "Liverpool": "ليفربول", "Chelsea": "تشيلسي", "Tottenham": "توتنهام", "Man United": "مانشستر يونايتد",
    "Manchester United": "مانشستر يونايتد", "Newcastle": "نيوكاسل", "Aston Villa": "أستون فيلا",
    "Brighton": "برايتون", "West Ham": "وست هام", "Crystal Palace": "كريستال بالاس",
    "Brentford": "برينتفورد", "Fulham": "فولهام", "Everton": "إيفرتون", "Wolves": "وولفرهامبتون",
    "Bournemouth": "بورنموث", "Nottingham Forest": "نوتينغهام فورست", "Leicester": "ليستر سيتي",
    "Ipswich": "إيبسويتش", "Southampton": "ساوثهامبتون", "Leeds": "ليدز", "Burnley": "بيرنلي",
    "Sheffield Utd": "شيفيلد يونايتد", "Norwich": "نورويتش", "Watford": "واتفورد",
    
    # الدوري الإسباني
    "Real Madrid": "ريال مدريد", "Barcelona": "برشلونة", "Atletico Madrid": "أتلتيكو مدريد",
    "Athletic Club": "أتلتيك بلباو", "Athletic Bilbao": "أتلتيك بلباو", "Real Sociedad": "ريال سوسيداد",
    "Real Betis": "ريال بيتيس", "Villarreal": "فياريال", "Valencia": "فالنسيا",
    "Sevilla": "إشبيلية", "Girona": "جيرونا", "Celta Vigo": "سيلتا فيغو", "Osasuna": "أوساسونا",
    "Mallorca": "مايوركا", "Rayo Vallecano": "رايو فاييكانو", "Getafe": "خيتافي",
    "Alaves": "ألافيس", "Espanyol": "إسبانيول", "Elche": "إلتشي", "Levante": "ليفانتي",
    "Las Palmas": "لاس بالماس", "Valladolid": "بلد الوليد", "Leganes": "ليغانيس",
    "Cadiz": "قادش", "Almeria": "ألميريا", "Granada": "غرناطة",

    # الدوري الإيطالي
    "Inter": "إنتر", "AC Milan": "ميلان", "Milan": "ميلان", "Juventus": "يوفنتوس",
    "Napoli": "نابولي", "Roma": "روما", "Lazio": "لاتسيو", "Atalanta": "أتالانتا",
    "Fiorentina": "فيورنتينا", "Bologna": "بولونيا", "Torino": "تورينو", "Udinese": "أودينيزي",
    "Genoa": "جنوى", "Cagliari": "كالياري", "Verona": "هيلاس فيرونا", "Parma": "بارما",
    "Como": "كومو", "Lecce": "ليتشي", "Sassuolo": "ساسولو", "Cremonese": "كريمونيزي",
    "Pisa": "بيزا", "Empoli": "إمبولي", "Monza": "مونزا", "Venezia": "فينيسيا",

    # الدوري الألماني
    "Bayern Munich": "بايرن ميونخ", "Borussia Dortmund": "دورتموند", "RB Leipzig": "لايبزيغ",
    "Bayer Leverkusen": "ليفركوزن", "Eintracht Frankfurt": "آينتراخت فرانكفورت", "Stuttgart": "شتوتغارت",
    "Freiburg": "فرايبورغ", "Wolfsburg": "فولفسبورغ", "Gladbach": "مونشنغلادباخ",
    "Hoffenheim": "هوفنهايم", "Mainz": "ماينز", "Augsburg": "أوغسبورغ", "Werder Bremen": "فيردر بريمن",
    "Union Berlin": "يونيون برلين", "St Pauli": "سانت باولي", "Heidenheim": "هايدنهايم",
    "FC Koln": "كولن", "Hamburger SV": "هامبورغ", "Holstein Kiel": "هولشتاين كيل", "Bochum": "بوخوم",

    # الدوري الفرنسي
    "PSG": "باريس سان جيرمان", "Paris Saint Germain": "باريس سان جيرمان", "Marseille": "مارسيليا",
    "Lyon": "ليون", "Monaco": "موناكو", "Lille": "ليل", "Nice": "نيس", "Rennes": "رين",
    "Lens": "لانس", "Reims": "ريمس", "Strasbourg": "ستراسبورغ", "Nantes": "نانت",
    "Toulouse": "تولوز", "Montpellier": "مونبلييه", "Brest": "بريست", "Lorient": "لوريان",
    "Angers": "أنجيه", "Auxerre": "أوكسير", "Le Havre": "لوهافر", "Metz": "ميتز",
    "Saint Etienne": "سانت إتيان", "Clermont": "كليرمون",

    # الدوري الهولندي
    "Ajax": "أياكس", "PSV": "آيندهوفن", "Feyenoord": "فاينورد", "AZ Alkmaar": "ألكمار",
    "Twente": "تفنتي", "Utrecht": "أوتريخت", "Sparta Rotterdam": "سبارتا روتردام",

    # الدوري البرتغالي
    "Benfica": "بنفيكا", "Porto": "بورتو", "Sporting CP": "سبورتينغ لشبونة", "Braga": "براغا",
    "Vitoria Guimaraes": "غيماريش", "Casa Pia": "كاسا بيا",

    # الدوري التركي
    "Galatasaray": "غلطة سراي", "Fenerbahce": "فنربخشة", "Besiktas": "بشكتاش", "Trabzonspor": "طرابزون سبور",

    # الدوري السعودي
    "Al Hilal": "الهلال", "Al Nassr": "النصر", "Al Ittihad": "الاتحاد", "Al Ahli": "الأهلي",
    "Al Shabab": "الشباب", "Al Ettifaq": "الاتفاق", "Al Fateh": "الفتح", "Al Taawoun": "التعاون",
    "Al Fayha": "الفيحاء", "Al Khaleej": "الخليج", "Damac": "ضمك", "Al Riyadh": "الرياض",

    # الدوري العراقي
    "Al Shorta": "الشرطة", "Al Quwa Al Jawiya": "القوة الجوية", "Al Zawraa": "الزوراء",
    "Al Talaba": "الطلبة", "Al Najaf": "النجف", "Naft Al Wasat": "نفط الوسط",
    "Naft Maysan": "نفط ميسان", "Al Minaa": "الميناء", "Al Karkh": "الكرخ",
    "Al Kahrabaa": "الكهرباء", "Amanat Baghdad": "أمانة بغداد", "Al Hudood": "الحدود",
    "Al Diwaniya": "الديوانية", "Duhok": "دهوك", "Erbil": "أربيل", "Zakho": "زاخو",
    "Karbala": "كربلاء", "Al Mosul": "الموصل", "Iraq": "العراق",

    # الدوري المصري والمغربي والأفريقي
    "Al Ahly": "الأهلي", "Zamalek": "الزمالك", "Pyramids": "بيراميدز",
    "Wydad": "الوداد", "Raja Casablanca": "الرجاء", "Esperance": "الترجي",
    "Mamelodi Sundowns": "صن داونز", "FUS Rabat": "الفتح الرباطي", "Renaissance Zemamra": "نهضة الزمامرة",

    # الدوري البرازيلي والأرجنتيني والأمريكي
    "Flamengo": "فلامنغو", "Palmeiras": "بالميراس", "Corinthians": "كورنثيانز",
    "Sao Paulo": "ساو باولو", "Santos": "سانتوس", "Fluminense": "فلوميننسي",
    "Botafogo": "بوتافوغو", "Vasco": "فاسكو دا غاما", "Gremio": "غريميو",
    "Internacional": "إنترناسيونال", "Atletico Mineiro": "أتلتيكو مينيرو",
    "Cruzeiro": "كروزيرو", "Bahia": "باهيا", "Fortaleza": "فورتاليزا",
    "Bragantino": "براغانتينو", "Chapecoense": "شابيكوينسي", "Mirassol": "ميراسول",
    "Inter Miami": "إنتر ميامي", "Boca Juniors": "بوكا جونيورز", "River Plate": "ريفر بليت",
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

            t1_ar = TEAM_DICT.get(t1_en, t1_en)
            t2_ar = TEAM_DICT.get(t2_en, t2_en)

            print(f"🔍 البحث عن: {t1_ar} ضد {t2_ar}")

            target_url = None
            try:
                await page.goto("https://koora7goal.com/", wait_until="domcontentloaded", timeout=30000)
                # نبحث عن الفريق الأول أو الثاني
                locator = page.locator(f"a:has-text('{t1_ar}')").first
                if await locator.count() == 0:
                    locator = page.locator(f"a:has-text('{t2_ar}')").first
                
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
                    # 🔥 الحل السحري للشاشة السوداء: تمرير الرابط عبر البروكسي مالتك
                    if PROXY_URL:
                        final_link = f"{PROXY_URL}/?u={quote(stream_url)}"
                        print(f"  🛡️ تم تمرير الرابط عبر البروكسي")
                    else:
                        final_link = stream_url
                    
                    links_to_update[str(m.get("id"))] = {"link": final_link, "mode": "embed"}
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
        print("⚠️ لم يتم العثور على روابط جديدة.")

if __name__ == "__main__":
    asyncio.run(main())
