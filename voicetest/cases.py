from voicetest.compare import compare_amount, compare_digits, compare_time

# (name, kind, expected value, sentence we ask Timbre to speak)
CASES = [
    ("phone-digits",  "digits", "9876543210", "मेरा नंबर 9876543210 है"),
    ("phone-words",   "digits", "9876543210", "मेरा नंबर नौ आठ सात छह पाँच चार तीन दो एक शून्य है"),
    ("pin-digits",    "digits", "400076",     "मेरा पिन कोड 400076 है"),
    ("pin-words",     "digits", "400076",     "मेरा पिन कोड चार शून्य शून्य शून्य सात छह है"),
    ("amount-words",  "amount", 500000,       "पाँच लाख रुपये भेजना है"),
    ("amount-symbol", "amount", 500000,       "₹5,00,000 भेजना है"),
    ("amount-hazaar", "amount", 12500,        "बारह हज़ार पाँच सौ रुपये जमा करो"),
    ("time-half",     "time",   (9, 30),      "सुबह साढ़े नौ बजे मिलते हैं"),
    ("time-evening",  "time",   (17, 15),     "शाम पाँच बजकर पंद्रह मिनट पर कॉल करना"),
    ("acct-hinglish", "digits", "12345678",   "मेरा account number 1234 5678 है"),
]


def judge(kind, expected, heard):
    if kind == "digits":
        return compare_digits(expected, heard)
    if kind == "amount":
        return compare_amount(expected, heard)
    if kind == "time":
        return compare_time(expected, heard)
    raise ValueError(f"unknown kind: {kind}")