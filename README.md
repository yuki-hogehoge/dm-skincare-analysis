# dm-skincare-analysis

dm.de の Serum & Kur カテゴリ(スキンケア美容液)172製品を対象にした統計分析リポジトリです。
価格・rating・成分データをもとに、いくつかの仮説を検証していきます。

## 関連リポジトリ

このプロジェクトは3つのリポジトリに分かれています。

| リポジトリ | 役割 |
|---|---|
| [dm-skincare-manual-pilot](https://github.com/yuki-hogehoge/dm-skincare-manual-pilot) | 最初の予備調査(手動アノテーション30件) |
| [dm-skincare-data-pipeline](https://github.com/yuki-hogehoge/dm-skincare-data-pipeline) | データ自動収集パイプライン(172件、本リポジトリが使うデータの出どころ) |
| **dm-skincare-analysis(本リポジトリ)** | 172件データを使った統計分析一式 |

## 分析一覧

| | 問い | 状態 | 結論(一言) | Notebook | 記事 |
|---|---|---|---|---|---|
| A | 高価格帯ほど有効成分を成分表の上位に配合しているか | ✅ 完了 | 9成分いずれも支持されず | [analysis_A/](./analysis_A_ingredient_rank/analysis_A_ingredient_rank_vs_price.ipynb) | [Zenn](https://zenn.dev/yuki_hogehoge/articles/dm_serum_analysis_ingredient_rank) |
| B | 香料・アルコール系溶媒の有無とratingの関係 | 🔜 計画中 | — | — | — |
| C | PB(自社ブランド)とNBの成分配合順位比較 | 🔜 計画中 | — | — | — |
| D | 成分数と価格の関係 | 🟡 一部A内で先取り済み | 弱い正の相関(rho=0.34) | Aの Step 7 参照 | — |
| concern | 商品説明文からの訴求内容の自動抽出 | 🔜 計画中 | — | — | — |

各分析の詳細は、それぞれのサブディレクトリのREADME、またはNotebook内の解説を参照してください。
本READMEでは、最初に完了した**分析A**の詳細のみ以下に記載します。

## リポジトリ構成

```
.
├── README.md
├── requirements.txt
├── common/
│   └── stats_utils.py                # boot_spearman, cluster_boot, partial_spearman など共通関数
├── analysis_A_ingredient_rank/
│   ├── analysis_A_ingredient_rank_vs_price.ipynb
│   └── figures/
│       ├── fig2_glycerin.png
│       └── fig3_forest_all9.png
├── analysis_B_fragrance_rating/       # 準備中
├── analysis_C_private_label/          # 準備中
├── analysis_D_ingredient_count_price/ # 準備中
└── concern_extraction/                # 準備中
```

## 使ったデータ

`skincare_dataset_final.csv`(172行 × 49列)。[dm-skincare-data-pipeline](https://github.com/yuki-hogehoge/dm-skincare-data-pipeline)
で生成したものです。本リポジトリにはデータファイルを含めていないため、各Notebookを実行する場合は、
上記リポジトリの手順でデータを生成するか、CSVを各分析ディレクトリに配置してください。

## セットアップ

```bash
pip install -r requirements.txt
jupyter notebook
```

---

# 分析A: 成分の配合順位と価格の関係

dm.de の Serum & Kur カテゴリ171製品を対象に、
「高価格帯の商品ほど、有効成分を成分表の上位に配合しているか」を検証した分析です。

## 結論(先出し)

検証した9つの成分(ヒアルロン酸・ナイアシンアミド・ビタミンC・レチノール・パンテノール・
アラントイン・スクアラン・乳酸・サリチル酸系)のいずれでも、**「高価格帯ほど成分表の上位に
配合している」という仮説は支持されませんでした**。ブランド単位のクラスタ・ブートストラップで
95%信頼区間を計算した結果、9成分すべてで区間が0をまたいでいます。

分析の過程で、`順位 ÷ 総成分数` という正規化指標(`rank_norm`)が、成分数そのものと価格の
相関の影響を受けて見かけの相関を作り出す、という方法論上の落とし穴も発見しました。

詳細は [Zenn記事](https://zenn.dev/yuki_hogehoge/articles/dm_serum_analysis_ingredient_rank) および Notebook 本体を参照してください。

## 分析Aのファイル

```
analysis_A_ingredient_rank/
├── analysis_A_ingredient_rank_vs_price.ipynb   # 分析本体(Jupyter Notebook)
└── figures/
    ├── fig2_glycerin.png     # グリセリンの見かけの相関(交絡の可視化)
    └── fig3_forest_all9.png  # フォレストプロット(9成分の結論)
```

> `fig1_scatter_all.png`(散布図)は、実データがないと再生成できないため、本リポジトリには
> 含めていません。Notebookの Step 5 を実行すると同じファイル名で生成されるので、
> ご自身の実行結果を `figures/fig1_scatter_all.png` として追加してください。

## 実行方法

```bash
pip install -r requirements.txt
cd analysis_A_ingredient_rank
jupyter notebook analysis_A_ingredient_rank_vs_price.ipynb
```

`skincare_dataset_final.csv` を `analysis_A_ingredient_rank/` に置いた状態で、
上から順にセルを実行すれば再現できる構成になっています。

## 分析の流れ

| Step | 内容 |
|---|---|
| 1 | データ読み込みと健全性チェック |
| 2 | 分析対象外データの特定(成分混在) |
| 3 | 使い切り品(アンプル・カプセル等)の判定 |
| 4 | 成分リストを9成分+グリセリンに拡張する(頻度分析・バグ修正) |
| 5 | 散布図で関係を目で見る |
| 6 | Spearman相関とブートストラップ信頼区間 |
| 7 | 「成分数」という交絡変数(glycerinの謎) |
| 8 | 偏相関による頑健性チェック |
| 9 | ブランド構造の確認 |
| 10 | ブランド単位のクラスタ・ブートストラップ |
| 11 | まとめの図(フォレストプロット) |
| 12 | 総括と限界 |

## 使った統計手法

- **Spearman順位相関係数**: 価格と成分の配合順位(正規化順位/絶対順位)の関係を、
  外れ値に強い形で評価
- **ブートストラップ信頼区間**(商品単位・ブランドクラスタ単位): 点推定だけでなく、
  推定のばらつきの幅を評価
- **偏相関**: 成分数という交絡変数の影響を統制した頑健性チェック

これらの関数は `common/stats_utils.py` に切り出しており、B以降の分析でも再利用する想定です。

## 分析Aの限界

- 価格は容量(ml)を考慮していません(100mlあたり価格ではない)
- 成分の順位は濃度の完全な代理指標ではありません(EU規則上、濃度1%未満の成分は順不同)
- 対象はdm.deの、ある時点の171商品であり、市場全体への一般化はできません
- 偏相関は成分数の影響を線形回帰で除いた簡易版です

## ライセンス

このリポジトリのコード・分析内容のライセンスは、公開時に別途ご記載ください
(例: MIT License)。dm.deから収集したデータそのものの再配布については、
利用規約・robots.txtの範囲を踏まえてご判断ください。
