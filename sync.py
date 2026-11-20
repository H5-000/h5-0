import os
import re
import json
import asyncio
import requests
import subprocess
from urllib.parse import urljoin
from playwright.async_api import async_playwright
from rapidfuzz import fuzz

# محاولة استيراد stealth (اختياري)
try:
    from playwright_stealth import stealth_async
    HAS_STEALTH = True
except Exception:
    HAS_STEALTH = False

API_BASE = "https://workermatch-config.hs2224008.workers.dev"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

# 📚 القاموس الأساسي
TEAM_DICT = {
    "Man City": "مانشستر سيتي", "Arsenal": "أرسنال", "Liverpool": "ليفربول", "Chelsea": "تشيلسي",
    "Tottenham": "توتنهام", "Man United": "مانشستر يونايتد", "Newcastle": "نيوكاسل", "Aston Villa": "أستون فيلا",
    "Brighton": "برايتون", "West Ham": "وست هام", "Crystal Palace": "كريستال بالاس", "Brentford": "برينتفورد",
    "Fulham": "فولهام", "Everton": "إيفرتون", "Wolves": "وولفرهامبتون", "Bournemouth": "بورنموث",
    "Nottingham Forest": "نوتينغهام فورست", "Leicester": "ليستر سيتي", "Southampton": "ساوثهامبتون",
    "Leeds": "ليدز", "Leeds United": "ليدز يونايتد", "Sunderland": "سندرلاند", "Real Madrid": "ريال مدريد", "Barcelona": "برشلونة",
    "Atletico Madrid": "أتلتيكو مدريد", "Athletic Club": "أتلتيك بلباو", "Real Sociedad": "ريال سوسيداد",
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
    "Norwich": "نورويتش", "Watford": "واتفورد", "Rio Ave": "ريو أفي", "Famalicao": "فاماليكاو",
    "Al Ettifaq": "الاتفاق", "Al Taawoun": "التعاون", "Al Shabab": "الشباب", "Al Fateh": "الفتح", 
    "Damac": "ضمك", "Al Fayha": "الفيحاء", "Al Riyadh": "الرياض", "Al Khaleej": "الخليج", "Al Okhdood": "الأخدود", "Al Hazem": "الحزم", "Abha": "أبها"
}

# 🧠 ميزة التعلم الذاتي
LEARNED_FILE = "teams_learned.json"
if os.path.exists(LEARNED_FILE):
    with open(LEARNED_FILE, 'r', encoding='utf-8') as f:
        learned_teams = json.load(f)
        TEAM_DICT.update(learned_teams)

def save_learned_teams():
    with open(LEARNED_FILE, 'w', encoding='utf-8') as f:
        json.dump(TEAM_DICT, f, ensure_ascii=False, indent=2)
    try:
        subprocess.run(["git", "config", "user.name", "GitHub Action"])
        subprocess.run(["git", "config", "user.email", "action@github.com"])
        subprocess.run(["git", "add", LEARNED_FILE])
        subprocess.run(["git", "commit", "-m", "Auto-learn new teams [skip ci]"])
        subprocess.run(["git", "push"])
    except Exception:
        pass

def send_telegram(msg):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        try:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=5)
        except Exception:
            pass

def get_arabic_name(en_name):
    if not en_name: return ""
    if en_name in TEAM_DICT: return TEAM_DICT[en_name]
    best_score = 0
    best_match = en_name
    for en_key, ar_val in list(TEAM_DICT.items()):
        score = fuzz.token_set_ratio(en_name.lower(), en_key.lower())
        if score > 80 and score > best_score:
            best_score = score
            best_match = ar_val
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
        r = requests.get(f"{API_BASE}/fixtures", timeout=15)
        if r.ok: return r.json()
    except Exception as e:
        print(f"Error fetching fixtures: {e}")
    return []

AD_KEYWORDS = ["doubleclick", "googlesyndication", "adsystem", "googleads", "adservice", "analytics", "facebook.com/tr", "about:blank"]
PLAYER_KEYWORDS = ["embed", "player", "stream", "live", "iframe", "video", "play"]

async def extract_iframe(page, target_url):
    for attempt in range(3):
        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
            try:
                await page.wait_for_selector("iframe", timeout=12000)
            except Exception:
                pass
            await page.wait_for_timeout(1500)

            iframes = await page.query_selector_all("iframe")
            if not iframes:
                if attempt < 2:
                    await page.wait_for_timeout(2000)
                    continue
                return None

            fallback = None
            for iframe in iframes:
                src = await iframe.get_attribute("src")
                if not src: continue
                if src.startswith("//"): src = "https:" + src
                if not src.startswith("http"): continue

                low = src.lower()
                if any(x in low for x in AD_KEYWORDS): continue
                if any(k in low for k in PLAYER_KEYWORDS):
                    return src
                if fallback is None: fallback = src

            return fallback
        except Exception:
            if attempt == 2: return None
            await page.wait_for_timeout(2000)
    return None

async def process_match(browser_context, m, all_elements, semaphore):
    async with semaphore:
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
            if norm_t1 and norm_t2 and norm_t1 in norm_text and norm_t2 in norm_text:
                if el['href']:
                    target_url = el['href']
                    best_score = 100
                    break
            
            # تم تنزيل نسبة التشابه إلى 60% لالتقاط أسماء الفرق اللي تتشابه
            score = fuzz.token_set_ratio(norm_match_name, norm_text)
            if score > 60 and score > best_score and el['href']:
                best_score = score
                target_url = el['href']

        if target_url:
            print(f"  -> تطابق {round(best_score)}%: {target_url[:80]}")
            page = await browser_context.new_page()
            try:
                if HAS_STEALTH:
                    try: await stealth_async(page)
                    except Exception: pass
                iframe_url = await extract_iframe(page, target_url)
                if iframe_url:
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

    r = requests.get(f"{API_BASE}/auth", headers={"X-Admin-Password": ADMIN_PASSWORD}, timeout=15)
    if not r.ok:
        print("❌ كلمة المرور غير صحيحة")
        return
    token = r.json().get("token")

    fixtures = await get_matches()
    
    # 🔥 التعديل الأهم: جلب كل المباريات اللي مو منتهية (سواء live, soon, أو أي حالة ثانية)
    active_matches = [m for m in fixtures if m.get("status") not in ["done", "finished", "postponed"]]
    finished_matches = [m for m in fixtures if m.get("status") in ["done", "finished", "postponed"]]
    
    print(f"📊 إجمالي المباريات بالـ API: {len(fixtures)} | سيتم البحث عن: {len(active_matches)} مباراة")

    links_to_update = {}
    
    if active_matches:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True, 
                args=["--disable-webrtc", "--no-sandbox", "--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage"]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 800},
                locale="ar-EG"
            )
            page = await context.new_page()

            if HAS_STEALTH:
                try: await stealth_async(page)
                except Exception: pass

            print("🌐 جاري فتح صفحة المصدر (koora7goal)...")
            try:
                # فتح الصفحة الرئيسية
                await page.goto("https://koora7goal.com/", wait_until="domcontentloaded", timeout=60000)
                
                # انتظار ظهور أي عنصر يدل على مباراة
                try:
                    await page.wait_for_selector('a[href*="/match"], div.match-card, .match-item, [class*="match"], [class*="fixture"]', timeout=20000)
                except Exception:
                    pass
                
                await page.wait_for_timeout(3000)

                # استخراج البيانات بذكاء
                all_elements = await page.evaluate('''() => {
                    const results = [];
                    const nodes = document.querySelectorAll('a, button, div[onclick], div[data-href], div[data-url], div.match-card, .match-item, [class*="match"], [class*="fixture"]');
                    nodes.forEach(el => {
                        const text = (el.innerText || el.textContent || '').trim();
                        let href = el.href || el.getAttribute('data-href') || el.getAttribute('data-url') || null;
                        
                        if (!href) {
                            const onclick = el.getAttribute('onclick') || '';
                            const mm = onclick.match(/['"](https?:\\/\\/[^'"]+)['"]/);
                            if (mm) href = mm[1];
                        }
                        
                        if (!href) {
                            for (const attr of el.attributes || []) {
                                if (attr.name.startsWith('data-') && /^https?:\\/\\//.test(attr.value)) {
                                    href = attr.value;
                                    break;
                                }
                            }
                        }
                        if (text.length > 3) results.push({ text, href });
                    });
                    return results;
                }''')

                print(f"✅ تم سحب {len(all_elements)} عنصر من الموقع.")
                
                # طباعة 5 عينات للتأكد من أن السحب يعمل
                for i, el in enumerate(all_elements[:5]):
                    print(f"   [عينة {i+1}] {el['text'][:30]} | {str(el['href'])[:50]}")

            except Exception as e:
                print(f"❌ فشل تحميل الموقع: {e}")
                send_telegram(f"⚠️ فشل تحميل موقع koora: {e}")
                await browser.close()
                return

            # بدء المعالجة المتوازية
            semaphore = asyncio.Semaphore(6) # زيادة عدد العمليات المتزامنة لتسريع البوت
            tasks = [process_match(context, m, all_elements, semaphore) for m in active_matches]
            results = await asyncio.gather(*tasks)

            for res in results:
                if res:
                    links_to_update[res[0]] = {"link": res[1], "mode": "embed"}

            await browser.close()

    # تحديث البيانات في موقعك
    if links_to_update or finished_matches:
        print(f"📤 جاري تحديث بيانات الموقع...")
        cfg_res = requests.get(f"{API_BASE}/config", timeout=15)
        cfg = cfg_res.json()
        current_links = cfg.get("links", {})

        added_count = len(links_to_update)
        if added_count > 0:
            current_links.update(links_to_update)
            print(f"   ✅ تم إضافة/تحديث {added_count} رابط بنجاح.")

        deleted_count = 0
        for m in finished_matches:
            m_id = str(m.get("id"))
            if m_id in current_links:
                del current_links[m_id]
                deleted_count += 1
        
        if deleted_count > 0:
            print(f"   🗑️ تم حذف {deleted_count} رابط لمباريات منتهية.")

        cfg["links"] = current_links
        requests.post(f"{API_BASE}/config", json=cfg, headers={"Authorization": f"Bearer {token}"}, timeout=15)
        print("🎉 تم التحديث بنجاح!")

        save_learned_teams()

        msg = f"✅ *تحديث ملعب لايف*\n\n"
        msg += f"➕ روابط تم جلبها: {added_count}\n"
        msg += f"🗑️ مباريات منتهية تم مسحها: {deleted_count}\n"
        msg += f"📊 إجمالي الروابط بموقعك: {len(current_links)}"
        send_telegram(msg)
    else:
        print("⚠️ لا توجد تحديثات جديدة.")

if __name__ == "__main__":
    asyncio.run(main())
