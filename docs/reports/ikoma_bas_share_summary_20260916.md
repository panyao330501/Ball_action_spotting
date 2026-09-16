# IKOMA 動画に対する BAS 推定結果・モデル・推論設定

最終更新日：2026-09-16

## そのまま共有できるメッセージ

件名：IKOMA 動画に対する BAS 推定結果・モデル・推論設定の共有

Martin さん、根木さん

お疲れさまです。現在進めている IKOMA 動画に対する Ball Action Spotting（BAS）の PoC について、現時点の推定結果、使用モデル、推論方法・設定を共有します。

- 対象動画：キックオフ直後から 566.5 秒（約 9 分 26.5 秒）、1280×720、30 FPS
- 検出対象：`Pass` と `Drive`
- 推定候補：合計 58 件（Pass 34 件、Drive 24 件）
- モデル：2023 SoccerNet Ball Action Spotting 優勝ソリューションの公開済み学習済みモデル `ball_finetune_long_004`
- 推論：7 fold の平均、各 fold で horizontal flip TTA を使用
- 入力：元動画を全区間 25 FPS に変換し、リサイズせずに使用。推論入口でグレースケール化し、モデルの前処理で 1280×736 に黒埋めしています
- 時系列設定：33 フレーム、frame step 2（約 2.56 秒のコンテキスト）
- 後処理：クラスごとに Gaussian smoothing（σ=3）、peak threshold 0.2、peak 間最小距離 15 フレーム（0.6 秒）

可視化動画には、各イベントのラベル、信頼度、固定イベント時刻、現在のソース時刻、および全体タイムラインを表示しています。全 58 件を連続して確認できるイベント集も作成済みです。

なお、現時点ではこの動画に対する GT がなく、58 件の候補に対する人手レビューも未完了です。そのため、現段階の件数や信頼度は精度・再現率を示すものではありません。また、表示している信頼度は 7-fold 平均スコアを Gaussian 平滑化した後のピーク値であり、校正済み確率ではありません。

特に以下について、ご意見をいただけると助かります。

1. `Drive` のラベル定義を今回の映像でどのように解釈するのが適切か
2. threshold 0.2、最小間隔 0.6 秒という初期設定が妥当か
3. 主観レビュー時に重視すべき時間許容幅や失敗分類

詳細な設定と結果は下記にまとめています。よろしくお願いいたします。

## 1. 対象動画

| 項目 | 設定 |
| --- | --- |
| ファイル | `vs_飛鳥FC_20260704_trimmed_0930.mp4` |
| 対象区間 | `0.000`～`566.500` 秒（動画先頭がキックオフ） |
| 元動画 | H.264、1280×720、30 FPS、16,995 フレーム、AAC 音声 |
| 推論用 proxy | H.264、1280×720、25 FPS、14,163 フレーム、音声なし |
| proxy 作成 | 全区間、無クロップ、無リサイズ、FFmpeg `fps=25` |
| 時刻対応 | proxy のフレーム番号 `i` を `i / 25.0` 秒として元動画へ対応 |

元動画と推論用 proxy は SHA-256 で固定・検証済みです。推論は proxy 上で行い、最終可視化は元の 30 FPS・音声付き動画に対して行っています。

## 2. 使用モデル

| 項目 | 内容 |
| --- | --- |
| 公開実装 | `https://github.com/lRomul/ball-action-spotting` |
| 固定ソース commit | `9c471531c62b51bd0cfe6170b74d035da44c88ed` |
| 実験名 | `ball_finetune_long_004` |
| クラス | `PASS`、`DRIVE` |
| モデル | `multidim_stacker` |
| 2D backbone | `tf_efficientnetv2_b0` |
| 時系列部 | 3D blocks × 4、33 フレーム入力、frame step 2 |
| 入力処理 | grayscale、`pad_normalize(size=(1280, 736))`、上下を黒埋め |
| 集成 | 公式 7 fold（fold 0～6）のフレーム単位算術平均 |
| TTA | horizontal flip 有効 |
| 推論精度 | AMP 有効 |

7 個の公式 checkpoint はすべて SHA-256 を記録し、実際に同一設定で読み込めることを確認しています。33 フレームを 2 フレーム間隔で参照するため、最初から最後までの時間コンテキストは約 2.56 秒です。

## 3. 推論方法・実行環境

1. 25 FPS proxy を OpenCV/FFmpeg backend で連続デコードします。
2. 各フレームを grayscale に変換して GPU に渡します。
3. 上流実装の `MultiDimStackerPredictor` が 33 フレームの時系列バッファを構成します。
4. 7 fold それぞれで horizontal flip TTA を有効にして推論します。
5. 各 fold の 2 クラスの生スコアを保持し、その算術平均を `ensemble_scores` として保存します。
6. GPU 推論後に CPU 上で時系列後処理を行い、イベント候補を抽出します。閾値変更時に GPU 推論をやり直す必要はありません。

| 項目 | 実績 |
| --- | --- |
| 実行基盤 | `chiron`、Slurm job `6835526` |
| GPU | NVIDIA RTX A6000 × 1 |
| Python / PyTorch | Python 3.10.21 / PyTorch 2.0.1、CUDA 11.8 環境 |
| 推論範囲 | 要求範囲 `0.000`～`566.500` 秒 |
| 有効予測範囲 | `1.320`～`565.160` 秒（端部は完全な時間コンテキストがないため除外） |
| 有効予測数 | 14,097 フレーム × 7 fold × 2 クラス |
| 実行時間 | 1,742.97 秒（約 29 分 3 秒） |
| 出力 | 各 fold の生スコア `(14097, 7, 2)`、平均スコア `(14097, 2)` |

同一条件の 0～90 秒 smoke inference を 2 回実行し、全配列が要素単位で一致することを確認しています。

## 4. 時系列後処理

各クラスの `ensemble_scores` に対して独立に以下を適用しています。

| パラメータ | 値 | 25 FPS での意味 |
| --- | --- | --- |
| Gaussian smoothing | `sigma=3.0` | σ 約 0.12 秒 |
| peak 最小高さ | `0.2` | 平滑化後スコアの候補閾値 |
| peak 最小距離 | `15` フレーム | 同一クラス内で 0.6 秒 |

イベントの `confidence` は平滑化後ピークの高さです。学習済み確率校正は行っていないため、値を正解確率として解釈しません。

## 5. 現在の推定結果

| クラス | 候補数 | 最小 | 中央値 | 平均 | 最大 | 0.5 以上 | 0.7 以上 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Pass | 34 | 0.207 | 0.314 | 0.393 | 0.895 | 8 | 4 |
| Drive | 24 | 0.201 | 0.279 | 0.363 | 0.834 | 5 | 1 |
| 合計 | 58 | － | － | － | － | 13 | 5 |

高スコア上位の例：

| 時刻 | クラス | confidence |
| --- | --- | ---: |
| `00:04:26.360` | Pass | 0.895 |
| `00:07:26.920` | Drive | 0.834 |
| `00:01:23.040` | Pass | 0.818 |
| `00:09:06.320` | Pass | 0.715 |
| `00:07:25.800` | Pass | 0.706 |

confidence の分布は、`0.2～0.3` が 28 件、`0.3～0.4` が 9 件、`0.4～0.5` が 8 件、`0.5 以上`が 13 件です。低い閾値を採用しているため、現在の 58 件は高信頼イベントだけではなく、主観レビュー用の広めの候補集合です。

## 6. 共有可能な成果物

| 成果物 | 内容 |
| --- | --- |
| `ball_action_spotting_with_global_ bar.mp4` | 566.5 秒の全体可視化。イベント情報、ソース時刻、全体タイムライン付き |
| `event_highlights.mp4` | 58 件を順番に収録。各候補について前 3 秒＋後 4 秒、合計 406 秒 |
| `events.csv` / `events.json` | event ID、時刻、クラス、confidence |
| `scores.npz` | 7 fold の生スコアと平均スコア。閾値変更用 |
| `manifest.json` | 入力、モデル、checkpoint hash、環境、実行時間、出力形状 |

ローカル上の正式可視化：

- `outputs/20260902_151709_978ded7_poc-video-global-timeline-2px/ball_action_spotting_with_global_ bar.mp4`
- `outputs/20260902_151709_978ded7_poc-video-global-timeline-2px/event_highlights.mp4`
- `artifacts/inference/full_6835526/events.csv`
- `artifacts/inference/full_6835526/events.json`
- `artifacts/inference/full_6835526/scores.npz`

コード・設定リポジトリ：`https://github.com/panyao330501/Ball_action_spotting.git`

## 7. 現時点の制約

- GT がないため、accuracy、precision、recall、mAP は算出していません。
- 58 件はモデル候補であり、人手による正誤・可視性判定はまだ完了していません。
- `events.json` の初期 `visibility=VISIBLE` は export 時の仮値であり、人手確認済みラベルではありません。
- IKOMA 動画は低解像度の単一広角カメラで、ボールが小さく、カメラ追従の遅れや画面外イベントがあります。SoccerNet の放送映像との domain gap が想定されます。
- 画面外の行動は入力から観測できないため、自動的に false negative とは扱いません。
- `Drive` と `Reception (Drive)` の意味には解釈上の曖昧さがあり、レビュー前に定義を共有する必要があります。
- 現在の threshold は上流設定に基づく PoC 初期値であり、IKOMA 動画に最適化された値ではありません。

## 8. 関連する再現情報

- モデル・checkpoint 記録：`docs/model_sources/lromul_ball_action_2023.md`
- 入力・時間契約：`configs/poc_video.yaml`
- 推論マニフェスト：`artifacts/inference/full_6835526/manifest.json`
- 後処理マニフェスト：`artifacts/inference/full_6835526/postprocess_manifest.json`
- 推論入口：`scripts/run_custom_inference.py`
- 後処理入口：`scripts/postprocess_scores.py`
