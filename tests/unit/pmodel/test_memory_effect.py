"""Tests the application of the memory effect in the subdaily model."""

from contextlib import nullcontext as does_not_raise

import numpy as np
import pytest


@pytest.mark.parametrize(
    argnames="inputs",
    argvalues=[
        pytest.param(np.arange(0, 10), id="1D"),
        pytest.param(
            np.column_stack([np.arange(0, 10)] * 4) + np.arange(4),
            id="2D",
        ),
        pytest.param(
            np.dstack([np.column_stack([np.arange(0, 10)] * 4)] * 4)
            + np.arange(16).reshape(4, 4),
            id="3D",
        ),
    ],
)
@pytest.mark.parametrize(argnames="alpha", argvalues=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0))
def test_memory_effect(inputs, alpha):
    """Test the memory effect.

    This uses matrix maths to calculate expected by calculating the coefficients of the
    recursive equation. Does not scale well, but a useful parallel implementation for
    testing.
    """
    from pyrealm.pmodel import memory_effect

    result = memory_effect(inputs, alpha=alpha)

    # Calculate the coefficients for product sum of the elements along the time axis
    one_minus_alpha = 1 - alpha
    n = len(inputs)
    ident = np.identity(n)
    nan = np.ones_like(ident) * np.nan
    rw, cl = np.indices(ident.shape)
    rwcl = rw - cl
    one_minus_alpha_exp = np.where(rwcl >= 0, rwcl, nan)
    alpha_exp = np.where(rwcl >= 0, 1, nan)
    alpha_exp[:, 0] = 0

    coef = one_minus_alpha**one_minus_alpha_exp * alpha**alpha_exp
    coef = np.where(np.triu(coef, k=1), 0, coef)

    # Calculate the tensor dot product of the coefficients and the inputs along the
    # first (time) axis.
    expected = np.tensordot(coef, inputs, axes=1)

    assert np.allclose(result, expected)


@pytest.mark.parametrize(
    argnames="inputs,handle_nan,context_manager,expected",
    argvalues=[
        pytest.param(
            np.arange(1, 8),
            False,
            does_not_raise(),
            np.array([1.0, 1.1, 1.29, 1.561, 1.9049, 2.31441, 2.782969]),
            id="no missing data",
        ),
        pytest.param(
            np.array([1, 2, 3, 4, np.nan, np.nan, 7]),
            False,
            pytest.raises(ValueError),
            None,
            id="unhandled missing data",
        ),
        pytest.param(
            np.array([1, 2, 3, 4, np.nan, np.nan, 7]),
            True,
            does_not_raise(),
            np.array([1.0, 1.1, 1.29, 1.561, 1.561, 1.561, 2.1049]),
            id="handled missing data",
        ),
    ],
)
@pytest.mark.parametrize(argnames="ndim", argvalues=(1, 2, 3))
def test_memory_effect_inputs(inputs, handle_nan, context_manager, expected, ndim):
    """Simple testing of nan handling and predictions across multiple dimensions."""
    from pyrealm.pmodel.subdaily import memory_effect

    if ndim == 2:
        inputs = np.broadcast_to(inputs[:, np.newaxis], (7, 2))
        if expected is not None:
            expected = np.broadcast_to(expected[:, np.newaxis], (7, 2))

    if ndim == 3:
        inputs = np.broadcast_to(inputs[:, np.newaxis, np.newaxis], (7, 2, 2))
        if expected is not None:
            expected = np.broadcast_to(expected[:, np.newaxis, np.newaxis], (7, 2, 2))

    with context_manager:
        results = memory_effect(inputs, handle_nan=handle_nan, alpha=0.1)

        assert np.allclose(results, expected)
