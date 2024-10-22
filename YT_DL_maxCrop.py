import subprocess
import os
import re
import concurrent.futures
import tempfile
from tqdm import tqdm  # プログレスバー用ライブラリのインポート
import threading

def generate_ffmpeg_command(video_path, output_dir, filename_prefix, aspect_ratio):
    """動画のアスペクト比に応じて ffmpeg コマンドを生成する関数"""

    if aspect_ratio == "h":
        crop_filter = "crop=w=3/4*ih:h=ih:x=(iw-3/4*ih)/2:y=0"
    elif aspect_ratio == "v":
        crop_filter = "crop=w=iw:h=4/3*iw:x=0:y=(ih-4/3*iw)/2"
    else:
        crop_filter = "crop=w=iw:h=ih:x=0:y=0"

    ffmpeg_cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vf", f"fps=1/5,{crop_filter}",
        "-q:v", "1",
        os.path.join(output_dir, f"{filename_prefix}_%04d.jpg"),
    ]

    return ffmpeg_cmd

def get_multiline_input(prompt):
    """複数行の入力を取得する関数"""
    lines = []
    print(prompt)
    while True:
        try:
            line = input()
            if line.strip() == "":
                break
            lines.append(line.strip())
        except EOFError:
            break
    return lines

def process_video(i, video_url, output_dir, filename_prefix, aspect_ratio, temp_dir, position):
    """動画をダウンロードし、ffmpeg で処理する関数"""
    success = False  # 処理が成功したかどうかを示すフラグ
    try:
        print(f"動画 {i+1} の処理を開始します。")
        # プレフィックス名から特殊文字を削除
        filename_prefix_clean = re.sub(r'[\\/:*?"<>|]', "_", filename_prefix)
        aspect_ratio = aspect_ratio.strip().lower()

        if aspect_ratio not in ["h", "v"]:
            print(f"動画 {i+1} のアスペクト比が無効です。'h' または 'v' を入力してください。")
            return False  # 処理が失敗したことを示す

        # プレフィックス名のフォルダを作成
        prefix_dir = os.path.join(output_dir, filename_prefix_clean)
        os.makedirs(prefix_dir, exist_ok=True)
        print(f"ディレクトリ '{prefix_dir}' を作成または確認しました。")

        # train_images フォルダを作成
        train_dir = os.path.join(prefix_dir, "train_images")
        os.makedirs(train_dir, exist_ok=True)
        print(f"ディレクトリ '{train_dir}' を作成または確認しました。")

        # 一時ファイルのパスを設定（ローカルディスク上の temp_dir を使用）
        temp_video_path = os.path.join(temp_dir, f"{filename_prefix_clean}.mp4")

        # プログレスバーの設定
        download_pbar = tqdm(total=100, desc=f"動画 {i+1} ダウンロード", position=position, leave=False, unit="%", ncols=80)

        # yt-dlp のプログレスフック関数
        def yt_dlp_hook(d):
            if d['status'] == 'downloading':
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
                if total_bytes:
                    downloaded_bytes = d.get('downloaded_bytes', 0)
                    percentage = downloaded_bytes / total_bytes * 100
                    download_pbar.n = percentage
                    download_pbar.refresh()
            elif d['status'] == 'finished':
                download_pbar.n = 100
                download_pbar.refresh()
                download_pbar.close()

        # yt-dlp で動画を一時ファイルにダウンロード
        download_cmd = [
            "yt-dlp",
            "-f", "bestvideo+bestaudio/best",  # 解像度制限を解除
            "--progress-hooks", "hook_script",  # プログレスフックを設定
            "-o", temp_video_path,
            video_url,
        ]

        # 一時的な yt-dlp スクリプトを作成
        hook_script_path = os.path.join(temp_dir, f"hook_{i}.py")
        with open(hook_script_path, 'w', encoding='utf-8') as hook_file:
            hook_file.write("""
import sys
import json

def hook(d):
    import json
    print(json.dumps(d))
    sys.stdout.flush()

hook(json.loads(sys.stdin.read()))
""")

        # yt-dlp コマンドを実行し、プログレスフックを通じてプログレスバーを更新
        print(f"動画 {i+1} のダウンロードコマンドを実行します。")
        process = subprocess.Popen(
            ["yt-dlp"] + ["--progress-hooks", hook_script_path] + download_cmd[1:],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            universal_newlines=True
        )

        # プログレスフックからの出力を処理
        for line in process.stderr:
            try:
                d = json.loads(line.strip())
                yt_dlp_hook(d)
            except json.JSONDecodeError:
                continue

        process.wait()

        if process.returncode != 0:
            print(f"動画 {i+1} のダウンロード中にエラーが発生しました。")
            print(process.stderr.read())
            return False

        print(f"動画 {i+1} のダウンロードが完了しました。")

        # ダウンロードが成功しているか再度チェック
        if os.path.exists(temp_video_path) and os.path.getsize(temp_video_path) > 0:
            # ダウンロードファイルのサイズをログに出力
            file_size_mb = os.path.getsize(temp_video_path) / (1024 * 1024)
            print(f"動画 {i+1} のダウンロードファイルサイズ: {file_size_mb:.2f} MB")

            # ffmpeg プロセスのプログレスバー設定
            ffmpeg_pbar = tqdm(total=100, desc=f"動画 {i+1} 処理", position=position+1, leave=False, unit="%", ncols=80)

            # ffmpeg のプログレスフック関数
            def ffmpeg_hook(proc):
                while True:
                    line = proc.stderr.readline()
                    if not line:
                        break
                    if "time=" in line:
                        # 時間情報を抽出して進行状況を推定
                        match = re.search(r"time=(\d+):(\d+):(\d+\.\d+)", line)
                        if match:
                            hours = float(match.group(1))
                            minutes = float(match.group(2))
                            seconds = float(match.group(3))
                            elapsed = hours * 3600 + minutes * 60 + seconds
                            # ここでは簡単に推定
                            # 正確な進行状況を得るには動画の全体時間が必要
                            # この例では仮に動画の長さを2分と仮定
                            total_time = 120  # 秒
                            percentage = min(elapsed / total_time * 100, 100)
                            ffmpeg_pbar.n = percentage
                            ffmpeg_pbar.refresh()

            # ffmpeg コマンドを生成して実行
            ffmpeg_cmd = generate_ffmpeg_command(temp_video_path, train_dir, filename_prefix_clean, aspect_ratio)
            print(f"動画 {i+1} の ffmpeg 処理を実行します。")
            ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                universal_newlines=True
            )

            # ffmpeg のプログレスフックをスレッドで実行
            ffmpeg_thread = threading.Thread(target=ffmpeg_hook, args=(ffmpeg_process,))
            ffmpeg_thread.start()

            ffmpeg_process.wait()
            ffmpeg_thread.join()

            if ffmpeg_process.returncode != 0:
                print(f"動画 {i+1} の ffmpeg 処理中にエラーが発生しました。")
                print(ffmpeg_process.stderr.read())
                ffmpeg_pbar.close()
                return False

            ffmpeg_pbar.n = 100
            ffmpeg_pbar.refresh()
            ffmpeg_pbar.close()
            print(f"動画 {i+1} の処理が完了しました。")

            # 一時ファイルを削除
            try:
                os.remove(temp_video_path)
                print(f"一時ファイル '{temp_video_path}' を削除しました。")
            except Exception as e:
                print(f"一時ファイルの削除に失敗しました: {e}")

            success = True
        else:
            print(f"動画 {i+1} のダウンロードが不完全です。ffmpeg の処理をスキップします。")
            success = False

    except Exception as e:
        print(f"動画 {i+1} の処理中に例外が発生しました: {e}")
        success = False

    return success

# --- メイン処理 ---
if __name__ == "__main__":
    try:
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
        # 例: C:\Temp
        temp_dir = "C:\\Temp"
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir, exist_ok=True)
        print(f"一時ファイルの保存先: {temp_dir}")

        # 並列実行のために各動画に一意のプログレスバー位置を割り当て
        # `tqdm` の position パラメータは、同時に表示されるバーの位置を指定します。
        # 動画数が多い場合、スクロールが必要になるため注意が必要です。
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            for i, video_url in enumerate(video_urls):
                futures.append(
                    executor.submit(
                        process_video, i, video_url, output_dir, filename_prefixes[i], aspect_ratios[i], temp_dir, i * 2
                    )
                )

            # tqdm を使用して全体の進行状況を表示
            with tqdm(total=len(futures), desc="全動画の処理", unit="動画", ncols=100) as pbar:
                for future in concurrent.futures.as_completed(futures):
                    success = future.result()
                    if success:
                        pbar.set_postfix({"状態": "完了"})
                    else:
                        pbar.set_postfix({"状態": "失敗"})
                    pbar.update(1)

        print("全ての処理が完了しました。")
    except Exception as e:
        print(f"メイン処理中に例外が発生しました: {e}")
