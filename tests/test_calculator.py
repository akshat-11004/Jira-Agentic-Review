from calculator import add


def test_positive_numbers():
    assert add(2, 3) == 5


def test_negative_numbers():
    assert add(-2, 3) == 1


def test_zero():
    assert add(0, 0) == 0
