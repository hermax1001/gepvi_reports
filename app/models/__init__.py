"""Database models"""
from app.models.user import User
from app.models.webhook import Webhook
from app.models.weight_history import WeightHistory

__all__ = ["User", "Webhook", "WeightHistory"]
