import subprocess

def generate_ffmpeg_command(video_path, output_dir, filename_prefix, aspect_ratio):
    """動画のアスペクト比に応じて ffmpeg コマンドを生成する関数

    Args:
        video_path (str): 入力動画のパス
        output_dir (str): 出力ディレクトリ
        filename_prefix (str): 出力ファイル名のプレフィックス
        aspect_ratio (str): 動画のアスペクト比 ("h" または "v")

    Returns:
        list: ffmpeg コマンド
    """

    # アスペクト比に応じて crop フィルタのパラメータを決定
    if aspect_ratio == "h":
        crop_filter = f"crop=w=3/4*ih:h=ih:x=(iw-3/4*ih)/2:y=0"
    elif aspect_ratio == "v":
        crop_filter = f"crop=w=iw:h=4/3*iw:x=0:y=(ih-4/3*iw)/2"
    else:
        crop_filter = "crop=w=iw:h=ih:x=0:y=0"

    # ffmpeg コマンドを生成
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vf", f"fps=1/5,{crop_filter}",
        "-q:v", "1",
        f"{output_dir}/{filename_prefix}_%04d.jpg",
    ]

    return ffmpeg_cmd

def get_multiline_input(prompt):
    """複数行の入力を取得する関数

    Args:
        prompt (str): 入力時に表示するメッセージ

    Returns:
        list: 入力された各行を要素とするリスト
    """
    lines = []
    print(prompt)
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    return lines

# --- メイン処理 ---
if __name__ == "__main__":
    video_urls = get_multiline_input("動画のURLを改行区切りで入力してください:\n（入力を終了するには、空行を入力してください）")
    output_dir = input("出力ディレクトリを入力してください: ")
    filename_prefixes = get_multiline_input("出力ファイル名のプレフィックスを改行区切りで入力してください:\n（入力を終了するには、空行を入力してください）")
    aspect_ratios = get_multiline_input("横:縦が3:4よりも横長ですか？縦長ですか？ (h: 横長, v: 縦長) を改行区切りで入力してください:\n（入力を終了するには、空行を入力してください）")

    # 入力値の数が一致することを確認
    if not (len(video_urls) == len(filename_prefixes) == len(aspect_ratios)):
        print("エラー: 入力値の数が一致しません。")
        exit(1)

    # 各動画について処理を実行
    for i, video_url in enumerate(video_urls):
        filename_prefix = filename_prefixes[i]
        aspect_ratio = aspect_ratios[i].strip().lower()

        if aspect_ratio not in ["h", "v"]:
            print(f"動画 {i+1} のアスペクト比が無効です。'h' または 'v' を入力してください。")
            continue

        # yt-dlp で動画をダウンロードし、ffmpeg で処理
        download_cmd = [
            "yt-dlp",
            "-f", "bv+ba/b",
            "-o", "-",
            video_url,
        ]
        ffmpeg_cmd = generate_ffmpeg_command("-", output_dir, filename_prefix, aspect_ratio)

        # yt-dlp と ffmpeg をパイプで接続して同時に実行
        download_process = subprocess.Popen(download_cmd, stdout=subprocess.PIPE)
        ffmpeg_process = subprocess.Popen(ffmpeg_cmd, stdin=download_process.stdout)  # shell=True を削除

        # プロセスの終了を待つ
        download_process.stdout.close()  # パイプの終端を閉じる

        download_process.wait()
        ffmpeg_process.wait()

        print(f"動画 {i+1} の処理が完了しました。")

    print("全ての処理が完了しました。")