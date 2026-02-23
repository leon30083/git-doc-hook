#!/bin/bash
# Manual test script for git-doc-hook
# This script performs end-to-end testing of git-doc-hook functionality

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Create a temporary directory for testing
TEST_DIR=$(mktemp -d)
echo_info "Created test directory: $TEST_DIR"

cleanup() {
    echo_info "Cleaning up..."
    rm -rf "$TEST_DIR"
}
trap cleanup EXIT

cd "$TEST_DIR"

# Initialize test project
echo_info "=== Step 1: Initialize test project ==="
git init
git config user.email "test@example.com"
git config user.name "Test User"

# Install git-doc-hook in development mode if needed
# pip install -e /path/to/git-doc-hook

echo_info "=== Step 2: Initialize git-doc-hook ==="
git-doc-hook init

# Check that config file was created
if [ ! -f ".git-doc-hook.yml" ]; then
    echo_error "Config file not created"
    exit 1
fi
echo_info "✓ Config file created"

# Check that hooks were installed
if [ ! -f ".git/hooks/pre-push" ]; then
    echo_error "pre-push hook not installed"
    exit 1
fi
echo_info "✓ Git hooks installed"

echo_info "=== Step 3: Create services directory and files ==="
mkdir -p services
cat > services/auth.py << 'EOF'
"""Authentication service"""
class AuthService:
    def authenticate(self, username, password):
        """Authenticate user"""
        return True

    def logout(self, token):
        """Logout user"""
        return True
EOF

cat > services/user.py << 'EOF'
"""User service"""
class UserService:
    def get_user(self, user_id):
        """Get user by ID"""
        return {"id": user_id, "name": "Test User"}
EOF

echo_info "=== Step 4: Commit changes ==="
git add .
git commit -m "feat: add auth and user services"

echo_info "=== Step 5: Check status ==="
git-doc-hook status

echo_info "=== Step 6: Manually set pending state for testing ==="
# This simulates what the pre-push hook would do
python3 << PYTHON
import sys
sys.path.insert(0, '/home/luo/github/git-doc-hook/src')
from core.state import StateManager

state = StateManager('.')
state.set_pending(
    layers={'traditional'},
    reason='Services changed',
    triggered_by='manual',
    files=['services/auth.py', 'services/user.py'],
    commit_message='feat: add auth and user services',
)
print("✓ Pending state set")
PYTHON

echo_info "=== Step 7: Check status again ==="
git-doc-hook status

echo_info "=== Step 8: Create README.md for testing ==="
cat > README.md << 'EOF'
# Test Project

## Services

| Name | Path | Type |
|------|------|------|
EOF

echo_info "=== Step 9: Run documentation update ==="
git-doc-hook update traditional

echo_info "=== Step 10: Check README.md for updates ==="
echo "Content of README.md:"
cat README.md

echo_info "=== Step 11: Test config rules update ==="
git-doc-hook update config

if [ -f ".clinerules" ]; then
    echo_info "✓ .clinerules created/updated"
    echo "Content:"
    cat .clinerules
fi

echo_info "=== Step 12: Test clear command ==="
git-doc-hook clear --yes || git-doc-hook clear | echo "y"

git-doc-hook status
if grep -q "No pending" <(git-doc-hook status); then
    echo_info "✓ Pending state cleared"
fi

echo_info "=== Step 13: Test MemOS sync (will cache if offline) ==="
# Make a fix commit to test troubleshooting record
cat > services/auth.py << 'EOF'
"""Authentication service"""
class AuthService:
    def authenticate(self, username, password):
        """Authenticate user"""
        # Fixed: Added proper validation
        if username and password:
            return True
        return False
EOF

git add .
git commit -m "fix: add validation to auth service"

# Set pending for memos layer
python3 << PYTHON
import sys
sys.path.insert(0, '/home/luo/github/git-doc-hook/src')
from core.state import StateManager

state = StateManager('.')
state.set_pending(
    layers={'memo'},
    reason='Bug fix committed',
    triggered_by='manual',
    files=['services/auth.py'],
    commit_message='fix: add validation to auth service',
)
print("✓ Pending state set for memos")
PYTHON

git-doc-hook update memo

echo_info "=== Step 14: Test MemOS sync command ==="
git-doc-hook memos-sync

echo_info "=== All tests completed ==="
echo_info "Test directory: $TEST_DIR"
echo_warn "Note: Test directory will be cleaned up on exit"
