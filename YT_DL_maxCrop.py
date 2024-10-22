import subprocess
import os
import re
import concurrent.futures
import tempfile
import shutil

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

def process_video(i, video_url, output_dir, filename_prefix, aspect_ratio, temp_dir):
    """動画をダウンロードし、ffmpeg で処理する関数"""
    print(f"動画 {i+1} の処理を開始します。")
    # プレフィックス名から特殊文字を削除
    filename_prefix = re.sub(r'[\\/:*?"<>|]', "_", filename_prefix)
    aspect_ratio = aspect_ratio.strip().lower()

    if aspect_ratio not in ["h", "v"]:
        print(f"動画 {i+1} のアスペクト比が無効です。'h' または 'v' を入力してください。")
        return

    # プレフィックス名のフォルダを作成
    prefix_dir = os.path.join(output_dir, filename_prefix)
    os.makedirs(prefix_dir, exist_ok=True)
    print(f"ディレクトリ '{prefix_dir}' を作成または確認しました。")

    # train_images フォルダを作成
    train_dir = os.path.join(prefix_dir, "train_images")
    os.makedirs(train_dir, exist_ok=True)
    print(f"ディレクトリ '{train_dir}' を作成または確認しました。")

    # 一時ファイルのパスを設定（ローカルディスク上の temp_dir を使用）
    temp_video_path = os.path.join(temp_dir, f"{filename_prefix}.mp4")

    # yt-dlp で動画を一時ファイルにダウンロード
    download_cmd = [
        "yt-dlp",
        "-f", "bestvideo+bestaudio/best",  # 解像度制限を解除
        "-o", temp_video_path,
        video_url,
    ]

    print(f"動画 {i+1} のダウンロードコマンドを実行します。")
    try:
        result = subprocess.run(download_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        print(f"動画 {i+1} のダウンロードが完了しました。")
    except subprocess.CalledProcessError as e:
        print(f"動画 {i+1} のダウンロード中にエラーが発生しました。")
        print(e.stderr)
        return

    # ダウンロードが成功しているか再度チェック
    if os.path.exists(temp_video_path) and os.path.getsize(temp_video_path) > 0:
        # ffmpeg コマンドを生成して実行
        ffmpeg_cmd = generate_ffmpeg_command(temp_video_path, train_dir, filename_prefix, aspect_ratio)

        print(f"動画 {i+1} の ffmpeg 処理を実行します。")
        try:
            result = subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            print(f"動画 {i+1} の処理が完了しました。")
        except subprocess.CalledProcessError as e:
            print(f"動画 {i+1} の ffmpeg 処理中にエラーが発生しました。")
            print(e.stderr)
            return
        finally:
            # 一時ファイルを削除
            try:
                os.remove(temp_video_path)
                print(f"一時ファイル '{temp_video_path}' を削除しました。")
            except Exception as e:
                print(f"一時ファイルの削除に失敗しました: {e}")
    else:
        print(f"動画 {i+1} のダウンロードが不完全です。ffmpeg の処理をスキップします。")

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

        # マルチスレッドで各動画の処理を実行（並列実行数を制限しない）
        with concurrent.futures.ThreadPoolExecutor() as executor:  # デフォルトで適切な数に設定されます
            futures = []
            for i, video_url in enumerate(video_urls):
                futures.append(
                    executor.submit(
                        process_video, i, video_url, output_dir, filename_prefixes[i], aspect_ratios[i], temp_dir
                    )
                )

            # 全てのスレッドの終了を待つ
            concurrent.futures.wait(futures)

        print("全ての処理が完了しました。")
    except Exception as e:
        print(f"メイン処理中に例外が発生しました: {e}")
