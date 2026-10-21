import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from sod import config  # noqa: E402
from sod.viz import theme  # noqa: E402


def test_palettes_have_distinct_group_colours():
    for p in theme.PALETTES.values():
        cols = [p.so, p.so_language, p.tech, p.donor, p.counterfactual]
        assert len(set(cols)) == len(cols)


def test_use_switches_and_restores(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "FIGURE_DIR", tmp_path)
    with theme.use("dark") as p:
        assert theme.palette() is theme.DARK
        assert plt.rcParams["figure.facecolor"].lower() == p.surface.lower()
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1], color=theme.group_color("treated"))
        paths = theme.save(fig, "t")
    assert theme.palette() is theme.LIGHT
    assert [x.name for x in paths] == ["t_dark.png", "t_dark.svg"]
    assert all(x.exists() for x in paths)
