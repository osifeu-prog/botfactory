from typing import Literal
from sqlalchemy.orm import Session
from models import Balance, Order, Wallet


def deposit_token(session: Session, wallet_id: int, token: str, amount: float) -> float:
    amount = float(amount)
    if amount <= 0:
        raise ValueError("amount must be positive")
    bal = session.query(Balance).filter_by(wallet_id=wallet_id, token=token).first()
    if not bal:
        bal = Balance(wallet_id=wallet_id, token=token, amount=0.0)
        session.add(bal)
    bal.amount += amount
    session.commit()
    return bal.amount


def withdraw_token(session: Session, wallet_id: int, token: str, amount: float) -> float:
    amount = float(amount)
    if amount <= 0:
        raise ValueError("amount must be positive")
    bal = session.query(Balance).filter_by(wallet_id=wallet_id, token=token).first()
    if not bal or bal.amount < amount:
        raise ValueError("insufficient balance")
    bal.amount -= amount
    session.commit()
    return bal.amount


def create_order(
    session: Session,
    wallet_id: int,
    order_type: Literal["buy", "sell"],
    token: str,
    amount: float,
    price_per_token: float,
) -> Order:
    if order_type not in ("buy", "sell"):
        raise ValueError("order_type must be 'buy' or 'sell'")
    amount = float(amount)
    price_per_token = float(price_per_token)
    if amount <= 0 or price_per_token <= 0:
        raise ValueError("amount and price_per_token must be positive")
    order = Order(
        wallet_id=wallet_id,
        type=order_type,
        token=token,
        amount=amount,
        price_per_token=price_per_token,
        status="open",
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


def fill_order(session: Session, order_id: int, taker_wallet_id: int) -> Order:
    order = session.query(Order).filter_by(id=order_id).first()
    if not order:
        raise ValueError("order not found")
    if order.status != "open":
        raise ValueError("order not open")

    total_price = order.amount * order.price_per_token
    base_token = "TON"

    maker_wallet = session.query(Wallet).filter_by(id=order.wallet_id).first()
    taker_wallet = session.query(Wallet).filter_by(id=taker_wallet_id).first()
    if not maker_wallet or not taker_wallet:
        raise ValueError("wallet(s) not found")

    if order.type == "sell":
        withdraw_token(session, taker_wallet.id, base_token, total_price)
        deposit_token(session, taker_wallet.id, order.token, order.amount)
        deposit_token(session, maker_wallet.id, base_token, total_price)
    else:
        withdraw_token(session, taker_wallet.id, order.token, order.amount)
        deposit_token(session, taker_wallet.id, base_token, total_price)
        deposit_token(session, maker_wallet.id, order.token, order.amount)

    order.status = "filled"
    session.commit()
    session.refresh(order)
    return order
