import subprocess
from tqdm import tqdm

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
        crop_filter = f"crop=w=ih*4/3:h=ih:x=(iw-out_w)/2:y=0"
    elif aspect_ratio == "v":
        crop_filter = f"crop=w=iw:h=iw*3/4:x=0:y=(ih-out_h)/2"
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

    # プログレスバーを表示
    with tqdm(total=100, desc="Processing", unit="%", ncols=100) as pbar:
        while download_process.poll() is None or ffmpeg_process.poll() is None:
            pbar.update(1)
            pbar.refresh()

    download_process.wait()
    ffmpeg_process.wait()

    print("処理が完了しました。")