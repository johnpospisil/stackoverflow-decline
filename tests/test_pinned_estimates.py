"""P28: pin the headline estimates, so a code or data change can't move them silently.

Reads the model summaries in <SOD_REPORT_DIR>/qa. Real run: the numbers reported in the
findings (P15-P24); sample run (make all SAMPLE=1): the synthetic dump's values. A failure
means a result changed: either a bug, or a deliberate change that must be explained (and,
for the pre-registered tests, logged in PREREGISTRATION.md) before the pin is updated.

Tolerances are absolute, in the units shown (mostly percentage points). They allow for
platform differences in optimisers and MCMC, not for real changes.
"""

from __future__ import annotations

import json
from functools import cache

import pytest

from sod import config

QA = config.REPORT_DIR / "qa"


@cache
def summary(name: str) -> dict:
    path = QA / f"{name}_summary.json"
    if not path.exists():
        pytest.skip(f"{path.name} not built")
    return json.loads(path.read_text())


def get(name: str, path: str):
    out = summary(name)
    for key in path.split("/"):
        out = out[int(key)] if isinstance(out, list) else out[key]
    return out


# (summary, key path, real value, sample value, tolerance)
PINS = [
    # H1: synthetic control (P17), the primary pre-registered estimate
    ("synth", "att/all_post/att_pct", -72.31, -74.67, 1.0),
    ("synth", "att_interval_readings_pct/monthly_average/0", -75.70, -77.98, 1.0),
    ("synth", "att_interval_readings_pct/monthly_average/1", -68.47, -70.85, 1.0),
    ("synth", "placebo_space/p_value", 0.0625, 0.0625, 1e-9),
    ("synth", "months_interval_excludes_zero", 42, 43, 1),
    # supporting estimates (P15, P16) and robustness range (P18)
    ("its", "fits/preregistered/windows/all_post/mean_gap_pct", -83.39, -77.17, 1.0),
    ("its", "fits/post_covid/windows/all_post/mean_gap_pct", -79.26, -76.28, 1.0),
    ("forecast", "models/ets/gaps/all_post/mean_gap_pct", -82.72, -79.94, 1.5),
    ("forecast", "models/prophet/gaps/all_post/mean_gap_pct", -81.08, -78.02, 2.0),
    ("robustness", "att_range_pct/0", -83.39, -82.01, 1.5),
    ("robustness", "att_range_pct/1", -59.64, -62.93, 1.5),
    # H2 (P19-P20): MCMC, so wider
    ("thin_data", "a_age/gamma_z_log_age/median", 0.412, -0.011, 0.04),
    ("thin_data", "b_new_tags/median_gap_pct", -49.48, -52.54, 2.0),
    ("thin_data", "b_new_tags/top300_median_pct", -85.49, -77.43, 2.0),
    # H3 (P21)
    ("question_mix", "h3_n_as_predicted", 2, 1, 0),
    # H4 (P22): 12-month return of new askers
    ("newcomers", "b_km/2019-2021/365/p", 0.4398, 0.4694, 0.005),
    ("newcomers", "b_km/2023-2026/365/p", 0.2852, 0.4013, 0.005),
    ("newcomers", "a_synth/log_share_first_time/att_pct", 18.29, 1.14, 1.5),
    # H5 (P23): share of 2019-21 core answerers still active 2 and 3 years on
    ("answerers", "h5_test/distance_2/treated_share", 0.6272, 0.5882, 0.005),
    ("answerers", "h5_test/distance_3/treated_share", 0.4826, 0.3529, 0.005),
    # E1 (P24): answered within 24 hours
    (
        "responsiveness",
        "by_group_and_period/treated/rate_answered_24h/2019-2021",
        0.6744,
        0.7001,
        0.005,
    ),
    ("responsiveness", "by_group_and_period/treated/rate_answered_24h/2025", 0.5469, 0.5041, 0.005),
    # P29: questions fewer than expected (synthetic control, counts) and the H5 Holm p-value
    ("validation", "missing_questions/windows/all_post/missing", 1_574_501, 20_357, 20_000),
    ("validation", "multiplicity/family_p/H5", 0.0237, 0.4295, 0.003),
]

# Pre-registered verdicts: these must not flip without a logged deviation.
VERDICTS = [
    ("synth", "h1_supported_by_reading/monthly_average", True, True),
    ("synth", "h1_supported_by_reading/constant_effect", False, False),
    ("thin_data", "h2_supported", False, False),
    ("question_mix", "h3_supported", False, False),
    ("newcomers", "h4_supported", False, False),
    ("answerers", "h5_supported", True, False),  # unadjusted rule (P23)
    # P29: Holm across H2-H5 (pre-registration section 6): none survives
    *[
        ("validation", f"multiplicity/holm/{h}/reject", False, False)
        for h in ("H2", "H3", "H4", "H5")
    ],
]


def _id(p):
    return f"{p[0]}:{p[1]}"


@pytest.mark.parametrize("pin", PINS, ids=_id)
def test_pinned_value(pin):
    name, path, real, sample, tol = pin
    expected = sample if config.SAMPLE else real
    assert get(name, path) == pytest.approx(expected, abs=tol)


@pytest.mark.parametrize("pin", VERDICTS, ids=_id)
def test_pinned_verdict(pin):
    name, path, real, sample = pin
    assert get(name, path) is (sample if config.SAMPLE else real)
