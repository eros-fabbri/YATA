from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, UniqueConstraint, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from smarttrading.domain import Bar


class Base(DeclarativeBase):
    pass


class BarRow(Base):
    __tablename__ = "bars"
    __table_args__ = (UniqueConstraint("asset", "timeframe", "timestamp"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    asset: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str] = mapped_column(String(8), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    high: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    low: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    close: Mapped[Decimal] = mapped_column(Numeric(28, 12))
    volume: Mapped[Decimal] = mapped_column(Numeric(28, 12))


class BarRepository:
    def __init__(self, url: str) -> None:
        self._engine = create_engine(url)

    def create_schema(self) -> None:
        Base.metadata.create_all(self._engine)

    def add(self, bars: Sequence[Bar]) -> None:
        with Session(self._engine) as session, session.begin():
            session.add_all(BarRow(**bar.model_dump()) for bar in bars)

    def get(self, asset: str, timeframe: str, start: datetime, end: datetime) -> list[Bar]:
        statement = (
            select(BarRow)
            .where(
                BarRow.asset == asset,
                BarRow.timeframe == timeframe,
                BarRow.timestamp >= start,
                BarRow.timestamp <= end,
            )
            .order_by(BarRow.timestamp)
        )
        with Session(self._engine) as session:
            rows = session.scalars(statement).all()
            return [
                Bar(
                    timestamp=(
                        row.timestamp.replace(tzinfo=UTC)
                        if row.timestamp.tzinfo is None
                        else row.timestamp
                    ),
                    asset=row.asset,
                    timeframe=row.timeframe,
                    open=row.open,
                    high=row.high,
                    low=row.low,
                    close=row.close,
                    volume=row.volume,
                )
                for row in rows
            ]
