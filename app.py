import streamlit as st
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="デバッグ画面", layout="wide")
st.title("🕵️‍♂️ レビューページのHTML構造チェック")

# ターゲットURL（検証したい最古のページ）
target_url = "https://minne.com/@enuzu7/reviews?page=64"
headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

st.info(f"現在、次のURLにスクレイピングを仕掛けています... \n{target_url}")

try:
    res = requests.get(target_url, headers=headers, timeout=10)
    st.write(f"📡 通信ステータスコード: {res.status_code} (200なら成功)")
    
    if res.status_code == 200:
        soup = BeautifulSoup(res.text, "html.parser")
        
        st.subheader("1. ページ全体の文字数チェック")
        st.write(f"取得したHTML全体の文字数: {len(res.text)} 文字")
        
        st.subheader("2. 日付のクラス名（目印）の探索テスト")
        
        # パターンA：前回仕込んだ ReviewCard_reviewDate__
        dates_a = soup.find_all(class_=lambda x: x and x.startswith("ReviewCard_reviewDate__"))
        st.write(f"・パターンA (ReviewCard_...) で見つかった件数: {len(dates_a)}件")
        if dates_a:
            st.code([d.text.strip() for d in dates_a])

        # パターンB：以前使っていた MinneReviewCard_reviewDate__
        dates_b = soup.find_all(class_=lambda x: x and x.startswith("MinneReviewCard_reviewDate__"))
        st.write(f"・パターンB (MinneReviewCard_...) で見つかった件数: {len(dates_b)}件")
        if dates_b:
            st.code([d.text.strip() for d in dates_b])

        # パターンC：少し広く「reviewDate」というキーワードを含むものを全スキャン
        dates_c = soup.find_all(class_=lambda x: x and "reviewdate" in x.lower())
        st.write(f"・パターンC (部分一致 reviewdate) で見つかった件数: {len(dates_c)}件")
        if dates_c:
            st.code([f"クラス名: {d.get('class')} / 中身: {d.text.strip()}" for d in dates_c])
            
        st.subheader("3. HTMLの生テキスト（一部抜粋）")
        st.caption("もし上のパターンで1件も引っかからない場合、そもそもminneがJavaScriptなどで後から文字を表示させている（＝プログラムで直接読めない）可能性があります。下の箱に『2020』や『日付』っぽい文字があるか確認します。")
        # 最初の2000文字ほどを表示してみる
        st.text_area("HTMLソース（冒頭部）", value=res.text[:2000], height=200)

except Exception as e:
    st.error(f"エラーが発生しました: {e}")
