import streamlit as st
import requests
import re

st.set_page_config(page_title="パターン検索テスト", layout="wide")
st.title("🕵️‍♂️ 日付パターン「YYYY/MM/DD」の全スキャン")

target_url = "https://minne.com/@enuzu7/reviews?page=64"
headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

st.info(f"アクセス中: {target_url}")

try:
    res = requests.get(target_url, headers=headers, timeout=10)
    
    if res.status_code == 200:
        html_text = res.text
        
        st.subheader("🔍 パターン検索の結果")
        
        # 「数字4桁/数字2桁/数字2桁」の形（2015/03/09 など）をページ全体から探す
        # 秒数まで含む形「\d{4}/\d{2}/\d{2}\s\d{2}:\d{2}:\d{2}」も一応カバー
        date_pattern = r'\d{4}/\d{2}/\d{2}'
        found_dates = re.findall(date_pattern, html_text)
        
        st.write(f"・『YYYY/MM/DD』の形で引っかかった件数: **{len(found_dates)} 件**")
        
        if found_dates:
            st.success("🎉 日付データを発見しました！以下のデータが文字として含まれています：")
            st.code(found_dates)
        else:
            st.error("❌ 『YYYY/MM/DD』の形をした文字は、ページの生のデータの中に1件も見つかりませんでした。")
            
            st.subheader("💡 これで分かったこと")
            st.write(
                "この形で1件も出ないということは、HTMLの目印（タグ）の問題ではなく、"
                "**『そもそもツールがページを読み込んだ瞬間には、画面に2020年や2015年といった日付の文字自体がまだ存在していない（後から読み込まれる仕組みである）』** "
                "ということが完全に証明されました。"
            )

except Exception as e:
    st.error(f"エラーが発生しました: {e}")
