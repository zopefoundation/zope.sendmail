try:
    text_type = unicode
    PY2 = True
except NameError:  # pragma: NO COVER Py3k
    text_type = str
    PY2 = False
