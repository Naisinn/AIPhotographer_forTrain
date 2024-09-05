import subprocess
import re

def generate_ffmpeg_command(video_path, output_dir, filename_prefix):
    """動画のアスペクト比に応じて ffmpeg コマンドを生成する関数

    Args:
        video_path (str): 入力動画のパス
        output_dir (str): 出力ディレクトリ
        filename_prefix (str): 出力ファイル名のプレフィックス

    Returns:
        str: ffmpeg コマンド
    """

    # ffprobe コマンドを実行して動画情報を取得
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        video_path,
    ]
    output = subprocess.check_output(cmd).decode("utf-8").strip()
    width, height = map(int, output.split("x"))

    # アスペクト比に応じて crop フィルタのパラメータを決定
    if width / height > 4 / 3:
        crop_filter = f"crop=w=ih*4/3:h=ih:x=(iw-out_w)/2:y=0"
    elif height / width > 4 / 3:
        crop_filter = f"crop=w=iw:h=iw*3/4:x=0:y=(ih-out_h)/2"
    else:
        crop_filter = "crop=w=iw:h=ih:x=0:y=0"

    # ffmpeg コマンドを生成
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", video_path,
        "-filter_complex", f"[0:v]fps=1/5[fps];[fps]scale=w='if(gt(a,4/3),-1,oh*4/3)':h='if(gt(a,4/3),ow*3/4,-1)'[scaled];[scaled]crop=w='if(gt(a,4/3),in_h*4/3,in_w)':h='if(gt(a,4/3),in_w*3/4,in_h)':x=(in_w-out_w)/2:y=(in_h-out_h)/2[cropped]",
        "-map", "[cropped]",
        "-q:v", "1",
        f"{output_dir}/{filename_prefix}_%04d.jpg",
    ]

    return " ".join(ffmpeg_cmd)

# --- メイン処理 ---
if __name__ == "__main__":
    video_url = input("動画のURLを入力してください: ")
    output_dir = input("出力ディレクトリを入力してください: ")
    filename_prefix = input("出力ファイル名のプレフィックスを入力してください: ")

    # yt-dlp コマンドを生成
    download_cmd = [
        "yt-dlp",
        "-f", "bv+ba/b",
        "-o", "-",
        video_url
    ]

    # ffmpeg コマンドを生成
    ffmpeg_cmd = generate_ffmpeg_command("-", output_dir, filename_prefix)

    # コマンド全体を表示
    print(" ".join(download_cmd) + " | " + ffmpeg_cmd)