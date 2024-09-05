# YT_DL_maxCrop

このプロジェクトは、YouTube動画をダウンロードし、指定したアスペクト比に基づいて中央部分を切り抜くツールです。

## 必要条件

- Python 3.9
- `yt-dlp`
- `ffmpeg`

## インストール

1. 仮想環境を作成し、アクティベートします。

    ```sh
    python3 -m venv YT_DL
    source YT_DL/bin/activate  # Windowsの場合は `YT_DL\Scripts\Activate.ps1`
    ```

2. 必要なパッケージをインストールします。

    ```sh
    pip install yt-dlp
    ```

3. `ffmpeg`をインストールします。詳細は[公式サイト](https://ffmpeg.org/download.html)を参照してください。

## 使い方

1. スクリプトを実行します。

    ```sh
    python YT_DL_maxCrop.py
    ```

2. プロンプトに従って、以下の情報を入力します。

    - 動画のURL
    - 出力ディレクトリ
    - 出力ファイル名のプレフィックス
    - 動画のアスペクト比（横長の場合は `h`、縦長の場合は `v`）

3. 処理が完了すると、指定したディレクトリに切り抜かれた画像が保存されます。

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。