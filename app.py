import time
import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import streamlit as st

# --- ページの設定（タイトルやアイコン） ---
st.set_page_config(page_title="minne市場リサーチツール", page_icon="🛍️", layout="wide")

st.title("🛍️ minne市場リサーチツール")
st.write("キーワード、またはminneの検索結果URLを入力するだけで、売れ行きやライバル作品を爆速で一括解析します。")

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
        
        related_count, shop_review_count, related_num = "0件", "0件", 0
        sidebar = soup.find(class_=lambda x: x and (x.startswith("ProductSinglePage-sidebar-shop-wrapper__") or x.startswith("ProductSinglePage_sidebar-shop-wrapper__")))
        if sidebar:
            sidebar_text = sidebar.text.strip()
            related_match = re.search(r'関連レビュー\s*(\d+)', sidebar_text)
            shop_match = re.search(r'ショップレビュー\s*(\d+)', sidebar_text)
            if related_match:
                related_num = int(related_match.group(1))
                related_count = f"{related_num}件"
            if shop_match:
                shop_review_count = f"{shop_match.group(1)}件"

        date_list = []
        if related_num == 0:
            date_list = ["なし", "なし", "なし"]
        else:
            review_dates = soup.find_all(class_=lambda x: x and x.startswith("MinneReviewCard_reviewDate__"))
            for i in range(3):
                if i < len(review_dates): date_list.append(review_dates[i].text.strip())
                else: date_list.append("なし")
        
        return {"ショップ名": shop_name, "価格": price, "ハッシュタグ": hashtag_str, "関連レビュー数": related_count, "ショップレビュー数": shop_review_count, "レビュー日1": date_list[0], "レビュー日2": date_list[1], "レビュー日3": date_list[2]}
    except: return {}

# --- 🛰️ 画面（サイドバー）の設定 ➔ 入力フォームを作る ---
st.sidebar.header("🔍 検索・フィルター条件")
target_input = st.sidebar.text_input("キーワード または 検索結果URL", value="天然石 リング アメジスト")
limit = st.sidebar.number_input("解析する件数上限", min_value=10, max_value=200, value=40, step=10)

st.sidebar.subheader("価格帯フィルター")
min_p = st.sidebar.number_input("最低価格 (円)", min_value=0, value=1000, step=100)
max_p = st.sidebar.number_input("最高価格 (円)", min_value=0, value=6000, step=100)

st.sidebar.subheader("実績フィルター")
col1, col2 = st.sidebar.columns(2)
with col1:
    min_rev = st.number_input("作品レビュー最低", min_value=0, value=0)
with col2:
    max_rev = st.number_input("作品レビュー最高", min_value=0, value=9999)

col3, col4 = st.sidebar.columns(2)
with col3:
    min_shop_rev = st.number_input("ショップレビュー最低", min_value=0, value=0)
with col4:
    max_shop_rev = st.number_input("ショップレビュー最高", min_value=0, value=99999)

st.sidebar.subheader("日付フィルター")
# 💡 日付設定を有効にするかどうかのチェックボックス
use_date_filter = st.sidebar.checkbox("対象とする関連レビューの日付を指定する", value=False)

if use_date_filter:
    today = datetime.now()
    seven_days_ago = today - timedelta(days=7)
    date_range = st.sidebar.date_input(
        "対象とする関連レビューの日付（開始日 〜 終了日）",
        value=(seven_days_ago, today),
        max_value=today
    )
else:
    date_range = None

# --- 🚀 実行ボタン ---
if st.sidebar.button("リサーチを開始する", type="primary"):
    # 日付指定ありの場合のチェック
    if use_date_filter:
        if date_range and len(date_range) == 2:
            start_date, end_date = date_range
            start_dt = datetime.combine(start_date, datetime.min.time())
            end_dt = datetime.combine(end_date, datetime.max.time())
        else:
            st.error("❌ 期間は「開始日」と「終了日」の両方を選択してください。")
            st.stop()

    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    if target_input.startswith("http://") or target_input.startswith("https://"):
        st.info("🔗 URLモードで実行中...")
        base_url = target_input
    else:
        st.info(f"🔍 キーワードモード（{target_input}）で実行中...")
        encoded_keyword = urllib.parse.quote(target_input)
        base_url = f"https://minne.com/category/saleonly?input_method=typing&q={encoded_keyword}&commit=%E6%A4%9C%E7%B4%A2&search_type=normal"
    
    product_urls_with_titles = []
    page = 1
    seen_urls = set()
    
    status_text = st.empty()
    
    # URL集め
    while len(product_urls_with_titles) < limit:
        search_url = f"{base_url}&page={page}" if "?" in base_url else f"{base_url}?page={page}"
        status_text.text(f"📄 minneの {page} ページ目を読み込み中... (現在 {len(product_urls_with_titles)} 件の候補)")
        
        try:
            response = requests.get(search_url, headers=headers)
            if response.status_code != 200: break
            soup = BeautifulSoup(response.text, "html.parser")
            products = soup.find_all("a", class_=lambda x: x and (x.startswith("MinneProductCard_grid__") or x.startswith("ProductGrid_item__") or "product-card" in x.lower()))
            if not products: products = soup.find_all('a', href=re.compile(r'/items/\d+'))
            if not products: break
            
            page_added = 0
            for product in products:
                href = product.get("href")
                if not href: continue
                p_url = "https://minne.com" + href.split('?')[0] if href.startswith("/items/") else (href.split('?')[0] if "minne.com/items/" in href else None)
                if p_url and p_url not in seen_urls:
                    seen_urls.add(p_url)
                    title_tag = product.find(class_=lambda x: x and "title" in x.lower())
                    title = title_tag.text.strip() if title_tag else "商品名（個別解析で取得）"
                    product_urls_with_titles.append((title, p_url))
                    page_added += 1
            if page_added == 0: break
            page += 1
            time.sleep(0.3)
        except:
            break

    total_to_scrape = min(limit, len(product_urls_with_titles))
    
    if total_to_scrape == 0:
        st.error("❌ 条件に合う商品が1件も取得できませんでした。")
    else:
        status_text.text(f"📦 候補 {total_to_scrape} 件の詳細データを並行解析中...（しばらくお待ちください）")
        
        progress_bar = st.progress(0)
        raw_results = [None] * total_to_scrape
        completed_count = 0
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_info = {executor.submit(get_minne_perfect_details, url): (idx, title, url) for idx, (title, url) in enumerate(product_urls_with_titles[:total_to_scrape])}
            for future in as_completed(future_to_info):
                idx, title, url = future_to_info[future]
                try: details = future.result()
                except: details = {}
                
                display_title = "作品（詳細はURLへ）" if title == "商品名（個別解析で取得）" and "ショップ名" in details else title
                raw_results[idx] = {
                    "ショップ名": details.get("ショップ名", "取得失敗"), "商品名": display_title, "価格": details.get("価格", "価格なし"),
                    "URL": url, "関連レビュー数": details.get("関連レビュー数", "0件"),
                    "関連レビュー日1": details.get("レビュー日1", "なし"), "関連レビュー日2": details.get("レビュー日2", "なし"), "関連レビュー日3": details.get("レビュー日3", "なし"),
                    "ショップレビュー数": details.get("ショップレビュー数", "0件"), "ハッシュタグ": details.get("ハッシュタグ", "なし")
                }
                completed_count += 1
                progress_bar.progress(completed_count / total_to_scrape)
        
        status_text.empty()
        progress_bar.empty()
        
        # データクレンジング
        df_raw = pd.DataFrame(raw_results)
        df_filter = df_raw.copy()
        df_filter['価格_数値'] = pd.to_numeric(df_filter['価格'].str.replace('円', '').str.replace(',', '').str.strip(), errors='coerce').fillna(0).astype(int)
        df_filter['関連レビュー_数値'] = pd.to_numeric(df_filter['関連レビュー数'].str.replace('件', '').str.strip(), errors='coerce').fillna(0).astype(int)
        df_filter['ショップレビュー_数値'] = pd.to_numeric(df_filter['ショップレビュー数'].str.replace('件', '').str.strip(), errors='coerce').fillna(0).astype(int)
        
        def clean_japanese_date(date_str):
            if not date_str or pd.isna(date_str) or date_str in ['なし', 'レビューなし']: return pd.NaT
            try: return pd.to_datetime(date_str.replace('年', '/').replace('月', '/').replace('日', '').strip(), format='%Y/%m/%d')
            except: return pd.NaT
            
        df_filter['関連レビュー日1_日付'] = df_filter['関連レビュー日1'].apply(clean_japanese_date)
        
        # 💡【フィルター条件のロジック変更】
        if use_date_filter:
            # 日付指定ありの場合：指定期間内、かつレビュー数が1件以上のもの（0件は自動除外）
            df_result = df_filter[
                (df_filter['価格_数値'] >= min_p) & (df_filter['価格_数値'] <= max_p) &
                (df_filter['関連レビュー_数値'] >= min_rev) & (df_filter['関連レビュー_数値'] <= max_rev) &
                (df_filter['関連レビュー_数値'] > 0) & # 👈 レビュー0件を絶対に排除
                (df_filter['ショップレビュー_数値'] >= min_shop_rev) & (df_filter['ショップレビュー_数値'] <= max_shop_rev) &
                (df_filter['関連レビュー日1_日付'] >= start_dt) & (df_filter['関連レビュー日1_日付'] <= end_dt)
            ]
        else:
            # 日付指定なしの場合：日付に関係なくすべて、レビュー0件も含む
            df_result = df_filter[
                (df_filter['価格_数値'] >= min_p) & (df_filter['価格_数値'] <= max_p) &
                (df_filter['関連レビュー_数値'] >= min_rev) & (df_filter['関連レビュー_数値'] <= max_rev) &
                (df_filter['ショップレビュー_数値'] >= min_shop_rev) & (df_filter['ショップレビュー_数値'] <= max_shop_rev)
            ]
        
        display_cols = ["ショップ名", "商品名", "価格", "URL", "関連レビュー数", "関連レビュー日1", "関連レビュー日2", "関連レビュー日3", "ショップレビュー数", "ハッシュタグ"]
        df_final = df_result[display_cols]
        
        st.success(f"🎯 解析完了！ 条件にマッチした作品が 【 {len(df_final)} 件 】 見つかりました。")
        
        csv = df_final.to_csv(index=False).encode('utf-8-sig')
        st.download_button(label="📥 結果をExcel(CSV)形式でダウンロード", data=csv, file_name=f"minne_research_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
        st.dataframe(df_final, column_config={"URL": st.column_config.LinkColumn("URL")}, use_container_width=True)
