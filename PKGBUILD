pkgname=predator-sense
pkgver=0.1.0
pkgrel=1
pkgdesc="Predator Sense hardware monitoring and controls for Acer laptops"
arch=('any')
url="https://github.com/"
license=('MIT')
depends=('python' 'gtk4' 'python-gobject')
optdepends=('nvidia-utils: NVIDIA GPU telemetry')
source=(
  "app.py"
  "predator-kbd-effects.py"
  "README.md"
  "predator-sense.png"
)
sha256sums=('SKIP' 'SKIP' 'SKIP' 'SKIP')

package() {
  install -d "$pkgdir/opt/predator-sense"

  install -Dm644 "$srcdir/app.py" \
    "$pkgdir/opt/predator-sense/app.py"
  install -Dm644 "$srcdir/predator-kbd-effects.py" \
    "$pkgdir/opt/predator-sense/predator-kbd-effects.py"
  install -Dm644 "$srcdir/README.md" \
    "$pkgdir/opt/predator-sense/README.md"

  install -Dm644 "$srcdir/predator-sense.png" \
    "$pkgdir/usr/share/icons/hicolor/512x512/apps/predator-sense.png"

  install -Dm644 "$srcdir/predator-sense.png" \
    "$pkgdir/usr/share/icons/hicolor/512x512/apps/predator-sense.png"

  install -d "$pkgdir/usr/bin"
  cat > "$pkgdir/usr/bin/predator-sense" <<'LAUNCHER'
#!/bin/sh
exec /usr/bin/python /opt/predator-sense/app.py "$@"
LAUNCHER
  chmod 755 "$pkgdir/usr/bin/predator-sense"

  install -d "$pkgdir/usr/share/applications"
  cat > "$pkgdir/usr/share/applications/predator-sense.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Predator Sense
Comment=Acer Predator hardware monitoring and controls
Icon=predator-sense
Exec=predator-sense
Terminal=false
Categories=System;Monitor;
DESKTOP
}
