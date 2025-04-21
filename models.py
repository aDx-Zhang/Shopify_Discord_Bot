from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from flask_sqlalchemy import SQLAlchemy
from flask import Flask
import os

# Create a database instance
db = SQLAlchemy()

# Define models
class User(db.Model):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    discord_id = Column(String(32), unique=True, nullable=False)
    email = Column(String(120), nullable=True)
    profiles = relationship('Profile', back_populates='user', cascade='all, delete-orphan')
    tasks = relationship('Task', back_populates='user', cascade='all, delete-orphan')
    monitors = relationship('Monitor', back_populates='user', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'discord_id': self.discord_id,
            'email': self.email
        }


class Profile(db.Model):
    __tablename__ = 'profiles'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    user = relationship('User', back_populates='profiles')
    
    name = Column(String(100), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(120), nullable=False)
    address1 = Column(String(200), nullable=False)
    address2 = Column(String(200), nullable=True)
    city = Column(String(100), nullable=False)
    zip = Column(String(20), nullable=False)
    phone = Column(String(20), nullable=False)
    card_number = Column(String(256), nullable=False)  # Encrypted
    card_month = Column(String(256), nullable=False)   # Encrypted
    card_year = Column(String(256), nullable=False)    # Encrypted
    card_cvv = Column(String(256), nullable=False)     # Encrypted
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.email,
            'address1': self.address1,
            'address2': self.address2,
            'city': self.city,
            'zip': self.zip,
            'phone': self.phone,
            # Masked card info for safety
            'card_number': '****' + self.card_number[-4:] if self.card_number else None
        }


class Task(db.Model):
    __tablename__ = 'tasks'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    user = relationship('User', back_populates='tasks')
    profile_id = Column(Integer, ForeignKey('profiles.id'), nullable=False)
    
    product_url = Column(String(500), nullable=False)
    quantity = Column(Integer, default=1)
    auto_checkout = Column(Boolean, default=False)
    active = Column(Boolean, default=True)
    task_id = Column(String(36), unique=True, nullable=False)  # UUID


class Monitor(db.Model):
    __tablename__ = 'monitors'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    user = relationship('User', back_populates='monitors')
    
    product_url = Column(String(500), nullable=False)
    notify = Column(Boolean, default=True)
    active = Column(Boolean, default=True)
    monitor_id = Column(String(36), unique=True, nullable=False)  # UUID
    

class Setting(db.Model):
    __tablename__ = 'settings'
    
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    
    @classmethod
    def get(cls, key, default=None):
        """Get setting value by key"""
        setting = cls.query.filter_by(key=key).first()
        if setting:
            return setting.value
        return default
    
    @classmethod
    def set(cls, key, value):
        """Set or update setting value"""
        setting = cls.query.filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = cls(key=key, value=value)
            db.session.add(setting)
        db.session.commit()