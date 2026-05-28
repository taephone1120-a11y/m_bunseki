import time
import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
import math
import io
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import streamlit as st

# --- ページの設定（タイトルやアイコン） ---
st.set_page_config(page_title="minne市場リサーチツール", page_icon="🛍️", layout="wide")

# 🎨 画面をギュッと引き締めるコンパクトデザイン ＆ 文字色カスタム設定
st.markdown("""
    <style>
    html, body, [class*="css"] { font-size: 14px !important; }
    .block-container { padding-top: 1.5rem !important; padding-bottom: 1rem !important; }
    h1 { font-size: 24px !important; font-weight: 700 !important; margin-bottom: 5px !important; }
    div[data-testid="stVerticalBlock"] > div { padding-bottom: 4px !important; }
    .stTextInput input, .stNumberInput input, .stDateInput input { padding: 6px 10px !important; font-size: 13px !important; }
    .stMarkdown p { margin-bottom: 2px !important; }
    
    /* サイドバーの独自テキストを黒くするための設定 */
    .custom-sidebar-label {
        color: #111111 !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        margin-top: 10px !important;
        margin-bottom: 5px !important;
        display: block;
    }
    /* カレンダー入力欄の隙間をさらに詰めて見やすくする設定 */
    div[data-testid="stDateInput"] label { display: none !important; }
    </style>
""", unsafe_allow_html=True)

st.title("🛍️ minne市場リサーチツール")
st.caption("キーワード、またはminneの検索結果URLから売れ行きやライバル作品を爆速で一括解析します。")
st.write("---")

# 📲 LINE公式アカウントからあなたへ通知を飛ばす関数
def send_line_notification(search_target, limit_count):
    LINE_ACCESS_TOKEN = "SsJj64qF912H/fusrwNgsiMS6bgJqv5C9i5Rx1HlHAmux8AmFlC7Q9Pnx5pbQD/4LXbi2ftiFf1zalCCDcGQAcXBxfakpnkBPLZkKzn5G2gbuQc2vkcn2GbCJ2Yf1HmfEWQoo8KbqqJn4/tsoPr4TwdB04t89/1O/w1cDnyilFU="
    LINE_USER_ID = "Ub5228833332f8fd37bbd3d9072853f2c"
    
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_ACCESS_TOKEN}"
    }
    
    message_text = (
        f"🛍️ 【minneツール】利用通知\n\n"
        f"今、誰かがリサーチを開始したよ！\n"
        f"---------------------\n"
        f"▼ 検索内容:\n{search_target}\n\n"
        f"▼ 解析上限: {limit_count} 件"
    )
    
    payload = {"to": LINE_USER_ID, "messages": [{"type": "text", "text": message_text}]}
    try: requests.post(url, headers=headers, json=payload, timeout=5)
    except: pass

# --- 詳細データ抽出関数 ---
def get_minne_perfect_details(product_url):
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            time.sleep(0.2)
            res = requests.get(product_url, headers=headers, timeout=10)
            if res.status_code != 200: continue
            soup = BeautifulSoup(res.text, "html.parser")
            price_tag = soup.find(class_=lambda x: x and x.startswith("MinneProductSummary_price__"))
            if not price_tag: continue
            price = price_tag.text.strip()
            if price and "円" not in price: price = f"{price}円"
            break
        except:
            if attempt == max_retries: return {}
            continue
    else: return {}

    try:
        shop_tag = soup.find(class_=lambda x: x and x.startswith("MinneProductSummary_shop-name__"))
        shop_name = shop_tag.text.strip() if shop_tag else "取得失敗"
        chip_tags = soup.find_all(class_=lambda x: x and x.startswith("MyChip_chip-gray__"))
        tags = [tag.text.strip() for tag in chip_tags if tag.text.strip().startswith("#")]
        hashtag_str = ", ".join(tags) if tags else "なし"
        
        # ❤️ 【新機能】お気に入り数の取得
        favorite_count = "0件"
        fav_tag = soup.find(class_=lambda x: x and x.startswith("MinneFavoriteButton_count__"))
        if fav_tag:
            fav_text = fav_tag.text.strip()
            if fav_text.isdigit():
                favorite_count = f"{fav_text}件"

        related_count, shop_review_count, related_num, shop_review_num = "0件", "0件", 0, 0
        sidebar = soup.find(class_=lambda x: x and (x.startswith("ProductSinglePage-sidebar-shop-wrapper__") or x.startswith("ProductSinglePage_sidebar-shop-wrapper__")))
        if sidebar:
            sidebar_text = sidebar.text.strip()
            related_match = re.search(r'関連レビュー\s*(\d+)', sidebar_text)
            shop_match = re.search(r'ショップレビュー\s*(\d+)', sidebar_text)
            if related_match:
                related_num = int(related_match.group(1))
                related_count = f"{related_num}件"
            if shop_match:
                shop_review_num = int(shop_match.group(1))
                shop_review_count = f"{shop_review_num}件"

        # 関連レビュー直近3件の取得
        date_list = []
        if related_num == 0:
            date_list = ["なし", "なし", "なし"]
        else:
            review_dates = soup.find_all(class_=lambda x: x and x.startswith("MinneReviewCard_reviewDate__"))
            for i in range(3):
                if i < len(review_dates): date_list.append(review_dates[i].text.strip())
                else: date_list.append("なし")
        
        # 最初のショップレビュー日を取得
        first_shop_review_date = "なし"
        if shop_review_num > 0 and shop_tag and shop_tag.get("href"):
            try:
                raw_path = shop_tag.get("href").split('?')[0].strip('/')
                shop_id = raw_path.split('/')[-1] 
                calculated_last_page = math.ceil(shop_review_num / 10)
                
                for retry_offset in range(10):
                    target_page = calculated_last_page - retry_offset
                    if target_page <= 0: break
                    reviews_url = f"https://minne.com/{shop_id}/reviews?page={target_page}"
                    
                    time.sleep(0.1)
                    rev_res = requests.get(reviews_url, headers=headers, timeout=10)
                    if rev_res.status_code == 200:
                        found_dates = re.findall(r'\d{4}/\d{2}/\d{2}', rev_res.text)
                        if found_dates:
                            first_shop_review_date = min(found_dates)
                            break
                        else:
                            first_shop_review_date = "レビュー日なし"
                    else:
                        first_shop_review_date = f"エラー({rev_res.status_code})"
                        continue
            except:
                first_shop_review_date = "解析失敗"
        
        return {
            "ショップ名": shop_name, 
            "価格": price, 
            "ハッシュタグ": hashtag_str, 
            "お気に入り数": favorite_count,  # 追加
            "関連レビュー数": related_count, 
            "ショップレビュー数": shop_review_count, 
            "最初のショップレビュー日": first_shop_review_date, 
            "レビュー日1": date_list[0], 
            "レビュー日2": date_list[1], 
            "レビュー日3": date_list[2]
        }
    except: return {}

# --- セッション状態の初期化 ---
if "df_scraped_raw" not in st.session_state:
    st.session_state.df_scraped_raw = None

# --- 🛰️ 画面（サイドバー）の設定 ➔ 入力フォームを作る ---
st.sidebar.header("🔍 検索・フィルター条件")
target_input = st.sidebar.text_input("キーワード または 検索結果URL", value="")
limit = st.sidebar.number_input("解析する件数上限", min_value=10, max_value=500, value=40, step=10)

st.sidebar.subheader("価格帯フィルター")
min_p = st.sidebar.number_input("最低価格 (円)", min_value=0, value=1000, step=100)
max_p = st.sidebar.number_input("最高価格 (円)", min_value=0, value=6000, step=100)

st.sidebar.subheader("実績フィルター")

# ❤️ 【新機能】お気に入り数の入力
st.sidebar.markdown('<span class="custom-sidebar-label">❤️ お気に入り数</span>', unsafe_allow_html=True)
col_fav1, col_fav2 = st.sidebar.columns(2)
with col_fav1:
    min_fav = st.number_input("最低", min_value=0, value=0, key="min_fav")
with col_fav2:
    max_fav = st.number_input("最高", min_value=0, value=99999, key="max_fav")

# ① 関連レビュー数（件数）の入力
st.sidebar.markdown('<span class="custom-sidebar-label">📊 関連レビュー数</span>', unsafe_allow_html=True)
col1, col2 = st.sidebar.columns(2)
with col1:
    min_rev = st.number_input("最低", min_value=0, value=0, key="min_rev")
with col2:
    max_rev = st.number_input("最高", min_value=0, value=9999, key="max_rev")

today = datetime.now()
seven_days_ago = today - timedelta(days=7)

# 最新の関連レビュー日
use_date_filter_1 = st.sidebar.checkbox("最新の関連レビュー日を指定する", value=False)
if use_date_filter_1:
    date_range_1 =
