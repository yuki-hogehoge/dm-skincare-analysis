"""
dm-skincare-analysis で使う共通統計関数。

分析Aで実装したものを切り出しています。B以降の分析でも、
同じ考え方(Spearman相関、ブートストラップ信頼区間、成分数を統制した偏相関、
ブランド単位のクラスタ・ブートストラップ)を再利用できます。

使い方:
    from common.stats_utils import boot_spearman, partial_spearman, cluster_boot

分析Bで追加:
    from common.stats_utils import auc_xy, make_auc_func, bayes_avg, run_test
"""

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, mannwhitneyu, rankdata


def boot_spearman(x, y, rng=None, n_boot=5000):
    """
    商品単位の復元抽出によるSpearman相関のブートストラップ95%信頼区間。

    Parameters
    ----------
    x, y : array-like
        相関を見たい2変数(例: 価格、成分の配合順位)。
    rng : numpy.random.Generator, optional
        乱数生成器。再現性を保つため、呼び出し側で
        `np.random.default_rng(42)` のように固定したものを渡すことを推奨。
        省略した場合は毎回シードなしで生成される(結果が実行のたびに変わる)。
    n_boot : int
        ブートストラップの反復回数。既定5000回。

    Returns
    -------
    (ci_low, ci_high) : tuple of float
        95%信頼区間の下限・上限。
    """
    if rng is None:
        rng = np.random.default_rng()
    x = np.asarray(x)
    y = np.asarray(y)
    n = len(x)
    rhos = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        r, _ = spearmanr(x[idx], y[idx])
        rhos.append(r)
    rhos = np.array(rhos)
    return tuple(np.nanpercentile(rhos, [2.5, 97.5]))


def partial_spearman(x, y, z):
    """
    zの影響を線形回帰で取り除いた、x・yの偏相関(簡易版)。

    xとyをそれぞれ順位に変換し、zの順位で線形回帰した残差同士の
    Pearson相関を返す。「順位のPearson相関=Spearman相関」という性質を
    利用した簡易的な偏Spearman相関。非線形な交絡関係までは除去できない点に注意。

    Parameters
    ----------
    x, y : array-like
        相関を見たい2変数。
    z : array-like
        統制したい交絡変数(例: ingredient_count)。

    Returns
    -------
    float
        偏相関係数。
    """
    rx = pd.Series(x).rank().values
    ry = pd.Series(y).rank().values
    rz = pd.Series(z).rank().values
    ex = rx - np.polyval(np.polyfit(rz, rx, 1), rz)
    ey = ry - np.polyval(np.polyfit(rz, ry, 1), rz)
    return np.corrcoef(ex, ey)[0, 1]


def cluster_boot(d, func, brand_col="brand", price_col="price_eur_clean", rng=None, n_boot=2000):
    """
    ブランドを単位にした復元抽出によるクラスタ・ブートストラップ95%信頼区間。

    同じブランドの商品は成分設計が似ている可能性が高く独立とみなせないため、
    商品単位ではなくブランド単位で選び直すことで、より保守的な(実態に近い)
    信頼区間を推定する。

    Parameters
    ----------
    d : pandas.DataFrame
        対象データ。brand_col・price_col列を含む必要がある。
    func : callable
        `func(dataframe)` の形で呼び出され、相関係数などの推定値(float)を返す関数。
        例: `lambda df: spearmanr(df["price_eur_clean"], df["hyaluronic_acid_rank_norm"])[0]`
    brand_col : str
        ブランド名の列名。既定 "brand"。
    price_col : str
        選び直した後に「価格の値がすべて同一で計算不能」なケースを弾くための
        チェックに使う列名。既定 "price_eur_clean"。
    rng : numpy.random.Generator, optional
        乱数生成器。再現性を保つため、呼び出し側で固定したものを渡すことを推奨。
    n_boot : int
        ブートストラップの反復回数。既定2000回(ブランド単位はデータの結合が
        発生し商品単位より重いため、商品単位より少なめにしている)。

    Returns
    -------
    (ci_low, ci_high) : tuple of float
        95%信頼区間の下限・上限。
    """
    if rng is None:
        rng = np.random.default_rng()
    groups = {b: g for b, g in d.groupby(brand_col)}
    brands = list(groups.keys())
    vals = []
    for _ in range(n_boot):
        chosen = rng.choice(brands, size=len(brands), replace=True)
        boot = pd.concat([groups[b] for b in chosen])
        if len(boot) < 5 or boot[price_col].nunique() < 2:
            continue
        try:
            vals.append(func(boot))
        except Exception:
            continue
    return tuple(np.nanpercentile(np.array(vals), [2.5, 97.5]))


# ---------------------------------------------------------------------------
# 分析Bで追加(2群比較・ベイズ平均)
# ---------------------------------------------------------------------------

def auc_xy(x, y):
    """
    共通言語効果量(AUC): xから1件、yから1件ランダムに選んだとき、
    xのほうが高い確率。同値は0.5件分として数える。

    Mann-Whitney U検定の U / (n1 * n2) と同じ値。順位の合計から計算するのは、
    scipyのバージョンによって U がどちらの群の値で返るかが違うのを避けるため。
    0.5なら差なし。目安(慣例)は 0.56 小 / 0.64 中 / 0.71 大。

    Parameters
    ----------
    x, y : array-like
        比較する2群の値(x = 「あり」群、y = 「なし」群 など)。

    Returns
    -------
    float
        0〜1のAUC。
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    ranks = rankdata(np.concatenate([x, y]))  # 全体での順位(同値は平均順位)
    n1, n2 = len(x), len(y)
    return (ranks[:n1].sum() - n1 * (n1 + 1) / 2) / (n1 * n2)


def make_auc_func(flag_col, value_col, min_group=3):
    """
    `cluster_boot` に渡すための関数を作る。

    cluster_boot は `func(dataframe) -> float` の形でしか呼べないので、
    比較する列名を内側に閉じ込めた関数を返す。

    Parameters
    ----------
    flag_col : str
        0/1のグループ列(1 = 「あり」群)。
    value_col : str
        比較する値の列。
    min_group : int
        選び直した結果どちらかの群がこの件数未満になったら NaN を返して捨てる。

    Returns
    -------
    callable
        `f(dataframe) -> float`(AUC、または群が小さすぎれば NaN)。
    """
    def f(dd):
        x = dd.loc[dd[flag_col] == 1, value_col]
        y = dd.loc[dd[flag_col] == 0, value_col]
        if len(x) < min_group or len(y) < min_group:
            return np.nan
        return auc_xy(x, y)
    return f


def bayes_avg(r, n, m, C):
    """
    ベイズ平均(縮小推定): (C*m + n*r) / (C + n)

    レビュー数nが少ない商品の評価rを、全体の代表値mに引き寄せる。
    Cは「mの評価が最初からC件付いている」とみなす仮想レビュー数(縮小の強さ)。

    注意: mを平均にするか中央値にするかで結果が変わる。ratingは天井効果で
    中央値 > 平均になりやすく、mを平均にすると、レビュー数の少ない普通の商品が
    実際より下に引かれ、rating_countとの人工的な正の相関ができることがある
    (分析Bで確認)。mの取り方は必ず感度チェックすること。
    """
    return (C * m + n * r) / (C + n)


def run_test(data, flag_col, value_col, label, brand_col="brand",
             n_boot=2000, seed=42):
    """
    Mann-Whitney U検定(両側)+ AUC + ブランド単位クラスタ・ブートストラップCI。

    Parameters
    ----------
    data : pandas.DataFrame
    flag_col : str
        0/1のグループ列(1 = 「あり」群)。
    value_col : str
        比較する値の列(例: ベイズ平均)。
    label : str
        結果表に出す比較の名前。
    brand_col : str
        クラスタ(ブランド)列。表記ゆれを統一した列を渡すこと
        (統一が不完全だとCIが実態より狭くなる)。
    n_boot, seed : int
        ブートストラップ回数と乱数シード(再現性のため固定)。

    Returns
    -------
    dict
        n、中央値、AUC、CI、p値を含む1行ぶんの結果。
    """
    x = data.loc[data[flag_col] == 1, value_col]
    y = data.loc[data[flag_col] == 0, value_col]
    p = mannwhitneyu(x, y, alternative="two-sided").pvalue
    rng = np.random.default_rng(seed)
    # price_col は cluster_boot の「全値同一を弾く」チェック用だが、AUCでは
    # make_auc_func 側の NaN ガードで足りるので、比較対象の列を渡して無害化する。
    lo, hi = cluster_boot(data, make_auc_func(flag_col, value_col),
                          brand_col=brand_col, price_col=value_col,
                          rng=rng, n_boot=n_boot)
    return {"比較": label, "指標": value_col,
            "n_あり": len(x), "n_なし": len(y),
            "median_あり": round(x.median(), 3), "median_なし": round(y.median(), 3),
            "AUC": round(auc_xy(x, y), 3),
            "CI_low": round(lo, 3), "CI_high": round(hi, 3), "p": round(p, 4)}
