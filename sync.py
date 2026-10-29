import os
import re
import json
import asyncio
import requests
import subprocess
from urllib.parse import urljoin
from playwright.async_api import async_playwright
from rapidfuzz import fuzz
from bs4 import BeautifulSoup

API_BASE = "https://workermatch-config.hs2224008.workers.dev"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

# 📚 القاموس الأساسي (اللي أنت عطيتني إياه)
TEAM_DICT = {
    "Man City": "مانشستر سيتي", "Arsenal": "أرسنال", "Liverpool": "ليفربول", "Chelsea": "تشيلسي",
    "Tottenham": "توتنهام", "Man United": "مانشستر يونايتد", "Newcastle": "نيوكاسل", "Aston Villa": "أستون فيلا",
    "Brighton": "برايتون", "West Ham": "وست هام", "Crystal Palace": "كريستال بالاس", "Brentford": "برينتفورد",
    "Fulham": "فولهام", "Everton": "إيفرتون", "Wolves": "وولفرهامبتون", "Bournemouth": "بورنموث",
    "Nottingham Forest": "نوتينغهام فورست", "Leicester": "ليستر سيتي", "Southampton": "ساوثهامبتون",
    "Leeds": "ليدز", "Leeds United": "ليدز يونايتد", "Sunderland": "سندرلاند", "Real Madrid": "ريال مدريد", "Barcelona": "برشلونة",
    "Atletico Madrid": "أتلتيكو مدريد", "Athletic Club": "أتلتيك بيلباو", "Real Sociedad": "ريال سوسيداد",
    "Real Betis": "ريال بيتيس", "Villarreal": "فياريال", "Valencia": "فالنسيا", "Sevilla": "إشبيلية",
    "Girona": "جيرونا", "Celta Vigo": "سيلتا فيغو", "Osasuna": "أوساسونا", "Mallorca": "مايوركا",
    "Rayo Vallecano": "رايو فاييكانو", "Getafe": "خيتافي", "Espanyol": "إسبانيول", "Inter": "إنتر",
    "AC Milan": "ميلان", "Juventus": "يوفنتوس", "Napoli": "نابولي", "Roma": "روما", "Lazio": "لاتسيو",
    "Atalanta": "أتالانتا", "Fiorentina": "فيورنتينا", "Bologna": "بولونيا", "Torino": "تورينو",
    "Udinese": "أودينيزي", "Genoa": "جنوى", "Cagliari": "كالياري", "Lecce": "ليتشي", "Monza": "مونزا",
    "Venezia": "فينيسيا", "Bayern": "بايرن ميونخ", "Bayern Munich": "بايرن ميونخ", "Borussia Dortmund": "دورتموند", "Dortmund": "دورتموند", "RB Leipzig": "لايبزيغ", "Leipzig": "لايبزيغ",
    "Bayer Leverkusen": "ليفركوزن", "Leverkusen": "ليفركوزن", "Eintracht Frankfurt": "آينتراخت فرانكفورت", "Stuttgart": "شتوتغارت",
    "Freiburg": "فرايبورغ", "Wolfsburg": "فولفسبورغ", "Gladbach": "مونشنغلادباخ", "Hoffenheim": "هوفنهايم",
    "Mainz": "ماينز", "Augsburg": "أوغسبورغ", "Werder Bremen": "فيردر بريمن", "Union Berlin": "يونيون برلين",
    "PSG": "باريس سان جيرمان", "Marseille": "مارسيليا", "Lyon": "ليون", "Monaco": "موناكو", "Lille": "ليل",
    "Nice": "نيس", "Rennes": "رين", "Stade Rennais": "رين", "Lens": "لانس", "Reims": "ريمس", "Strasbourg": "ستراسبورغ",
    "Nantes": "نانت", "Toulouse": "تولوز", "Montpellier": "مونبلييه", "Brest": "بريست", "Lorient": "لوريان",
    "Angers": "أنجيه", "Angers SCO": "أنجيه", "Troyes": "تروا", "Le Mans": "لو مان", "Auxerre": "أوكسير", "Le Havre": "لوهافر",
    "Ajax": "أياكس", "PSV": "آيندهوفن", "Feyenoord": "فاينورد", "Benfica": "بنفيكا", "Porto": "بورتو",
    "Sporting CP": "سبورتينغ لشبونة", "Braga": "براغا", "Galatasaray": "غلطة سراي", "Fenerbahce": "فنربخشة",
    "Besiktas": "بشكتاش", "Al Hilal": "الهلال", "Al Nassr": "النصر", "Al Ittihad": "الاتحاد", "Al Ahli": "الأهلي",
    "Al Shorta": "الشرطة", "Al Quwa Al Jawiya": "القوة الجوية", "Al Zawraa": "الزوراء", "Al Talaba": "الطلبة",
    "Al Najaf": "النجف", "Al Ahly": "الأهلي", "Zamalek": "الزمالك", "Pyramids": "بيراميدز", "Wydad": "الوداد",
    "Raja Casablanca": "الرجاء", "Esperance": "الترجي", "TP Mazembe": "تي بي مازيمبي", "Flamengo": "فلامنغو",
    "Palmeiras": "بالميراس", "Corinthians": "كورنثيانز", "Sao Paulo": "ساو باولو", "Santos": "سانتوس",
    "Fluminense": "فلوميننسي", "Bahia": "باهيا", "Chapecoense": "شابيكوينسي", "Nacional": "ناسيونال", "CD Nacional": "ناسيونال", "Sparta": "سبارتا", "Sparta Rotterdam": "سبارتا روتردام",
    "AZ Alkmaar": "ألكمار", "Parma": "بارما", "Casa Pia": "كاسا بيا", "Stoke": "ستوك سيتي", 
    "Preston": "بريستون", "Lincoln City": "لينكولن", "Birmingham": "برمنغهام", "Elversberg": "إلفرسبيرغ", 
    "Norwich": "نورويتش", "Watford": "واتفورد", "Rio Ave": "ريو أفي", "Famalicao": "فاماليكاو"
}

# 🧠 ميزة التعلم الذاتي: تحميل الأسماء المكتسبة سابقاً
LEARNED_FILE = "teams_learned.json"
if os.path.exists(LEARNED_FILE):
    with open(LEARNED_FILE, 'r', encoding='utf-8') as f:
        learned_teams = json.load(f)
        TEAM_DICT.update(learned_teams)

def save_learned_teams():
    with open(LEARNED_FILE, 'w', encoding='utf-8') as f:
        json.dump(TEAM_DICT, f, ensure_ascii=False, indent=2)
    # رفع الملف إلى GitHub عشان الذاكرة تبقى محفوظة
    try:
        subprocess.run(["git", "config", "user.name", "GitHub Action"])
        subprocess.run(["git", "config", "user.email", "action@github.com"])
        subprocess.run(["git", "add", LEARNED_FILE])
        subprocess.run(["git", "commit", "-m", "Auto-learn new teams [skip ci]"])
        subprocess.run(["git", "push"])
    except:
        pass

# 📱 ميزة إشعارات تلغرام
def send_telegram(msg):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        try:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": msg}, timeout=5)
        except:
            pass

def get_arabic_name(en_name):
    if not en_name: return ""
    if en_name in TEAM_DICT: return TEAM_DICT[en_name]
    best_score = 0
    best_match = en_name
    for en_key, ar_val in TEAM_DICT.items():
        score = fuzz.token_set_ratio(en_name.lower(), en_key.lower())
        if score > 80 and score > best_score:
            best_score = score
            best_match = ar_val
            # 🧠 إذا لقى تطابق عالي، نحفظ الاسم الجديد في الذاكرة
            if score > 90 and en_name not in TEAM_DICT:
                TEAM_DICT[en_name] = ar_val
    return best_match

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

# 🛡️ ميزة إعادة المحاولة (Retry) وفحص الرابط (Dead Link Checker)
async def extract_iframe(page, target_url):
    # التحقق من أن الرابط ليس ميتاً
    try:
        head_req = requests.head(target_url, timeout=5, allow_redirects=True)
        if head_req.status_code not in [200, 206, 301, 302, 403]:
            return None
    except:
        pass # بعض المواقع ترفض طلبات HEAD، فنتجاهل ونكمل

    # محاولة فتح الصفحة 3 مرات
    for attempt in range(3):
        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)
            
            iframe = await page.query_selector("iframe")
            if iframe:
                src = await iframe.get_attribute("src")
                if src:
                    if src.startswith("//"): src = "https:" + src
                    # فحص إذا كان الرابط يبدأ بـ http (ليس رابط فارغ)
                    if src.startswith("http"):
                        return src
            return None
        except Exception as e:
            if attempt == 2:
                print(f"  ❌ فشل بعد 3 محاولات: {e}")
                return None
            await page.wait_for_timeout(2000)
    return None

# ⚡ ميزة السرعة: دالة لمعالجة المباراة بشكل متوازي
async def process_match(browser_context, m, all_elements, semaphore):
    async with semaphore: # نسمح فقط بـ 5 عمليات متزامنة
        t1_en = m.get("home", {}).get("name", "")
        t2_en = m.get("away", {}).get("name", "")
        if not t1_en or not t2_en: return None

        t1_ar = get_arabic_name(t1_en)
        t2_ar = get_arabic_name(t2_en)
        match_name_ar = f"{t1_ar} {t2_ar}"
        
        print(f"🔍 البحث عن: {t1_ar} ضد {t2_ar}")

        target_url = None
        best_score = 0
        norm_t1 = normalize_arabic(t1_ar)
        norm_t2 = normalize_arabic(t2_ar)
        norm_match_name = normalize_arabic(match_name_ar)

        for el in all_elements:
            norm_text = normalize_arabic(el['text'])
            if norm_t1 in norm_text and norm_t2 in norm_text:
                if el['href']:
                    target_url = el['href']
                    best_score = 100
                    break
            score = fuzz.token_set_ratio(norm_match_name, norm_text)
            if score > 70 and score > best_score and el['href']:
                best_score = score
                target_url = el['href']

        if target_url:
            print(f"  -> تطابق {round(best_score)}%: {target_url}")
            page = await browser_context.new_page()
            try:
                iframe_url = await extract_iframe(page, target_url)
                if iframe_url:
                    print(f"  ✅ تم التقاط المشغل!")
                    return (str(m.get("id")), iframe_url)
            finally:
                await page.close()
        else:
            print(f"  ⚠️ المباراة غير موجودة بالصفحة.")
        return None

async def main():
    if not ADMIN_PASSWORD:
        print("❌ خطأ: لم يتم وضع كلمة المرور")
        return

    r = requests.get(f"{API_BASE}/auth", headers={"X-Admin-Password": ADMIN_PASSWORD})
    if not r.ok:
        print("❌ كلمة المرور غير صحيحة")
        send_telegram("❌ فشل البوت: كلمة المرور غير صحيحة")
        return
    token = r.json().get("token")

    fixtures = await get_matches()
    
    active_matches = [m for m in fixtures if m.get("status") in ["live", "soon"]]
    finished_matches = [m for m in fixtures if m.get("status") in ["done", "finished", "postponed"]]
    
    print(f"📊 إجمالي المباريات: {len(fixtures)} | النشطة: {len(active_matches)} | المنتهية: {len(finished_matches)}")

    links_to_update = {}
    
    if active_matches:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--disable-webrtc", "--no-sandbox"])
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            page = await context.new_page()

            print("🌐 جاري فتح الصفحة الرئيسية...")
            try:
                await page.goto("https://koora7goal.com/", wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(4000)
                
                all_elements = await page.evaluate('''() => {
                    let results = [];
                    document.querySelectorAll('a, button, div[onclick], div.match-card, .match-item').forEach(el => {
                        let text = el.innerText || el.textContent;
                        let href = el.href || null;
                        if (text && text.trim().length > 3) {
                            results.push({ text: text.trim(), href: href });
                        }
                    });
                    return results;
                }''')
                print(f"✅ تم سحب {len(all_elements)} عنصر. بدء المعالجة المتوازية...")
            except Exception as e:
                print(f"❌ فشل تحميل الموقع: {e}")
                send_telegram(f"⚠️ فشل تحميل موقع koora: {e}")
                await browser.close()
                return

            # ⚡ تشغيل المعالجة المتوازية (5 مباريات بنفس الوقت)
            semaphore = asyncio.Semaphore(5)
            tasks = [process_match(context, m, all_elements, semaphore) for m in active_matches]
            results = await asyncio.gather(*tasks)

            for res in results:
                if res:
                    links_to_update[res[0]] = {"link": res[1], "mode": "embed"}

            await browser.close()

    # تحديث الموقع وحذف الروابط القديمة
    if links_to_update or finished_matches:
        print(f"📤 جاري تحديث بيانات الموقع...")
        cfg_res = requests.get(f"{API_BASE}/config")
        cfg = cfg_res.json()
        current_links = cfg.get("links", {})

        added_count = len(links_to_update)
        if added_count > 0:
            current_links.update(links_to_update)
            print(f"   ✅ تم إضافة {added_count} رابط.")

        deleted_count = 0
        for m in finished_matches:
            m_id = str(m.get("id"))
            if m_id in current_links:
                del current_links[m_id]
                deleted_count += 1
        
        if deleted_count > 0:
            print(f"   🗑️ تم حذف {deleted_count} رابط لمباريات منتهية.")

        cfg["links"] = current_links
        requests.post(f"{API_BASE}/config", json=cfg, headers={"Authorization": f"Bearer {token}"})
        print("🎉 تم التحديث بنجاح!")

        # حفظ الأسماء الجديدة ورفعها لـ GitHub
        save_learned_teams()

        # إرسال تقرير تلغرام
        msg = f"✅ *تحديث ملعب لايف*\n\n"
        msg += f"➕ مباريات تم جلب بثها: {added_count}\n"
        msg += f"🗑️ مباريات منتهية تم مسح بثها: {deleted_count}\n"
        msg += f"📊 إجمالي الروابط النشطة: {len(current_links)}"
        send_telegram(msg)
    else:
        print("⚠️ لا توجد تحديثات جديدة.")

if __name__ == "__main__":
    asyncio.run(main())
