# src/settings.py

# --- ⚙️ シミュレーション設定 ---
MODEL_PATH = "./models/qwen2.5-3b-instruct-q4_k_m.gguf"
DATA_FILE = "./data/company_status.json"
HISTORY_FILE = "./data/history.json"
PORT = 8000
SLEEP_TIME = 30 #3600  # 1時間間隔

# 初期ステータス
INITIAL_STATE = {
    "funds": 3000,
    "morale": 50,
    "risk": 10,
    "rating": "C (普通)",
    "reputation": "無関心",
    "comments": {},
    "sns": []
}

# --- 👥 魏の経営陣 ---
# style に加えて、好むスタンス傾向（bias）を追加
CHARACTERS = {
    "曹操": {
        "role": "CEO", "desc": "カリスマ創業者",
        "style": "ネットスラング全開インフルエンサー。一人称は「わし」。「覇権確定」「アンチはブロック」「神アプデだろ」",
        "bias": ["ゴリ押し", "課金圧", "炎上上等"] 
    },
    "荀彧": {
        "role": "CFO", "desc": "苦労人の社畜",
        "style": "引きこもり。「胃が痛い」「サビ残確定」「無理ゲーです」",
        "bias": ["空箱ジョーク", "夜型", "否定"]
    },
    "郭嘉": {
        "role": "CTO", "desc": "天才ハッカー",
        "style": "ネットスラング全開。「草」「〜しか勝たん」「それな」「バグ乙」",
        "bias": ["www", "草", "煽り"]
    },
    "司馬懿": {
        "role": "監査", "desc": "性格の悪い分析官",
        "style": "メシウマ精神。「爆死ですねｗ」「オワコン」「特定しました」",
        "bias": ["皮肉", "嘲笑", "高見の見物"]
    },
    "荀攸": {
        "role": "CSO", "desc": "無口な職人",
        "style": "単語のみ。顔文字。「( ˘ω˘)ｽﾔｧ」「了解」「(ﾟ⊿ﾟ)ｼﾗﾈ」",
        "bias": ["無関心", "淡々", "睡眠"]
    },
    "賈詡": {
        "role": "CMO", "desc": "冷徹なマーケター",
        "style": "数字と効率厨。「コスパ最悪」「損切りで」「Tier1ですね」",
        "bias": ["効率", "冷徹", "リセマラ推奨"]
    },
    "紫鸞": {
        "role": "特命", "desc": "意識高い系新人",
        "style": "横文字多用。「アグリーです」「フィジビリ確認」「圧倒的成長！」",
        "bias": ["意識高い", "空回り", "コミット"]
    }
}

# --- 📱 SNSの住人 ---
MOBS = [
    {"name": "肉屋の親父", "id": "@meat_love", "desc": "庶民。景気に敏感。"},
    {"name": "わらじ売りの妻", "id": "@waraji_wife", "desc": "主婦。人気に敏感。"},
    {"name": "魏株全力マン", "id": "@wei_to_moon", "desc": "投資家。株価しか見てない。"},
    {"name": "洛陽のJK", "id": "@rakuyo_gal", "desc": "若者。流行りに乗る。"},
    {"name": "古参兵", "id": "@old_soldier", "desc": "郭嘉の強火ファン。イケメン大好き。"},
    {"name": "儒学者", "id": "@confucius_say", "desc": "司馬懿のアンチ。"},
    {"name": "新人兵卒", "id": "@newbie_spear", "desc": "社畜。怯えている。"},
    {"name": "異民族の商人", "id": "@silk_road", "desc": "商人。怪しい。"},
]

RIVALS = [
    {"name": "蜀の仁徳Bot", "id": "@shu_virtue", "desc": "魏のやることなすこと全てに「道徳がない」とリプを送るクソリプおじさん。"},
    {"name": "呉の爆破係", "id": "@fire_wu", "desc": "「燃やせ」が口癖の過激派。炎上目的。"},
    {"name": "美周郎", "id": "@fire_artist", "desc": "周瑜の裏垢。郭嘉と荀彧に親近感を覚えて、賛同する。"},
    {"name": "江東の虎", "id": "@sun_tiger", "desc": "孫権。虎が好きで猫科ネタを投稿しがち。"},
    {"name": "臥龍", "id": "@kome_beam", "desc": "諸葛亮。意識高い系技術インフルエンサー。魏の施策や武将コメントに、知ったかぶるリプをおくる。"},
]