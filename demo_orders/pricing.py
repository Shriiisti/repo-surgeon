def apply_discount(amount, percent):
    """Reduce an amount by a percentage. For example, 10 means 10% off."""
    return amount - amount * percent / 10


def add_tax(amount, rate):
    """Add tax to an amount. The rate is a fraction: 0.08 means 8%."""
    return amount * (1 + rate)