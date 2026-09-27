import json
from pathlib import Path

from flask import Flask

from config import Config
from models import Badge, Discovery, Spot, db
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
    new_names_by_id = {item["id"]: item["name"] for item in spot_data}
    existing_spots = Spot.query.all()
    existing_names_by_id = {spot.id: spot.name for spot in existing_spots}
    # スポットの構成が変わったとき、名前が対応する発見記録を新しいIDへ引き継ぎます。
    migrated_discoveries = None
    if existing_names_by_id and existing_names_by_id != new_names_by_id:
        legacy_name_map = {
            "噴水前": "噴水前",
            "展望デッキ": "展望台",
            "西山動物園入口": "動物園",
            "レッサーパンダエリア": "レッサーパンダ",
            "道の駅西山公園": "道の駅西山",
            "庭": "嚮陽庭園",
            "ツツジ園（東側）": "庭",
            "ツツジ園（西側）": "庭",
        }
        new_ids_by_name = {name: spot_id for spot_id, name in new_names_by_id.items()}
        migrated_discoveries = {}
        for discovery in Discovery.query.all():
            if discovery.spot is None:
                target_id = discovery.spot_id if discovery.spot_id in new_names_by_id else None
            else:
                target_name = legacy_name_map.get(discovery.spot.name, discovery.spot.name)
                target_id = new_ids_by_name.get(target_name)
            if target_id is not None:
                previous_date = migrated_discoveries.get(target_id)
                if previous_date is None or discovery.created_at < previous_date:
                    migrated_discoveries[target_id] = discovery.created_at
        Discovery.query.delete()
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
            else:
                db.session.add(Spot(**item))
    if migrated_discoveries is not None:
        db.session.flush()
        db.session.add_all(Discovery(spot_id=spot_id, created_at=created_at) for spot_id, created_at in migrated_discoveries.items())
    badge_data = [
        ("🌺 ツツジ発見賞", "1スポットを発見", 1),
        ("🦊 レッサーパンダ博士", "4スポットを発見", 4),
        ("🏞 絶景ハンター", "6スポットを発見", 6),
        ("👑 西山公園マスター", "8スポットを発見", 8),
    ]
    badges = Badge.query.all()
    if {badge.name for badge in badges} != {name for name, _description, _count in badge_data}:
        Badge.query.delete()
        db.session.add_all(Badge(name=name, description=description, unlock_count=count) for name, description, count in badge_data)
    else:
        badges_by_name = {badge.name: badge for badge in badges}
        for name, description, count in badge_data:
            badge = badges_by_name[name]
            badge.name, badge.description, badge.unlock_count = name, description, count
    db.session.commit()


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
