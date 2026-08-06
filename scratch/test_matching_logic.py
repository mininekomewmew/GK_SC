import sys
sys.stdout.reconfigure(encoding='utf-8')
import re

def is_team_match(query: str, team_name: str) -> bool:
    q = query.lower().strip()
    t = team_name.lower().strip()
    
    # Helper to clean strings for comparison (remove spaces, dots, dashes, parentheses)
    def clean_for_match(s: str) -> str:
        return re.sub(r"[\s\.\-\(\)]", "", s)
        
    q_clean = clean_for_match(q)
    t_clean = clean_for_match(t)
    
    # 1. Direct substring check (original and cleaned)
    if q_clean in t_clean or t_clean in q_clean:
        return True
        
    # 2. Specific alias mappings (English/Thai/Nicknames -> target substrings)
    aliases = {
        "แมนยู": ["แมนเชสเตอร์ ยูไนเต็ด", "แมนฯ ยูไนเต็ด", "แมนยู", "manchester united", "man united"],
        "แมนฯ ยู": ["แมนเชสเตอร์ ยูไนเต็ด", "แมนฯ ยูไนเต็ด", "แมนยู", "manchester united", "man united"],
        "แมนฯยู": ["แมนเชสเตอร์ ยูไนเต็ด", "แมนฯ ยูไนเต็ด", "แมนยู", "manchester united", "man united"],
        "man u": ["แมนเชสเตอร์ ยูไนเต็ด", "แมนฯ ยูไนเต็ด", "แมนยู", "manchester united", "man united"],
        "man utd": ["แมนเชสเตอร์ ยูไนเต็ด", "แมนฯ ยูไนเต็ด", "แมนยู", "manchester united", "man united"],
        "man united": ["แมนเชสเตอร์ ยูไนเต็ด", "แมนฯ ยูไนเต็ด", "แมนยู", "manchester united", "man united"],
        "manchester united": ["แมนเชสเตอร์ ยูไนเต็ด", "แมนฯ ยูไนเต็ด", "แมนยู", "manchester united", "man united"],
        
        "แมนซิตี้": ["แมนเชสเตอร์ ซิตี้", "แมนฯ ซิตี้", "แมนซิตี้", "manchester city", "man city"],
        "แมนฯ ซิตี้": ["แมนเชสเตอร์ ซิตี้", "แมนฯ ซิตี้", "แมนซิตี้", "manchester city", "man city"],
        "แมนฯซิตี้": ["แมนเชสเตอร์ ซิตี้", "แมนฯ ซิตี้", "แมนซิตี้", "manchester city", "man city"],
        "man city": ["แมนเชสเตอร์ ซิตี้", "แมนฯ ซิตี้", "แมนซิตี้", "manchester city", "man city"],
        "mancity": ["แมนเชสเตอร์ ซิตี้", "แมนฯ ซิตี้", "แมนซิตี้", "manchester city", "man city"],
        "manchester city": ["แมนเชสเตอร์ ซิตี้", "แมนฯ ซิตี้", "แมนซิตี้", "manchester city", "man city"],
        
        "หงส์แดง": ["ลิเวอร์พูล", "liverpool"],
        "liverpool": ["ลิเวอร์พูล", "liverpool"],
        
        "สิงห์บลู": ["เชลซี", "chelsea"],
        "สิงโตน้ำเงินคราม": ["เชลซี", "chelsea"],
        "chelsea": ["เชลซี", "chelsea"],
        
        "ปืนใหญ่": ["อาร์เซน่อล", "อาร์เซนอล", "arsenal"],
        "arsenal": ["อาร์เซน่อล", "อาร์เซนอล", "arsenal"],
        
        "ไก่เดือยทอง": ["ท็อตแน่ม ฮ็อทสเปอร์", "สเปอร์ส", "สเปอร์", "tottenham"],
        "สเปอร์": ["ท็อตแน่ม ฮ็อทสเปอร์", "สเปอร์ส", "สเปอร์", "tottenham"],
        "สเปอร์ส": ["ท็อตแน่ม ฮ็อทสเปอร์", "สเปอร์ส", "สเปอร์", "tottenham"],
        "tottenham": ["ท็อตแน่ม ฮ็อทสเปอร์", "สเปอร์ส", "สเปอร์", "tottenham"],
        
        "สาลิกาดง": ["นิวคาสเซิ่ล", "นิวคาสเซิล", "newcastle"],
        "newcastle": ["นิวคาสเซิ่ล", "นิวคาสเซิล", "newcastle"],
        
        "บาร์ซ่า": ["บาร์เซโลน่า", "barcelona"],
        "เจ้าบุญทุ่ม": ["บาร์เซโลน่า", "barcelona"],
        "barcelona": ["บาร์เซโลน่า", "barcelona"],
        
        "มาดริด": ["เรอัล มาดริด", "real madrid"],
        "ราชันชุดขาว": ["เรอัล มาดริด", "real madrid"],
        "real madrid": ["เรอัล มาดริด", "real madrid"],
        
        "แอต มาดริด": ["แอตเลติโก มาดริด", "atletico madrid"],
        "แอตฯ มาดริด": ["แอตเลติโก มาดริด", "atletico madrid"],
        "atletico": ["แอตเลติโก มาดริด", "atletico madrid"],
        
        "เสือใต้": ["บาเยิร์น มิวนิค", "บาเยิร์น", "bayern"],
        "bayern": ["บาเยิร์น มิวนิค", "บาเยิร์น", "bayern"],
        
        "เสือเหลือง": ["โบรุสเซีย ดอร์ทมุนด์", "ดอร์ทมุนด์", "dortmund"],
        "dortmund": ["โบรุสเซีย ดอร์ทมุนด์", "ดอร์ทมุนด์", "dortmund"],
        
        "เปแอสเช": ["ปารีส แซงต์ แชร์กแมง", "ปารีส แซงต์-แชร์กแมง", "psg"],
        "psg": ["ปารีส แซงต์ แชร์กแมง", "ปารีส แซงต์-แชร์กแมง", "psg"],
        
        "งูใหญ่": ["อินเตอร์ มิลาน", "inter"],
        "inter": ["อินเตอร์ มิลาน", "inter"],
        
        "ปีศาจแดงดำ": ["เอซี มิลาน", "milan"],
        "ac milan": ["เอซี มิลาน", "milan"],
        
        "ม้าลาย": ["ยูเวนตุส", "juventus"],
        "juventus": ["ยูเวนตุส", "juventus"],
        
        "โรม่า": ["เอเอส โรม่า", "โรม่า", "roma"],
        "roma": ["เอเอส โรม่า", "โรม่า", "roma"],
        
        "บีจี": ["บีจี ปทุม ยูไนเต็ด", "บีจี ปทุม", "bg pathum", "bg"],
        "bg": ["บีจี ปทุม ยูไนเต็ด", "บีจี ปทุม", "bg pathum", "bg"],
        "bg pathum": ["บีจี ปทุม ยูไนเต็ด", "บีจี ปทุม", "bg pathum", "bg"],
        
        "ท่าเรือ": ["การท่าเรือ เอฟซี", "การท่าเรือ", "port fc", "port"],
        "port fc": ["การท่าเรือ เอฟซี", "การท่าเรือ", "port fc", "port"],
        
        "บุรีรัมย์": ["บุรีรัมย์ ยูไนเต็ด", "บุรีรัมย์", "buriram"],
        "buriram": ["บุรีรัมย์ ยูไนเต็ด", "บุรีรัมย์", "buriram"],
        
        "เมืองทอง": ["เมืองทอง ยูไนเต็ด", "กิเลนผยอง", "muangthong"],
        "muangthong": ["เมืองทอง ยูไนเต็ด", "กิเลนผยอง", "muangthong"],
    }
    
    # Check if cleaned query is in aliases
    for key, targets in aliases.items():
        if clean_for_match(key) == q_clean:
            for target in targets:
                if clean_for_match(target) in t_clean:
                    return True
                    
    return False

# Run test cases
test_cases = [
    ("แมนยู", "แมนเชสเตอร์ ยูไนเต็ด"),
    ("แมนฯ ยู", "แมนเชสเตอร์ ยูไนเต็ด"),
    ("แมนฯยู", "แมนเชสเตอร์ ยูไนเต็ด"),
    ("แมนซิตี้", "แมนเชสเตอร์ ซิตี้"),
    ("บีจี", "บีจี ปทุม ยูไนเต็ด"),
    ("มาดริด", "เรอัล มาดริด"),
    ("เสือใต้", "บาเยิร์น มิวนิค"),
    ("ท่าเรือ", "การท่าเรือ เอฟซี"),
    ("จาเกียลโลเนีย", "จาเกียลโลเนีย เบียลีสต็อก"),
    ("Real Madrid", "เรอัล มาดริด"),
    ("man united", "แมนเชสเตอร์ ยูไนเต็ด"),
]

for q, t in test_cases:
    res = is_team_match(q, t)
    print(f"Query: '{q}' | Team: '{t}' | Match: {res}")
