pkgname=ph16-linux-support
pkgver=0.1.0
pkgrel=1
pkgdesc="Hardware monitoring and controls for Acer Predator PH16-72 on Linux"
arch=('any')
url="https://github.com/ZoroXoXo/PH16-Linux-Support"
license=('GPL-3.0-or-later')
depends=('python' 'gtk4' 'python-gobject')
optdepends=('nvidia-utils: NVIDIA GPU telemetry')
source=(
  "app.py"
  "predator-kbd-effects.py"
  "README.md"
  "ph16-linux-support.png"
  "LICENSE"
)
sha256sums=('SKIP' 'SKIP' 'SKIP' 'SKIP' 'SKIP')

package() {
  install -d "$pkgdir/opt/ph16-linux-support"
  install -Dm644 "$srcdir/LICENSE" \
  "$pkgdir/opt/ph16-linux-support/LICENSE"
  install -Dm644 "$srcdir/app.py" \
    "$pkgdir/opt/ph16-linux-support/app.py"
  install -Dm644 "$srcdir/predator-kbd-effects.py" \
    "$pkgdir/opt/ph16-linux-support/predator-kbd-effects.py"
  install -Dm644 "$srcdir/README.md" \
    "$pkgdir/opt/ph16-linux-support/README.md"

  install -Dm644 "$srcdir/ph16-linux-support.png" \
    "$pkgdir/usr/share/icons/hicolor/512x512/apps/ph16-linux-support.png"

  install -d "$pkgdir/usr/bin"
  cat > "$pkgdir/usr/bin/ph16-linux-support" <<'LAUNCHER'
#!/bin/sh
exec /usr/bin/python /opt/ph16-linux-support/app.py "$@"
LAUNCHER
  chmod 755 "$pkgdir/usr/bin/ph16-linux-support"

  install -d "$pkgdir/usr/share/applications"
  cat > "$pkgdir/usr/share/applications/ph16-linux-support.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=PH16-Linux-Support
Comment=Acer Predator hardware monitoring and controls
Icon=ph16-linux-support
Exec=ph16-linux-support
Terminal=false
Categories=System;Monitor;
DESKTOP
}
