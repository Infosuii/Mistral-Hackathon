# voice/noise_test.py is a live benchmark tool that needs numpy (not in requirements.txt).
# Its name matches pytest's *_test.py pattern, so without this the whole suite fails to
# collect on any machine without numpy.
collect_ignore = ["noise_test.py"]
