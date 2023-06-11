# Author:   Niels Nuyttens  <niels@nannyml.com>
#
# License: Apache Software License 2.0

# TODO wording

"""The NannyML library, helping you maintain model performance since 2020.

Use the library to:
- Calculate drift on model inputs, outputs and ground truth
- Calculate performance metrics for your model
- Estimate model performance metrics in the absence of ground truth
"""

__author__ = """Niels Nuyttens"""
__email__ = 'niels@nannyml.com'

# PEP0440 compatible formatted version, see:
# https://www.python.org/dev/peps/pep-0440/
#
# Generic release markers:
#   X.Y.0   # For first release after an increment in Y
#   X.Y.Z   # For bugfix releases
#
# Admissible pre-release markers:
#   X.Y.ZaN   # Alpha release
#   X.Y.ZbN   # Beta release
#   X.Y.ZrcN  # Release Candidate
#   X.Y.Z     # Final release
#
# Dev branch marker is: 'X.Y.dev' or 'X.Y.devN' where N is an integer.
# 'X.Y.dev0' is the canonical version of 'X.Y.dev'
#
__version__ = '0.8.6'

import logging

from dotenv import load_dotenv

from .calibration import Calibrator, IsotonicCalibrator, needs_calibration
from .chunk import Chunk, Chunker, CountBasedChunker, DefaultChunker, PeriodBasedChunker, SizeBasedChunker
from .data_quality import MissingValuesCalculator, UnseenValuesCalculator
from .datasets import (
    load_modified_california_housing_dataset,
    load_synthetic_binary_classification_dataset,
    load_synthetic_car_loan_data_quality_dataset,
    load_synthetic_car_loan_dataset,
    load_synthetic_car_price_dataset,
    load_synthetic_multiclass_classification_dataset,
    load_titanic_dataset,
    load_us_census_ma_employment_data,
)
from .drift import AlertCountRanker, CorrelationRanker, DataReconstructionDriftCalculator, UnivariateDriftCalculator
from .exceptions import ChunkerException, InvalidArgumentsException, MissingMetadataException
from .io import DatabaseWriter, PickleFileWriter, RawFilesWriter
from .performance_calculation import PerformanceCalculator
from .performance_estimation import CBPE, DLE
from .usage_logging import UsageEvent, disable_usage_logging, enable_usage_logging, log_usage

# read any .env files to import environment variables
load_dotenv()

logging.getLogger(__name__).addHandler(logging.NullHandler())
