"""Map/scorer goodness parity (issue #807).

The map's zone band tables (apps/web/lib/layers_p4_*.ts + zones807.ts)
must agree byte-for-byte with the scorer dims in this directory: the
map paints the same verdict the scorer scores. Each test below pins
one side of the parity — the TS constant is quoted in the comment so
a drift on either side fails loudly here.

Hermetic: pure table/function assertions, no network, no fixtures.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dims_soil_map import SOIL_BANDS
from dims_p4_noisemap import LDEN_BANDS, LDEN_LOUD, LNIGHT_BANDS, LNIGHT_LOUD, _band_score
from dims_p4_harbour import FUNCTION_BANDS, PLEASURE_BANDS
from dims_p4_kitsendus import BAN_SCORES, CONDITIONED_SCORES, _band_for_zone
from dims_p4_typical_delay import DELAY_BANDS, _band as _delay_band
from dims_p4_forestchange import _score_change
from dims_p4_eelis import (FLOOD_SCORE, KAITSE_SCORE, HABITAT_NEAR_SCORE,
                           FELLING_SCORE)
from dims_p4_seveso import DANGER_SCORES
from dims_p4_maavara_extract import (EXTRACTION_INSIDE, EXTRACTION_NEAR,
                                     EXPLORATION_WATCH)
from dims_p4_riigimaa import (FOREST_ASSURANCE, OTHER_ASSURANCE,
                              AUCTION_FLAG)
from dims_p4_maaparandus import (INSIDE_VORK_SCORE, KEHTETU_SCORE,
                                 EESVOOL_SCORE)
from dims_overturn_planktpr import USE_BANDS


def test_soil_bands_match_ts():
    # TS: SOIL_CLASS_SCORE in apps/web/lib/layers_p4_soil.ts
    assert SOIL_BANDS == {
        "saviliiv": 85, "liiv": 70, "liivsavi": 65, "leede": 55,
        "paepealne": 50, "savi": 40, "glei": 30, "turvas": 25,
    }


def test_noise_bands_match_ts():
    # TS: NOISE_LDEN_BANDS/NOISE_LNIGHT_BANDS + noiseScoreForArea
    assert LDEN_BANDS == ((45.0, 85), (55.0, 65), (65.0, 40))
    assert LDEN_LOUD == 20
    assert LNIGHT_BANDS == ((40.0, 85), (50.0, 65), (60.0, 40))
    assert LNIGHT_LOUD == 20
    assert _band_score(45.0, LDEN_BANDS, LDEN_LOUD) == 85
    assert _band_score(55.0, LDEN_BANDS, LDEN_LOUD) == 65
    assert _band_score(65.0, LDEN_BANDS, LDEN_LOUD) == 40
    assert _band_score(80.0, LDEN_BANDS, LDEN_LOUD) == 20


def test_harbour_bands_match_ts():
    # TS: HARBOUR_FUNCTION_BANDS + harbourPortBands/harbourCellScoreFor
    assert FUNCTION_BANDS == {
        1: ((500, 45), (1500, 65)),
        2: ((500, 70), (1500, 80)),
        3: ((500, 75), (1500, 85)),
    }
    assert PLEASURE_BANDS == ((50, 70), (10, 80), (1, 85))


def test_kpo_bands_match_ts():
    # TS: kpoScoreForZone keyword order + scores
    assert BAN_SCORES == {"ehituskeeld": 20, "ehituskeeluvöönd": 20,
                          "tagasilöök": 35}
    assert CONDITIONED_SCORES == {"tingimuslik": 50, "kooskõlastus": 50,
                                  "teavitus": 65, "kaitsevöönd": 50,
                                  "asjaõigus": 50}
    assert _band_for_zone({"voond": "Ehituskeeld"}) == 20
    assert _band_for_zone({"voond": "Tagasilöök 4 m"}) == 35
    assert _band_for_zone({"voond": "Tingimuslik ehitus"}) == 50
    assert _band_for_zone({"voond": "Teavitusega ala"}) == 65
    assert _band_for_zone({"voond": "müstiline vöönd"}) is None
    assert _band_for_zone({"voond": "x", "family": "muinsuskaitse"}) == 50


def test_delay_bands_match_ts():
    # TS: DELAY_BAND_SCORE via delayBandForFactor (free 75 … jammed 30)
    assert DELAY_BANDS == [(1.1, 75), (1.3, 60), (1.6, 45),
                           (float("inf"), 30)]
    assert _delay_band(1.0, DELAY_BANDS) == 75
    assert _delay_band(1.2, DELAY_BANDS) == 60
    assert _delay_band(1.5, DELAY_BANDS) == 45
    assert _delay_band(2.0, DELAY_BANDS) == 30


def test_forestchange_cores_match_ts():
    # TS: FOREST_CLASS_SCORE {3: 30, 2: 60, 1: 70} (membership cores;
    # the scorer's 55 near-halo is scorer-side only, documented).
    assert _score_change(2.0, 100.0) == 30
    assert _score_change(2.0, 1000.0) == 55
    assert _score_change(6.0, 100.0) == 60
    assert _score_change(15.0, 100.0) == 70


def test_eelis_scores_match_ts():
    # TS: EELIS_KIND_SCORE {kaitse 55, niit 55, raie 45} + FLOOD 35
    assert KAITSE_SCORE == 55
    assert HABITAT_NEAR_SCORE == 55
    assert FELLING_SCORE == 45
    assert FLOOD_SCORE == 35


def test_seveso_quarry_stateland_maaparandus_match_ts():
    # TS: SEVESO_DANGER_SCORE / QUARRY_CLASS_SCORE /
    # STATELAND_CLASS_SCORE / MAAPARANDUS_CLASS_SCORE
    assert DANGER_SCORES == {"toxic": 20, "heat": 35, "overpressure": 35,
                             "combustion": 50, "unknown": 30}
    assert EXTRACTION_INSIDE == 25
    assert EXTRACTION_NEAR == 45  # scorer-side near-band, no map class
    assert EXPLORATION_WATCH == 55
    assert OTHER_ASSURANCE == 60
    assert AUCTION_FLAG == 40
    assert FOREST_ASSURANCE == 70  # scorer-side, unobserved in harvest
    assert INSIDE_VORK_SCORE == 55
    assert KEHTETU_SCORE == 40
    assert EESVOOL_SCORE == 45


def test_planktpr_bands_match_ts():
    # TS: PLANKTPR_USE_BANDS (cap 80)
    assert USE_BANDS == {"residential": 80, "mixed": 60, "commercial": 35,
                         "restricted": 20}
