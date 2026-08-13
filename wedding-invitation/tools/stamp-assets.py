#!/usr/bin/env python3
"""style·script 의 ?v= 를 파일 내용에서 뽑은 값으로 찍습니다.

브라우저는 주소가 같으면 받아 둔 파일을 계속 씁니다. 그래서 style.css 를 고쳐도
?v= 가 그대로면 방문자는 옛 스타일을 보게 됩니다(실제로 겪었습니다).

내용이 바뀐 파일만 값이 바뀌므로, 손대지 않은 파일에는 쓸데없는 변경이 생기지 않습니다.
커밋할 때 자동으로 돌리려면:  tools/install-hook.sh
그냥 한 번 돌리려면:        python3 tools/stamp-assets.py
"""

import hashlib
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent.parent   # wedding-invitation/

# 어느 html 이 어떤 파일을 참조하는지
PAGES = ["index.html", "index.old.html"]
ASSETS = ["style.css", "style.old.css", "script.js"]


def digest(path: pathlib.Path) -> str:
    """내용이 같으면 같은 값이 나오도록 짧은 해시를 만듭니다."""
    return hashlib.sha1(path.read_bytes()).hexdigest()[:8]


def main() -> int:
    stamps = {}
    for name in ASSETS:
        f = HERE / name
        if f.is_file():
            stamps[name] = digest(f)

    changed = []
    for page in PAGES:
        f = HERE / page
        if not f.is_file():
            continue
        before = f.read_text(encoding="utf-8")
        after = before

        for name, stamp in stamps.items():
            # href="style.css?v=…"  ·  src="script.js?v=…"  (없으면 붙이지 않습니다)
            after = re.sub(
                rf'((?:href|src)="{re.escape(name)})(\?v=[^"]*)?"',
                rf'\1?v={stamp}"',
                after,
            )

        if after != before:
            f.write_text(after, encoding="utf-8")
            changed.append(page)

    if changed:
        print("[stamp] 갱신:", ", ".join(changed))
        for name, stamp in stamps.items():
            print(f"         {name} → ?v={stamp}")
    else:
        print("[stamp] 바뀐 것 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
