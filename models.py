from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class Spot(db.Model):
    # 西山公園で探す1つのスポットを表すテーブルです。
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    hint = db.Column(db.Text, nullable=False)
    fact = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(40), nullable=False)
    audio = db.Column(db.String(120), nullable=True)
    image = db.Column(db.String(120), nullable=True)
    difficulty = db.Column(db.Integer, nullable=False, default=1)

    # spot.discovery で、このスポットの発見記録を取得できます。
    discovery = db.relationship("Discovery", back_populates="spot", uselist=False, cascade="all, delete-orphan")


class Discovery(db.Model):
    # ユーザーがスポットを発見した記録です。
    id = db.Column(db.Integer, primary_key=True)
    spot_id = db.Column(db.Integer, db.ForeignKey("spot.id"), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # discovery.spot で、発見したスポット本体を取得できます。
    spot = db.relationship("Spot", back_populates="discovery")


class Badge(db.Model):
    # 発見数に応じて解放されるバッジです。
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    unlock_count = db.Column(db.Integer, nullable=False)
