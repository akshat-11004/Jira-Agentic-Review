# This is addition functionality
def add(a, b):
    return a + b

# This is subtraction functionality
def subtract(a, b):
    return a - b

def modulo(a, b):
    if b == 0:
        raise ZeroDivisionError(
            "Modulo by zero is not allowed"
        )

    return a % b