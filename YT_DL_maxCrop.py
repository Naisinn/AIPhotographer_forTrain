import os
import re
import yt_dlp
import subprocess
import concurrent.futures
from tqdm import tqdm
import threading

def sanitize_filename(name):
    """ファイル名から特殊文字を除去する関数"""
    return re.sub(r'[\\/:*?"<>|]', "_", name)

def download_video(url, output_path, progress_bar):
    """動画をダウンロードする関数"""
    def progress_hook(d):
        if d['status'] == 'downloading':
            if d.get('total_bytes'):
                downloaded = d['downloaded_bytes']
                total = d['total_bytes']
                percentage = downloaded / total * 100
                progress_bar.update(percentage - progress_bar.n)
        elif d['status'] == 'finished':
            progress_bar.n = 100
            progress_bar.refresh()

    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': output_path,
        'merge_output_format': 'mp4',  # 出力形式を MP4 に統一
        'progress_hooks': [progress_hook],
        'noprogress': True,  # 自動プログレス出力を無効化
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def process_video_ffmpeg(input_video, output_dir, filename_prefix, aspect_ratio, progress_bar):
    """ffmpeg で動画を処理する関数"""
    if aspect_ratio == "h":
        crop_filter = "crop=w=3/4*ih:h=ih:x=(iw-3/4*ih)/2:y=0"
    elif aspect_ratio == "v":
        crop_filter = "crop=w=iw:h=4/3*iw:x=0:y=(ih-4/3*iw)/2"
    else:
        crop_filter = "crop=w=iw:h=ih:x=0:y=0"

    output_pattern = os.path.join(output_dir, f"{filename_prefix}_%04d.jpg")
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", input_video,
        "-vf", f"fps=1/5,{crop_filter}",
        "-q:v", "1",
        output_pattern,
    ]

    process = subprocess.Popen(
        ffmpeg_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        universal_newlines=True
    )

    total_time = None
    for line in process.stderr:
        if 'Duration' in line and total_time is None:
            # Duration: 00:02:00.00
            match = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', line)
            if match:
                hours = int(match.group(1))
                minutes = int(match.group(2))
                seconds = float(match.group(3))
                total_time = hours * 3600 + minutes * 60 + seconds
        if 'time=' in line and total_time:
            match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
            if match:
                hours = int(match.group(1))
                minutes = int(match.group(2))
                seconds = float(match.group(3))
                elapsed = hours * 3600 + minutes * 60 + seconds
                percentage = min(elapsed / total_time * 100, 100)
                progress_bar.update(percentage - progress_bar.n)

    process.wait()
    if process.returncode != 0:
        stderr = process.stderr.read()
        raise subprocess.CalledProcessError(process.returncode, ffmpeg_cmd, stderr)

    progress_bar.n = 100
    progress_bar.refresh()

def process_single_video(i, video_url, output_dir, filename_prefix, aspect_ratio, temp_dir, position):
    """単一の動画をダウンロードし、処理する関数"""
    try:
        filename_prefix_clean = sanitize_filename(filename_prefix)
        prefix_dir = os.path.join(output_dir, filename_prefix_clean)
        os.makedirs(prefix_dir, exist_ok=True)

        train_dir = os.path.join(prefix_dir, "train_images")
        os.makedirs(train_dir, exist_ok=True)

        temp_video_path = os.path.join(temp_dir, f"{filename_prefix_clean}.mp4")

        # ダウンロードプログレスバー
        download_pbar = tqdm(total=100, desc=f"動画 {i+1} ダウンロード", position=position, leave=False, unit="%")
        download_video(video_url, temp_video_path, download_pbar)
        download_pbar.close()

        # ダウンロードが成功したか確認
        if not (os.path.exists(temp_video_path) and os.path.getsize(temp_video_path) > 0):
            print(f"動画 {i+1} のダウンロードが不完全です。ffmpeg の処理をスキップします。")
            return False

        # ffmpeg プロセスプログレスバー
        ffmpeg_pbar = tqdm(total=100, desc=f"動画 {i+1} 処理", position=position + 1, leave=False, unit="%")
        try:
            process_video_ffmpeg(temp_video_path, train_dir, filename_prefix_clean, aspect_ratio, ffmpeg_pbar)
        except subprocess.CalledProcessError as e:
            print(f"動画 {i+1} の ffmpeg 処理中にエラーが発生しました。")
            print(e.stderr)
            ffmpeg_pbar.close()
            return False
        ffmpeg_pbar.close()

        # 一時ファイルを削除
        try:
            os.remove(temp_video_path)
            print(f"一時ファイル '{temp_video_path}' を削除しました。")
        except Exception as e:
            print(f"一時ファイルの削除に失敗しました: {e}")

        return True

    except Exception as e:
        print(f"動画 {i+1} の処理中に例外が発生しました: {e}")
        return False

def main():
    try:
        def get_multiline_input(prompt):
            """複数行の入力を取得する関数"""
            print(prompt)
            lines = []
            while True:
                line = input()
                if not line.strip():
                    break
                lines.append(line.strip())
            return lines

        video_urls = get_multiline_input("動画のURLを改行区切りで入力してください:\n（入力を終了するには、空行を入力してください）")
        print(f"入力された動画URLの数: {len(video_urls)}")
        output_dir = input("出力ディレクトリを入力してください: ").strip('"')
        print(f"出力ディレクトリ: {output_dir}")
        filename_prefixes = get_multiline_input("出力ファイル名のプレフィックスを改行区切りで入力してください:\n（入力を終了するには、空行を入力してください）")
        print(f"入力されたプレフィックスの数: {len(filename_prefixes)}")
        aspect_ratios = get_multiline_input("横:縦が3:4よりも横長ですか？縦長ですか？ (h: 横長, v: 縦長) を改行区切りで入力してください:\n（入力を終了するには、空行を入力してください）")
        print(f"入力されたアスペクト比の数: {len(aspect_ratios)}")

        # 入力値の数が一致することを確認
        if not (len(video_urls) == len(filename_prefixes) == len(aspect_ratios)):
            print("エラー: 入力値の数が一致しません。")
            exit(1)

        # 一時ファイルの保存先を設定（ローカルディスク上の temp_dir を使用）
        temp_dir = "C:\\Temp"
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir, exist_ok=True)
        print(f"一時ファイルの保存先: {temp_dir}")

        # 並列実行のために各動画に一意のプログレスバー位置を割り当て
        # `tqdm` の position パラメータは、同時に表示されるバーの位置を指定します。
        # 動画数が多い場合、スクロールが必要になるため注意が必要です。
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:  # 必要に応じて max_workers を調整
            futures = []
            for i, (video_url, filename_prefix, aspect_ratio) in enumerate(zip(video_urls, filename_prefixes, aspect_ratios)):
                futures.append(
                    executor.submit(
                        process_single_video, i + 1, video_url, output_dir, filename_prefix, aspect_ratio, temp_dir, i * 2
                    )
                )

            # 全体の進行状況プログレスバー
            overall_pbar = tqdm(total=len(futures), desc="全動画の処理", unit="動画", ncols=100)
            for future in concurrent.futures.as_completed(futures):
                success = future.result()
                if success:
                    overall_pbar.set_postfix({"状態": "完了"})
                else:
                    overall_pbar.set_postfix({"状態": "失敗"})
                overall_pbar.update(1)
            overall_pbar.close()

        print("全ての処理が完了しました。")
    except Exception as e:
        print(f"メイン処理中に例外が発生しました: {e}")

if __name__ == "__main__":
    main()
