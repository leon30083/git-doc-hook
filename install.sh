#!/bin/bash
# Git-Doc-Hook Installation Script
set -e

INSTALL_DIR="$HOME/.git-doc-hook"
REPO_URL="https://github.com/leon30083/git-doc-hook.git"

echo "🚀 Installing git-doc-hook..."

# Create install directory
if [ -d "$INSTALL_DIR" ]; then
    echo "📁 Updating existing installation..."
    cd "$INSTALL_DIR" && git pull
else
    echo "📁 Cloning repository..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

# Install Python package
echo "📦 Installing Python package..."
cd "$INSTALL_DIR"
pip3 install -e . --user

# Add to PATH if not already there
BASHRC="$HOME/.bashrc"
ZSHRC="$HOME/.zshrc"

PATH_EXPORT='export PATH="$HOME/.git-doc-hook/bin:$PATH"'

add_to_path() {
    local rc_file="$1"
    if [ -f "$rc_file" ] && ! grep -q "\.git-doc-hook/bin" "$rc_file"; then
        echo "" >> "$rc_file"
        echo "# Git-Doc-Hook" >> "$rc_file"
        echo "$PATH_EXPORT" >> "$rc_file"
        echo "✅ Added to PATH in $rc_file"
    fi
}

add_to_path "$BASHRC"
add_to_path "$ZSHRC"

echo ""
echo "✅ Installation complete!"
echo ""
echo "To use git-doc-hook in your current shell, run:"
echo "  export PATH=\"\$HOME/.git-doc-hook/bin:\$PATH\""
echo ""
echo "Then initialize in any project:"
echo "  cd your-project"
echo "  git-doc-hook init"
