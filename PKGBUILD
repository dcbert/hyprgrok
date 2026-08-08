# Maintainer: HyprGrok contributors
pkgname=hyprgrok
pkgver=0.2.0
pkgrel=1
pkgdesc="Hyprland companion panel for official Grok Build"
arch=('any')
url="https://github.com/dcbert/hyprgrok"
license=('MIT')
depends=('python' 'hyprland')
optdepends=(
  'grim: screenshot context'
  'jq: JSON tooling'
  'kitty: preferred terminal for full sessions'
  'google-chrome: glass panel app window'
  'chromium: glass panel app window'
)
source=("$pkgname-$pkgver.tar.gz::https://github.com/dcbert/hyprgrok/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('SKIP')

package() {
  cd "$srcdir/$pkgname-$pkgver" || cd "$srcdir/HyprGrok-$pkgver"

  install -d "$pkgdir/usr/share/$pkgname"
  cp -a hyprgrok ui configs assets "$pkgdir/usr/share/$pkgname/"
  install -Dm644 README.md "$pkgdir/usr/share/doc/$pkgname/README.md"
  install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"

  install -Dm755 /dev/stdin "$pkgdir/usr/bin/hyprgrok" <<'EOF'
#!/usr/bin/env bash
export PYTHONPATH="/usr/share/hyprgrok"
cd /usr/share/hyprgrok || true
exec python3 -P -m hyprgrok "$@"
EOF

  install -Dm755 uninstall.sh "$pkgdir/usr/bin/hyprgrok-uninstall"
}
