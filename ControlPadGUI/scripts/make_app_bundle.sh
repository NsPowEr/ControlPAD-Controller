#!/usr/bin/env bash
# Compila in release e impacchetta ControlPad.app: eseguibile + bundle
# risorse SPM + motore Python, così l'app gira senza bisogno di `swift run`
# né di trovare i sorgenti a fianco.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"          # ControlPadGUI/
PROJECT_ROOT="$(cd "$ROOT/.." && pwd)"        # ControlPAD-Controller/
APP_NAME="ControlPad"
BUILD_DIR="$ROOT/.build/release"
APP_DIR="$ROOT/dist/$APP_NAME.app"

echo "==> Compilo in release"
(cd "$ROOT" && swift build -c release)

echo "==> Preparo $APP_NAME.app"
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"

cp "$BUILD_DIR/ControlPadGUI" "$APP_DIR/Contents/MacOS/$APP_NAME"
chmod +x "$APP_DIR/Contents/MacOS/$APP_NAME"

if [ -d "$BUILD_DIR/ControlPadGUI_ControlPadGUI.bundle" ]; then
    cp -R "$BUILD_DIR/ControlPadGUI_ControlPadGUI.bundle" "$APP_DIR/Contents/Resources/"
fi

echo "==> Copio il motore Python (ControlPadEngine/)"
cp -R "$PROJECT_ROOT/ControlPadEngine" "$APP_DIR/Contents/Resources/ControlPadEngine"

cat > "$APP_DIR/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundleDisplayName</key>
    <string>$APP_NAME</string>
    <key>CFBundleIdentifier</key>
    <string>com.controlpad.gui</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleExecutable</key>
    <string>$APP_NAME</string>
    <key>CFBundleDevelopmentRegion</key>
    <string>it</string>
    <key>CFBundleLocalizations</key>
    <array>
        <string>it</string>
        <string>en</string>
    </array>
    <key>LSMinimumSystemVersion</key>
    <string>26.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.utilities</string>
</dict>
</plist>
PLIST

echo "==> Firma ad-hoc (solo uso locale, non per distribuzione)"
codesign --force --deep --sign - "$APP_DIR" 2>/dev/null || echo "    (codesign non riuscita, ignorato)"

# Il progetto sta sulla Scrivania, che su questo Mac è sincronizzata con
# iCloud: leggere le risorse da lì può bloccarsi dentro open() mentre iCloud
# decide, e l'app resta appesa senza finestra. ~/Applications non è
# sincronizzata, quindi l'app installata gira sempre da disco locale.
INSTALL_DIR="$HOME/Applications"
mkdir -p "$INSTALL_DIR"
echo "==> Installo in $INSTALL_DIR (fuori da iCloud)"
rm -rf "$INSTALL_DIR/$APP_NAME.app"
cp -R "$APP_DIR" "$INSTALL_DIR/$APP_NAME.app"

echo "==> Fatto: $INSTALL_DIR/$APP_NAME.app"
echo "Richiede: python3 con 'pip3 install hidapi' già eseguito sul Mac che la esegue."
echo "Apri con: open \"$INSTALL_DIR/$APP_NAME.app\""
