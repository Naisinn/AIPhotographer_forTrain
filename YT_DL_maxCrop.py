import os
import re
import yt_dlp
import subprocess
import concurrent.futures
from tqdm import tqdm

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
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',  # 'preferredformat' のスペルに注意
        }],
        'progress_hooks': [progress_hook],
        'noprogress': True,  # 自動プログレス出力を無効化
        'quiet': True,        # yt_dlp の標準出力を抑制
        'no_warnings': True,  # 警告を抑制
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def get_video_duration(input_video):
    """ffprobe を使用して動画の総時間を取得する関数"""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        input_video
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode == 0:
        try:
            return float(result.stdout.strip())
        except ValueError:
            return None
    else:
        return None

def process_video_ffmpeg(input_video, output_dir, filename_prefix, aspect_ratio, progress_bar, start_time=0, start_number=1):
    """ffmpeg で動画を処理する関数"""
    try:
        if aspect_ratio == "h":
            crop_filter = "crop=w=3/4*ih:h=ih:x=(iw-3/4*ih)/2:y=0"
        elif aspect_ratio == "v":
            crop_filter = "crop=w=iw:h=4/3*iw:x=0:y=(ih-4/3*iw)/2"
        else:
            crop_filter = "crop=w=iw:h=ih:x=0:y=0"

        output_pattern = os.path.join(output_dir, f"{filename_prefix}_%04d.jpg")
        ffmpeg_cmd = [
            "ffmpeg",
            "-ss", str(start_time),  # 開始時間を指定
            "-i", input_video,
            "-vf", f"fps=1/5,{crop_filter}",
            "-q:v", "1",
            "-start_number", str(start_number),  # 開始フレーム番号を指定
            output_pattern,
        ]

        # 動画の総時間を取得
        total_time = get_video_duration(input_video)
        if total_time is None:
            total_time = 120  # 仮の値を設定（必要に応じて調整）

        process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            universal_newlines=True
        )

        for line in process.stderr:
            if 'time=' in line:
                # 時間情報を抽出して進行状況を推定
                match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
                if match and total_time > 0:
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

    except Exception as e:
        print(f"ffmpeg 処理中にエラーが発生しました: {e}")
        raise  # エラーを再スローして上位で処理

def process_single_video(i, video_url, output_dir, filename_prefix, aspect_ratio, temp_dir, position):
    """単一の動画をダウンロードし、処理する関数"""
    temp_video_path = os.path.join(temp_dir, f"{sanitize_filename(filename_prefix)}.mp4")
    try:
        filename_prefix_clean = sanitize_filename(filename_prefix)
        prefix_dir = os.path.join(output_dir, filename_prefix_clean)
        train_dir = os.path.join(prefix_dir, "train_images")
        os.makedirs(train_dir, exist_ok=True)

        # 既に処理が完了している場合はスキップ
        existing_frames = sorted([fname for fname in os.listdir(train_dir) if fname.endswith('.jpg')])
        total_expected_frames = None

        if existing_frames:
            # 既に生成されたフレーム数をカウント
            existing_frame_count = len(existing_frames)
            # 動画の総時間を取得
            video_duration = get_video_duration(temp_video_path)
            if video_duration is None:
                # 一時ファイルが存在しない場合、動画がダウンロードされていないと判断
                video_duration = 120  # 仮の値を設定（必要に応じて調整）
            total_expected_frames = int(video_duration / 5)  # fps=1/5なので、5秒ごとに1フレーム

            if existing_frame_count >= total_expected_frames:
                print(f"動画 {i} の処理は既に完了しています。スキップします。")
                return True

            # 次に生成すべきフレームの開始番号と開始時間を計算
            start_number = existing_frame_count + 1
            start_time = existing_frame_count * 5  # 5秒ごとに1フレーム

            print(f"動画 {i} の処理を再開します。開始フレーム: {start_number}, 開始時間: {start_time}秒")
        else:
            start_number = 1
            start_time = 0

        # ダウンロードがまだ完了していない場合のみダウンロード
        if not (os.path.exists(temp_video_path) and os.path.getsize(temp_video_path) > 0):
            # ダウンロードプログレスバー
            download_pbar = tqdm(total=100, desc=f"動画 {i} ダウンロード", position=position, leave=False, unit="%")
            download_video(video_url, temp_video_path, download_pbar)
            download_pbar.close()

            # ダウンロードが成功したか確認
            if not (os.path.exists(temp_video_path) and os.path.getsize(temp_video_path) > 0):
                print(f"動画 {i} のダウンロードが不完全です。ffmpeg の処理をスキップします。")
                return False
        else:
            print(f"動画 {i} は既にダウンロードされています。")

        # ffmpeg プロセスプログレスバー
        ffmpeg_pbar = tqdm(total=100, desc=f"動画 {i} 処理", position=position + 1, leave=False, unit="%")
        try:
            process_video_ffmpeg(temp_video_path, train_dir, filename_prefix_clean, aspect_ratio, ffmpeg_pbar, start_time, start_number)
        except subprocess.CalledProcessError as e:
            print(f"動画 {i} の ffmpeg 処理中にエラーが発生しました。")
            print(e.stderr)
            ffmpeg_pbar.close()
            return False
        ffmpeg_pbar.close()

        # 一時ファイルを削除
        if os.path.exists(temp_video_path):
            try:
                os.remove(temp_video_path)
                print(f"一時ファイル '{temp_video_path}' を削除しました。")
            except Exception as e:
                print(f"一時ファイルの削除に失敗しました: {e}")

        return True

    except Exception as e:
        print(f"動画 {i} の処理中に例外が発生しました: {e}")
        # エラーが発生しても一時ファイルを削除
        if os.path.exists(temp_video_path):
            try:
                os.remove(temp_video_path)
                print(f"一時ファイル '{temp_video_path}' を削除しました。")
            except Exception as del_e:
                print(f"一時ファイルの削除に失敗しました: {del_e}")
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

        # 一時ファイルの保存先を設定（空き容量の多いドライブを指定）
        temp_dir = "C:\\Temp"  # 必要に応じて変更してください
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir, exist_ok=True)
        print(f"一時ファイルの保存先: {temp_dir}")

        # 並列実行のために各動画に一意のプログレスバー位置を割り当て
        # `tqdm` の position パラメータは、同時に表示されるバーの位置を指定します。
        # 動画数が多い場合、スクロールが必要になるため注意が必要です。
        max_workers = 4  # 要求に応じて設定
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
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
