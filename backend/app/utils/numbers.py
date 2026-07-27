from decimal import Decimal, ROUND_HALF_UP

ONES = [
    "",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
    "Thirteen",
    "Fourteen",
    "Fifteen",
    "Sixteen",
    "Seventeen",
    "Eighteen",
    "Nineteen",
]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def two_digit_words(number: int) -> str:
    if number < 20:
        return ONES[number]
    return f"{TENS[number // 10]} {ONES[number % 10]}".strip()


def three_digit_words(number: int) -> str:
    hundred = number // 100
    rest = number % 100
    words = []
    if hundred:
        words.append(f"{ONES[hundred]} Hundred")
    if rest:
        words.append(two_digit_words(rest))
    return " ".join(words)


def amount_to_indian_words(amount: Decimal) -> str:
    rounded = Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    is_negative = rounded < 0
    rounded = abs(rounded)
    rupees = int(rounded)
    paise = int((rounded - rupees) * 100)

    parts = []
    crore, rupees = divmod(rupees, 10000000)
    lakh, rupees = divmod(rupees, 100000)
    thousand, rupees = divmod(rupees, 1000)
    hundred = rupees
    if crore:
        parts.append(f"{three_digit_words(crore)} Crore")
    if lakh:
        parts.append(f"{three_digit_words(lakh)} Lakh")
    if thousand:
        parts.append(f"{three_digit_words(thousand)} Thousand")
    if hundred:
        parts.append(three_digit_words(hundred))

    rupee_words = " ".join(parts) if parts else "Zero"
    words = f"{rupee_words} Rupees"
    if paise:
        words = f"{words} and {two_digit_words(paise)} Paise"
    if is_negative:
        words = f"Minus {words}"
    return f"{words} Only"
