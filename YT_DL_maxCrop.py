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
    if aspect_ratio == "h":
        # 横長の動画の場合、左右を削除して中央を3:4で切り抜く
        crop_filter = "fps=1/5,crop=w=3/4*ih:h=ih:x=(iw-3/4*ih)/2:y=0"
    elif aspect_ratio == "v":
        # 縦長の動画の場合、上下を削除して中央を3:4で切り抜く
        crop_filter = "fps=1/5,crop=w=iw:h=4/3*iw:x=0:y=(ih-4/3*iw)/2"
    else:
        crop_filter = "fps=1/5,crop=w=iw:h=ih:x=0:y=0"

    ffmpeg_cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vf", crop_filter,
        "-q:v", "1",
        f"{output_dir}/{filename_prefix}_%04d.jpg",
    ]

    return ffmpeg_cmd

# --- メイン処理 ---
if __name__ == "__main__":
    video_url = input("動画のURLを入力してください: ")
    output_dir = input("出力ディレクトリを入力してください: ")
    filename_prefix = input("出力ファイル名のプレフィックスを入力してください: ")

    # 動画のアスペクト比をユーザーに尋ねる
    aspect_ratio = input("横:縦が3:4よりもその動画は横長ですか？縦長ですか？ (h: 横長, v: 縦長): ").strip().lower()
    if aspect_ratio not in ["h", "v"]:
        print("無効な入力です。'h' または 'v' を入力してください。")
        exit(1)

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
    ffmpeg_process = subprocess.Popen(ffmpeg_cmd, stdin=download_process.stdout)

    # プロセスの終了を待つ
    download_process.stdout.close()  # パイプの終端を閉じる

    download_process.wait()
    ffmpeg_process.wait()

    print("処理が完了しました。")