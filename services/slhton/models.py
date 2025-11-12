from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, Integer, String, Float, LargeBinary, DateTime, ForeignKey, text

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)

    wallets = relationship("Wallet", back_populates="user", cascade="all, delete-orphan")


class TelegramUser(Base):
    __tablename__ = "telegram_users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(String, unique=True, nullable=False)
    username = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    user = relationship("User", backref="telegram_profile")


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    address = Column(String, nullable=False)
    encrypted_privkey = Column(LargeBinary, nullable=False)
    pubkey = Column(String, nullable=True)

    user = relationship("User", back_populates="wallets")
    balances = relationship("Balance", back_populates="wallet", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="wallet", cascade="all, delete-orphan")


class Balance(Base):
    __tablename__ = "balances"

    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False)
    token = Column(String, nullable=False)
    amount = Column(Float, nullable=False, server_default=text("0"))

    wallet = relationship("Wallet", back_populates="balances")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False)
    type = Column(String, nullable=False)  # "buy" or "sell"
    token = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    price_per_token = Column(Float, nullable=False)
    status = Column(String, nullable=False, server_default=text("'open'"))
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    wallet = relationship("Wallet", back_populates="orders")
