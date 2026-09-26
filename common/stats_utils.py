"""
dm-skincare-analysis で使う共通統計関数。

分析Aで実装したものを切り出しています。B以降の分析でも、
同じ考え方(Spearman相関、ブートストラップ信頼区間、成分数を統制した偏相関、
ブランド単位のクラスタ・ブートストラップ)を再利用できます。

使い方:
    from common.stats_utils import boot_spearman, partial_spearman, cluster_boot
"""

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


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
