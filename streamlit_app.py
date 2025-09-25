import datetime
import pathlib
import re

import pandas as pd
import requests
from gtts import gTTS
from streamlit_folium import st_folium

import folium
import streamlit as st

base_url = st.secrets["url"]


def convert_time_format(time_str):
    # 各時間帯を分割
    time_ranges = time_str.split(" / ")
    converted_ranges = []

    for time_range in time_ranges:
        # 正規表現で時間を抽出
        m = re.match(r"(\d{2}):(\d{2})～(翌)?(\d{2}):(\d{2})", time_range)
        if m:
            start_hour, start_minute, next_day, end_hour, end_minute = m.groups()
            # 分が0の場合のフォーマットを変換
            start_time = f"{int(start_hour)}時" if start_minute == "00" else f"{int(start_hour)}時{int(start_minute)}分"
            end_time = f"{int(end_hour)}時" if end_minute == "00" else f"{int(end_hour)}時{int(end_minute)}分"
            # 翌日の場合のフォーマットを変換
            if next_day:
                converted_ranges.append(f"{start_time}から翌日{end_time}まで")
            else:
                converted_ranges.append(f"{start_time}から{end_time}まで")

    # 変換された時間帯を結合
    return "、".join(converted_ranges)


def make_voice(current, fn):
    date_string = re.sub(r"\d{4}年0?(\d+)月0?(\d+)日", r"\1月\2日", current["date_week"])

    text = []

    text.append(f"{date_string}の救急当番病院をおしらせします")

    for hospital in current["hospitals"]:
        match hospital["type"]:
            case 7 | 8:
                text.append(f'{hospital["medical"]}の診察は')
            case 9:
                text.append("島しょ部の診察は")

        text.append(convert_time_format(hospital["time"]))
        text.append(hospital["hira_address"])
        text.append(hospital["hira_name"])
        text.append("電話")
        text.append(f'{hospital["daytime"]}')

    message = "、".join(text)

    print(message)

    tts = gTTS(text=message, lang="ja")
    tts.save(fn)


@st.cache_data(ttl="3h")
def load_data():
    url = f"{base_url}/data.json"

    r = requests.get(url)
    r.raise_for_status()

    data = r.json()

    return data


st.set_page_config(page_title="今治市救急当番病院案内")
st.title("今治市救急当番病院案内")


data = load_data()

today = datetime.date.today()

option = list(data.keys())

start = datetime.datetime.strptime(option[0], r"%Y-%m-%d").date()
end = datetime.datetime.strptime(option[-1], r"%Y-%m-%d").date()

# 日付入力ウィジェットを表示
selected_date = st.date_input("日付を選択してください", value=today, min_value=start, max_value=end)


if selected_date:
    chois = selected_date.strftime(r"%Y-%m-%d")

    if chois in option:
        fn = pathlib.Path(f"{chois}.mp3")

        if not fn.exists():
            make_voice(data[chois], fn)

        st.subheader(data[chois]["date_week"])

        df = pd.DataFrame(data[chois]["hospitals"]).reindex(
            columns=["name", "medical", "time", "daytime", "address", "lat", "lon", "type", "link"]
        )

        st.dataframe(
            df[["name", "medical", "time", "daytime", "address", "link"]],
            column_config={
                "name": "医療機関名",
                "medical": "診療科目",
                "time": "診療時間",
                "daytime": "電話番号",
                "address": "住所",
                "link": st.column_config.LinkColumn("リンク", display_text="詳細"),
            },
            width="stretch",
            hide_index=True,
        )

        if fn.exists():
            st.audio(str(fn), format="audio/mpeg")
        else:
            st.write("音声データが見つかりません")

        gdf = (
            df.groupby("name")
            .agg(
                {
                    "medical": "・".join,
                    "type": "first",
                    "address": "first",
                    "lat": "first",
                    "lon": "first",
                }
            )
            .reset_index()
        )

        map_cont = st.container(height=500, border=True)
        
        with map_cont:

            m = folium.Map(
                location=[df["lat"].mean(), df["lon"].mean()],
                tiles="https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png",
                attr='&copy; <a href="https://maps.gsi.go.jp/development/ichiran.html">国土地理院</a>',
                zoom_start=10,
            )
    
            for _, r in gdf.iterrows():
                match r["type"]:
                    case 70:
                        color = "orange"
                    case 80:
                        color = "green"
                    case 90:
                        color = "blue"
                    case _:
                        color = "red"
    
                folium.Marker(
                    location=[r["lat"], r["lon"]],
                    popup=folium.Popup(
                        f'<p>{r["name"]}</p><p>{r["medical"]}</p>',
                        max_width=300,
                    ),
                    tooltip=r["name"],
                    icon=folium.Icon(color=color),
                ).add_to(m)
    
            st_data = st_folium(m, use_container_width=True, returned_objects=[])
    else:
        st.write("データが見つかりません")

st.image("logo_Code4Imabari_blue.png")
st.markdown("Powered by [Code for Imabari](https://www.code4imabari.org/)")
