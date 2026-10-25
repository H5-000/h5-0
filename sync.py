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
PROXY_URL = os.environ.get("PROXY_URL") 

# 📚 القاموس الشامل (تمت إضافة الفرق اللي بالصورة والكثير غيرها)
TEAM_DICT = {
    # الدوري الفرنسي
    "Strasbourg": "ستراسبورغ", "Rennes": "رين", "Troyes": "تروا", "Toulouse": "تولوز", 
    "PSG": "باريس سان جيرمان", "Marseille": "مارسيليا", "Lyon": "ليون", "Monaco": "موناكو", 
    "Lille": "ليل", "Nice": "نيس", "Lens": "لانس", "Reims": "ريمس", "Nantes": "نانت", 
    "Montpellier": "مونبلييه", "Brest": "بريست", "Lorient": "لوريان", "Auxerre": "أوكسير", 
    "Le Havre": "لوهافر", "Metz": "ميتز", "Saint Etienne": "سانت إتيان", "Clermont": "كليرمون",
    
    # الدوري الإنجليزي
    "Leeds": "ليدز", "Leeds United": "ليدز يونايتد", "Sunderland": "سندرلاند",
    "Man City": "مانشستر سيتي", "Manchester City": "مانشستر سيتي", "Arsenal": "أرسنال",
    "Liverpool": "ليفربول", "Chelsea": "تشيلسي", "Tottenham": "توتنهام", "Man United": "مانشستر يونايتد",
    "Manchester United": "مانشستر يونايتد", "Newcastle": "نيوكاسل", "Aston Villa": "أستون فيلا",
    "Brighton": "برايتون", "West Ham": "وست هام", "Crystal Palace": "كريستال بالاس",
    "Brentford": "برينتفورد", "Fulham": "فولهام", "Everton": "إيفرتون", "Wolves": "وولفرهامبتون",
    "Bournemouth": "بورنموث", "Nottingham Forest": "نوتينغهام فورست", "Leicester": "ليستر سيتي",
    "Southampton": "ساوثهامبتون", "Sheffield Utd": "شيفيلد يونايتد", "Norwich": "نورويتش", 
    "Watford": "واتفورد", "Stoke": "ستوك سيتي", "Preston": "بريستون", "Birmingham": "برمنغهام",
    "Wrexham": "ريكسهام", "Lincoln City": "لينكولن",
    
    # الدوري الألماني
    "Freiburg": "فرايبورغ", "Bayern Munich": "بايرن ميونخ", "Borussia Dortmund": "دورتموند", 
    "RB Leipzig": "لايبزيغ", "Bayer Leverkusen": "ليفركوزن", "Eintracht Frankfurt": "آينتراخت فرانكفورت", 
    "Stuttgart": "شتوتغارت", "Wolfsburg": "فولفسبورغ", "Gladbach": "مونشنغلادباخ", "Hoffenheim": "هوفنهايم",
    "Mainz": "ماينز", "Augsburg": "أوغسبورغ", "Werder Bremen": "فيردر بريمن", "Union Berlin": "يونيون برلين",
    "St Pauli": "سانت باولي", "Heidenheim": "هايدنهايم", "FC Koln": "كولن", "Hamburger SV": "هامبورغ", 
    "Holstein Kiel": "هولشتاين كيل", "Bochum": "بوخوم", "Elversberg": "إلفرسبيرغ",
    
    # الدوري الإيطالي
    "Lecce": "ليتشي", "Juventus": "يوفنتوس", "Inter": "إنتر", "AC Milan": "ميلان", 
    "Napoli": "نابولي", "Roma": "روما", "Lazio": "لاتسيو", "Atalanta": "أتالانتا",
    "Fiorentina": "فيورنتينا", "Bologna": "بولونيا", "Torino": "تورينو", "Udinese": "أودينيزي",
    "Genoa": "جنوى", "Cagliari": "كالياري", "Verona": "هيلاس فيرونا", "Parma": "بارما",
    "Como": "كومو", "Sassuolo": "ساسولو", "Cremonese": "كريمونيزي", "Pisa": "بيزا", 
    "Empoli": "إمبولي", "Monza": "مونزا", "Venezia": "فينيسيا",
    
    # الدوري الإسباني
    "Real Madrid": "ريال مدريد", "Barcelona": "برشلونة", "Atletico Madrid": "أتلتيكو مدريد",
    "Athletic Club": "أتلتيك بلباو", "Real Sociedad": "ريال سوسيداد", "Real Betis": "ريال بيتيس", 
    "Villarreal": "فياريال", "Valencia": "فالنسيا", "Sevilla": "إشبيلية", "Girona": "جيرونا", 
    "Celta Vigo": "سيلتا فيغو", "Osasuna": "أوساسونا", "Mallorca": "مايوركا", "Rayo Vallecano": "رايو فاييكانو", 
    "Getafe": "خيتافي", "Alaves": "ألافيس", "Espanyol": "إسبانيول", "Elche": "إلتشي", "Levante": "ليفانتـي",
    "Las Palmas": "لاس بالماس", "Valladolid": "بلد الوليد", "Leganes": "ليغانيس", "Cadiz": "قادش", 
    "Almeria": "ألميريا", "Granada": "غرناطة",
    
    # أفريقيا والبرازيل وغيرها
    "TP Mazembe": "تي بي مازيمبي", "Club Africain": "النادي الإفريقي", "Al Ahly": "الأهلي", 
    "Zamalek": "الزمالك", "Pyramids": "بيراميدز", "Wydad": "الوداد", "Raja Casablanca": "الرجاء", 
    "Esperance": "الترجي", "Mamelodi Sundowns": "صن داونز", "Flamengo": "فلامنغو", "Palmeiras": "بالميراس", 
    "Corinthians": "كورنثيانز", "Sao Paulo": "ساو باولو", "Santos": "سانتوس", "Fluminense": "فلوميننسي",
    "Botafogo": "بوتافوغو", "Vasco": "فاسكو دا غاما", "Gremio": "غريميو", "Internacional": "إنترناسيونال", 
    "Atletico Mineiro": "أتلتيكو مينيرو", "Cruzeiro": "كروزيرو", "Bahia": "باهيا", "Fortaleza": "فورتاليزا",
    "Bragantino": "براغانتينو", "Chapecoense": "شابيكوينسي", "Mirassol": "ميراسول", "Inter Miami": "إنتر ميامي",
    "Boca Juniors": "بوكا جونيورز", "River Plate": "ريفر بليت",
    
    # آسيا والهلال والنصر
    "Al Hilal": "الهلال", "Al Nassr": "النصر", "Al Ittihad": "الاتحاد", "Al Ahli": "الأهلي",
    "Al Shabab": "الشباب", "Al Ettifaq": "الاتفاق", "Al Fateh": "الفتح", "Al Taawoun": "التعاون",
    "Al Shorta": "الشرطة", "Al Quwa Al Jawiya": "القوة الجوية", "Al Zawraa": "الزوراء", 
    "Al Talaba": "الطلبة", "Al Najaf": "النجف", "Naft Al Wasat": "نفط الوسط", "Naft Maysan": "نفط ميسان", 
    "Al Minaa": "الميناء", "Al Karkh": "الكرخ", "Al Kahrabaa": "الكهرباء", "Amanat Baghdad": "أمانة بغداد", 
    "Al Hudood": "الحدود", "Al Diwaniya": "الديوانية", "Duhok": "دهوك", "Erbil": "أربيل", "Zakho": "زاخو",
    "Karbala": "كربلاء", "Al Mosul": "الموصل", "Iraq": "العراق",
    
    # أوروبا
    "Ajax": "أياكس", "PSV": "آيندهوفن", "Feyenoord": "فاينورد", "AZ Alkmaar": "ألكمار",
    "Twente": "تفنتي", "Utrecht": "أوتريخت", "Sparta Rotterdam": "سبارتا روتردام",
    "Benfica": "بنفيكا", "Porto": "بورتو", "Sporting CP": "سبورتينغ لشبونة", "Braga": "براغا",
    "Vitoria Guimaraes": "غيماريش", "Casa Pia": "كاسا بيا", "Galatasaray": "غلطة سراي", 
    "Fenerbahce": "فنربخشة", "Besiktas": "بشكتاش", "Trabzonspor": "طرابزون سبور",
    "Shakhtar": "شاختار", "Dinamo Kyiv": "دينامو كييف", "Salzburg": "سالزبورغ", "Young Boys": "يونغ بويز",
    "Basel": "بازل", "Copenhagen": "كوبنهاغن", "Olympiacos": "أولمبياكوس", "Panathinaikos": "باناثينايكوس",
    "AEK Athens": "إيه إي كيه أثينا", "PAOK": "باوك", "Dinamo Zagreb": "دينامو زغرب", "Red Star": "النجم الأحمر",
    "Slavia Prague": "سلافيا براغ", "Sparta Prague": "سبارتا براغ", "Plzen": "فيكتوريا بلزن", 
    "Bodo Glimt": "بودو غليمت", "Qarabag": "قره باغ", "Kairat": "كايرات", "Pafos": "بافوس", 
    "Ferencvaros": "فيرينكفاروش", "Legia Warsaw": "ليغيا وارسو", "Celtic": "سيلتيك", "Rangers": "رينجرز",
    "Club Brugge": "كلوب بروج", "Anderlecht": "أندرلخت", "Genk": "جنك"
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
        # إذا لم يجد الفيديو، يضغط على منتصف الشاشة لتشغيل المشغل
        if not stream_url:
            await page.mouse.click(400, 300)
            await page.wait_for_timeout(4000)
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
            args=["--disable-webrtc", "--no-sandbox"]
        )
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await context.new_page()

        print("🌐 جاري تحميل الصفحة الرئيسية...")
        try:
            # ننتظر تحميل الشبكة بالكامل (networkidle) لضمان اكتمال الجافاسكربت
            await page.goto("https://koora7goal.com/", wait_until="networkidle", timeout=40000)
            # ننتظر 5 ثواني إضافية لضمان ظهور كل المباريات
            await page.wait_for_timeout(5000)
            
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
            print(f"❌ فشل تحميل الصفحة: {e}")
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
            
            norm_match_name = normalize_arabic(match_name_ar)

            for link in all_links:
                norm_link_text = normalize_arabic(link['text'])
                
                # المطابقة الضبابية
                score = fuzz.token_set_ratio(norm_match_name, norm_link_text)
                
                # إذا كانت النسبة عالية، أو إذا كان اسم الفريقين موجوداً حرفياً داخل النص
                if (score > 60 and score > best_score) or (normalize_arabic(t1_ar) in norm_link_text and normalize_arabic(t2_ar) in norm_link_text):
                    best_score = score if score > 60 else 100
                    target_url = link['href']

            if target_url:
                print(f"  -> تطابق {round(best_score)}%: {target_url}")
                stream_url = await extract_stream(page, target_url)
                if stream_url:
                    final_link = f"{PROXY_URL}/?u={quote(stream_url)}" if PROXY_URL else stream_url
                    links_to_update[str(m.get("id"))] = {"link": final_link, "mode": "embed"}
                    print(f"  ✅ تم التقاط الفيديو وتمريره للبروكسي!")
                else:
                    print(f"  ⚠️ الصفحة فتحت بس ما لقينا الفيديو.")
            else:
                print(f"  ⚠️ المباراة غير موجودة بالصفحة الرئيسية حالياً.")

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
