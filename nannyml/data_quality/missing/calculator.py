#  Author:   Niels Nuyttens  <niels@nannyml.com>
#  Author:   Nikolaos Perrakis  <nikos@nannyml.com>
#
#  License: Apache Software License 2.0

"""Drift calculator using Reconstruction Error as a measure of drift."""

from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd
from pandas import MultiIndex

from nannyml.base import AbstractCalculator, _list_missing
from nannyml.chunk import Chunker
from nannyml.data_quality.base import _add_alert_flag
from nannyml.exceptions import InvalidArgumentsException
from nannyml.sampling_error import SAMPLING_ERROR_RANGE
from nannyml.thresholds import StandardDeviationThreshold, Threshold, calculate_threshold_values
from nannyml.usage_logging import UsageEvent, log_usage

from .result import Result

"""
Missing Values Data Quality Module.
"""


class MissingValuesCalculator(AbstractCalculator):
    """MissingValuesCalculator implementation using missing value rate as a measure of data quality."""

    def __init__(
        self,
        column_names: Union[str, List[str]],
        normalize: bool = True,
        timestamp_column_name: Optional[str] = None,
        chunk_size: Optional[int] = None,
        chunk_number: Optional[int] = None,
        chunk_period: Optional[str] = None,
        chunker: Optional[Chunker] = None,
        threshold: Threshold = StandardDeviationThreshold(),
    ):
        """Creates a new MissingValuesCalculator instance.

        Parameters
        ----------
        column_names: Union[str, List[str]]
            A string or list containing the names of features in the provided data set.
            Missing Values will be calculated for each entry in this list.
        normalize: bool, default=True
            Whether to provide the missing value ratio (True) or the absolute number of missing values (False).
        timestamp_column_name: str
            The name of the column containing the timestamp of the model prediction.
        chunk_size: int
            Splits the data into chunks containing `chunks_size` observations.
            Only one of `chunk_size`, `chunk_number` or `chunk_period` should be given.
        chunk_number: int
            Splits the data into `chunk_number` pieces.
            Only one of `chunk_size`, `chunk_number` or `chunk_period` should be given.
        chunk_period: str
            Splits the data according to the given period.
            Only one of `chunk_size`, `chunk_number` or `chunk_period` should be given.
        chunker : Chunker
            The `Chunker` used to split the data sets into a lists of chunks.


        Examples
        --------
        >>> import nannyml as nml
        >>> reference, analysis, _ = nml.load_synthetic_car_price_dataset()
        >>> column_names = [col for col in reference.columns if col not in ['timestamp', 'y_pred', 'y_true']]
        >>> calc = nml.MissingValuesCalculator(
        ...     column_names=column_names,
        ...     timestamp_column_name='timestamp',
        ... ).fit(reference)
        >>> res = calc.calculate(analysis)
        >>> for column_name in res.column_names:
        ...     res = res.filter(period='analysis', column_name=column_name).plot().show()
        """
        super(MissingValuesCalculator, self).__init__(
            chunk_size, chunk_number, chunk_period, chunker, timestamp_column_name
        )
        if isinstance(column_names, str):
            self.column_names = [column_names]
        elif isinstance(column_names, list):
            for el in column_names:
                if not isinstance(el, str):
                    raise InvalidArgumentsException(
                        f"column_names elements should be either a column name string or a list of strings, found\n{el}"
                    )
            self.column_names = column_names
        else:
            raise InvalidArgumentsException(
                "column_names should be either a column name string or a list of columns names strings, "
                "found\n{column_names}"
            )
        self.result: Optional[Result] = None
        self._sampling_error_components: Dict[str, float] = {column_name: 0 for column_name in self.column_names}
        # threshold strategy is the same across all columns
        self.threshold = threshold
        self._upper_alert_thresholds: Dict[str, Optional[float]] = {column_name: 0 for column_name in self.column_names}
        self._lower_alert_thresholds: Dict[str, Optional[float]] = {column_name: 0 for column_name in self.column_names}

        self.lower_threshold_value_limit: float = 0
        self.upper_threshold_value_limit: float
        self.normalize = normalize
        if self.normalize:
            self.data_quality_metric = 'missing_values_rate'
            self.upper_threshold_value_limit = 1
        else:
            self.data_quality_metric = 'missing_values_count'
            self.upper_threshold_value_limit = np.nan

    def _calculate_missing_value_stats(self, data: pd.Series):
        count_tot = data.shape[0]
        count_nan = data.isnull().sum()
        if self.normalize:
            count_nan = count_nan / count_tot
        return count_nan, count_tot

    @log_usage(UsageEvent.DQ_CALC_MISSING_VALUES_FIT, metadata_from_self=['normalize'])
    def _fit(self, reference_data: pd.DataFrame, *args, **kwargs):
        """Fits the drift calculator to a set of reference data."""
        if reference_data.empty:
            raise InvalidArgumentsException('data contains no rows. Please provide a valid data set.')

        _list_missing(self.column_names, reference_data)

        for col in self.column_names:
            count_nan, count_tot = self._calculate_missing_value_stats(reference_data[col])
            self._sampling_error_components[col] = count_nan if self.normalize else count_nan / count_tot

        for column in self.column_names:
            reference_chunk_results = np.asarray(
                [
                    self._calculate_missing_value_stats(chunk.data[column])[0]
                    for chunk in self.chunker.split(reference_data)
                ]
            )
            self._lower_alert_thresholds[column], self._upper_alert_thresholds[column] = calculate_threshold_values(
                threshold=self.threshold,
                data=reference_chunk_results,
                lower_threshold_value_limit=self.lower_threshold_value_limit,
                upper_threshold_value_limit=self.upper_threshold_value_limit,
                logger=self._logger,
                metric_name=self.data_quality_metric,
                override_using_none=True,
            )

        self.result = self._calculate(data=reference_data)
        self.result.data[('chunk', 'period')] = 'reference'

        return self

    @log_usage(UsageEvent.DQ_CALC_MISSING_VALUES_RUN, metadata_from_self=['normalize'])
    def _calculate(self, data: pd.DataFrame, *args, **kwargs) -> Result:
        """Calculates methods for both categorical and continuous columns."""
        if data.empty:
            raise InvalidArgumentsException('data contains no rows. Please provide a valid data set.')

        _list_missing(self.column_names, data)

        chunks = self.chunker.split(data)

        rows = []
        for chunk in chunks:
            row = {
                'key': chunk.key,
                'chunk_index': chunk.chunk_index,
                'start_index': chunk.start_index,
                'end_index': chunk.end_index,
                'start_datetime': chunk.start_datetime,
                'end_datetime': chunk.end_datetime,
                'period': 'analysis',
            }

            for column_name in self.column_names:
                for k, v in self._calculate_for_column(chunk.data, column_name).items():
                    row[f'{column_name}_{k}'] = v

            rows.append(row)

        result_index = _create_multilevel_index(
            column_names=self.column_names,
        )
        res = pd.DataFrame(rows)
        res.columns = result_index
        res = res.reset_index(drop=True)

        if self.result is None:
            self.result = Result(
                results_data=res,
                column_names=self.column_names,
                data_quality_metric=self.data_quality_metric,
                timestamp_column_name=self.timestamp_column_name,
                chunker=self.chunker,
            )
        else:
            # TODO: review subclassing setup => superclass + '_filter' is screwing up typing.
            #       Dropping the intermediate '_filter' and directly returning the correct 'Result' class works OK
            #       but this causes us to lose the "common behavior" in the top level 'filter' method when overriding.
            #       Applicable here but to many of the base classes as well (e.g. fitting and calculating)
            self.result = self.result.filter(period='reference')
            self.result.data = pd.concat([self.result.data, res]).reset_index(drop=True)

        return self.result

    def _calculate_for_column(self, data: pd.DataFrame, column_name: str) -> Dict[str, Any]:
        result = {}
        value, tot = self._calculate_missing_value_stats(data[column_name])
        result['value'] = value
        serr = np.sqrt(
            self._sampling_error_components[column_name] * (1 - self._sampling_error_components[column_name])
        )
        if self.normalize:
            result['sampling_error'] = serr / np.sqrt(tot)
        else:
            result['sampling_error'] = serr * np.sqrt(tot)

        result['upper_confidence_boundary'] = result['value'] + SAMPLING_ERROR_RANGE * result['sampling_error']
        result['lower_confidence_boundary'] = result['value'] - SAMPLING_ERROR_RANGE * result['sampling_error']

        result['upper_threshold'] = self._upper_alert_thresholds[column_name]
        result['lower_threshold'] = self._lower_alert_thresholds[column_name]
        result['alert'] = _add_alert_flag(result)
        return result


def _create_multilevel_index(
    column_names,
):
    chunk_column_names = ['key', 'chunk_index', 'start_index', 'end_index', 'start_date', 'end_date', 'period']
    chunk_tuples = [('chunk', chunk_column_name) for chunk_column_name in chunk_column_names]
    column_tuples = [
        (column_name, el)
        for column_name in column_names
        for el in [
            'value',
            'sampling_error',
            'upper_confidence_boundary',
            'lower_confidence_boundary',
            'upper_threshold',
            'lower_threshold',
            'alert',
        ]
    ]
    tuples = chunk_tuples + column_tuples
    return MultiIndex.from_tuples(tuples)
