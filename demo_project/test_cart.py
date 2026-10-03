from pytest import approx

from cart import total


def test_no_discount():
    assert total([10, 20, 30], 0) == approx(60)


def test_ten_percent_off():
    assert total([100, 100], 0.1) == approx(180)


def test_half_price():
    assert total([10, 20, 30], 0.5) == approx(30)