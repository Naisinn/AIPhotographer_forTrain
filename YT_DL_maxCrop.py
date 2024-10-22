import subprocess
import os
import re
import concurrent.futures

def generate_ffmpeg_command(output_dir, filename_prefix, aspect_ratio):
    """動画のアスペクト比に応じて ffmpeg コマンドを生成する関数"""

    if aspect_ratio == "h":
        crop_filter = f"crop=w=3/4*ih:h=ih:x=(iw-3/4*ih)/2:y=0"
    elif aspect_ratio == "v":
        crop_filter = f"crop=w=iw:h=4/3*iw:x=0:y=(ih-4/3*iw)/2"
    else:
        crop_filter = "crop=w=iw:h=ih:x=0:y=0"

    ffmpeg_cmd = [
        "ffmpeg",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "5",
        "-i", "pipe:0",
        "-vf", f"fps=1/5,{crop_filter}",
        "-q:v", "1",
        os.path.join(output_dir, f"{filename_prefix}_%04d.jpg"),
    ]

    return ffmpeg_cmd

def process_video(i, video_url, output_dir, filename_prefix, aspect_ratio):
    """動画をダウンロードし、ffmpeg で処理する関数"""
    filename_prefix = re.sub(r'[\\/:*?"<>|]', "_", filename_prefix)
    aspect_ratio = aspect_ratio.strip().lower()

    if aspect_ratio not in ["h", "v"]:
        print(f"動画 {i+1} のアスペクト比が無効です。'h' または 'v' を入力してください。")
        return

    # プレフィックス名のフォルダを作成
    prefix_dir = os.path.join(output_dir, filename_prefix)
    os.makedirs(prefix_dir, exist_ok=True)

    # train_images フォルダを作成
    train_dir = os.path.join(prefix_dir, "train_images")
    os.makedirs(train_dir, exist_ok=True)

    # yt-dlp と ffmpeg をパイプで接続して同時に実行
    download_cmd = [
        "yt-dlp",
        "-f", "bv+ba/b",
        "--buffer-size", "16K",
        "-o", "-",
        video_url,
    ]
    ffmpeg_cmd = generate_ffmpeg_command(train_dir, filename_prefix, aspect_ratio)

    try:
        download_process = subprocess.Popen(download_cmd, stdout=subprocess.PIPE)
        ffmpeg_process = subprocess.Popen(ffmpeg_cmd, stdin=download_process.stdout)
        download_process.stdout.close()
        ffmpeg_process.wait()
        download_process.wait()
        print(f"動画 {i+1} の処理が完了しました。")
    except subprocess.CalledProcessError:
        print(f"動画 {i+1} の処理中にエラーが発生しました。")
        return
