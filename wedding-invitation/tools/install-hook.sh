#!/bin/sh
# 커밋할 때마다 ?v= 를 자동으로 찍도록 pre-commit 훅을 깝니다.
# 훅은 .git/hooks 안에 있어 저장소에 함께 따라가지 않으므로,
# 새 컴퓨터에서 받아 왔다면 한 번 실행해 주세요.
#
#   sh wedding-invitation/tools/install-hook.sh

set -e
ROOT=$(git rev-parse --show-toplevel)
HOOK="$ROOT/.git/hooks/pre-commit"

cat > "$HOOK" <<'EOF'
#!/bin/sh
# style·script 를 고쳤으면 html 의 ?v= 를 새 값으로 바꾸고, 그 변경도 함께 커밋합니다.
ROOT=$(git rev-parse --show-toplevel)
python3 "$ROOT/wedding-invitation/tools/stamp-assets.py" || exit 1
git add "$ROOT/wedding-invitation/index.html" "$ROOT/wedding-invitation/index.old.html" 2>/dev/null || true
EOF

chmod +x "$HOOK"
echo "깔았습니다: $HOOK"
echo "이제 커밋할 때마다 ?v= 가 자동으로 맞춰집니다."
