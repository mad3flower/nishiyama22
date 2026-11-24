from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    login_id = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


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
    discovery = db.relationship("Discovery", back_populates="spot", cascade="all, delete-orphan")


class Discovery(db.Model):
    # ユーザーがスポットを発見した記録です。
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    spot_id = db.Column(db.Integer, db.ForeignKey("spot.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (db.UniqueConstraint("user_id", "spot_id", name="uq_discovery_user_spot"),)

    # discovery.spot で、発見したスポット本体を取得できます。
    spot = db.relationship("Spot", back_populates="discovery")
    user = db.relationship("User")


class Badge(db.Model):
    # 発見数に応じて解放されるバッジです。
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    unlock_count = db.Column(db.Integer, nullable=False)
