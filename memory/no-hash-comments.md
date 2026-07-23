---
name: no-hash-comments
description: Kodda # ile başlayan açıklama satırı kullanılmaz. Docstring ve shebang hariç.
metadata:
  type: feedback
---

Kod yazarken `#` ile başlayan açıklama satırı kullanılmamalı. Shebang (`#!/usr/bin/env python3`) ve docstring (`"""..."""`) kabul edilebilir.

**Why:** Kullanıcı kodu temiz ve yorumsuz tercih ediyor; kod kendini açıklamalı.

**How to apply:** Dosya yazarken inline comment (`# ...`) kullanma. Bunun yerine değişken/fonksiyon isimleriyle açıkla veya docstring kullan.
