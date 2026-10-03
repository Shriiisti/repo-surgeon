from pytest import approx

from orders import order_total
from pricing import add_tax, apply_discount


def test_discount_ten_percent():
    assert apply_discount(200, 10) == approx(180)


def test_tax():
    assert add_tax(100, 0.08) == approx(108)


def test_single_item_no_extras():
    assert order_total([(100, 1)], 0, 0) == approx(100)


def test_quantity_is_counted():
    assert order_total([(10, 2), (5, 1)], 0, 0) == approx(25)


def test_full_order():
    assert order_total([(10, 2), (5, 1)], 10, 0.1) == approx(24.75)