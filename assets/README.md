# Heartsteel audio asset

Place the redistributable Heartsteel proc audio at:

```text
assets/heartsteel-proc.wav
```

The application intentionally does not include copyrighted game audio. During
development it reads this path directly. When a wheel is built, `setup.py`
includes the file in the installed package data when it exists.

