"""User service module."""

class UserService:
    """Service for managing users."""
    
    def __init__(self):
        self.users = []
    
    def create_user(self, username, email):
        """Create a new user."""
        user = {"username": username, "email": email}
        self.users.append(user)
        return user
    
    def get_user(self, username):
        """Get user by username."""
        for user in self.users:
            if user["username"] == username:
                return user
        return None
