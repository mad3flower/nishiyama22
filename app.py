import json
from pathlib import Path

from flask import Flask

from config import Config
from models import Badge, Spot, db
from routes.api import api_bp
from routes.main import main_bp


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    with app.app_context():
        db.create_all()
        # 既存SQLiteを壊さず、後から追加した列だけを補います。
        migrate_schema()
        seed_database()
    return app


def migrate_schema():
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    if "spot" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("spot")}
    if "image" not in columns:
        with db.engine.begin() as connection:
            connection.execute(text("ALTER TABLE spot ADD COLUMN image VARCHAR(120)"))
    if "difficulty" not in columns:
        with db.engine.begin() as connection:
            connection.execute(text("ALTER TABLE spot ADD COLUMN difficulty INTEGER NOT NULL DEFAULT 1"))


def seed_database():
    # スポット情報はJSONを正として、初回登録と既存行の更新を行います。
    data_path = Path(__file__).resolve().parent / "spots.json"
    with data_path.open(encoding="utf-8") as file:
        spot_data = json.load(file)
    # JSONから削除されたスポットと、その発見記録をDBからも削除します。
    valid_ids = {item["id"] for item in spot_data}
    for old_spot in Spot.query.filter(~Spot.id.in_(valid_ids)).all():
        db.session.delete(old_spot)
    if Spot.query.count() == 0:
        db.session.add_all(Spot(**spot) for spot in spot_data)
    else:
        for item in spot_data:
            spot = db.session.get(Spot, item["id"])
            if spot:
                for key, value in item.items():
                    setattr(spot, key, value)
    badge_data = [
        ("🌺 ツツジ発見賞", "1スポットを発見", 1),
        ("🦊 レッサーパンダ博士", "6スポットを発見", 6),
        ("🏞 絶景ハンター", "3スポットを発見", 3),
        ("👑 西山公園マスター", "11スポットを発見", 11),
    ]
    badges = Badge.query.order_by(Badge.unlock_count).all()
    if len(badges) != len(badge_data):
        Badge.query.delete()
        db.session.add_all(Badge(name=name, description=description, unlock_count=count) for name, description, count in badge_data)
    else:
        for badge, (name, description, count) in zip(badges, badge_data):
            badge.name, badge.description, badge.unlock_count = name, description, count
    db.session.commit()


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
