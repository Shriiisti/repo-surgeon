from pricing import add_tax, apply_discount


def order_total(items, discount_percent, tax_rate):
    """Work out the final price. Each item is a (price, quantity) pair."""
    subtotal = sum(price for price, quantity in items)
    discounted = apply_discount(subtotal, discount_percent)
    return add_tax(discounted, tax_rate)