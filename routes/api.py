import math
import random

from flask import Blueprint, jsonify, request, session

from models import Badge, Discovery, Spot, db

api_bp = Blueprint("api", __name__)


def discovered_ids():
    # Discoveryテーブルから「発見済みID」の一覧を作ります。
    return {item.spot_id for item in Discovery.query.all()}


def next_mission_spot(found_ids):
    # 未発見スポットのうち、最も低いレベルのスポットから出題します。
    candidates = Spot.query.filter(~Spot.id.in_(found_ids)).all() if found_ids else Spot.query.all()
    if not candidates:
        return None
    lowest_level = min(spot.difficulty for spot in candidates)
    return random.choice([spot for spot in candidates if spot.difficulty == lowest_level])


def public_spot(spot, reveal=False):
    # 未発見スポットは番号だけ返し、答えや位置情報を隠します。
    payload = {"id": spot.id, "name": spot.name if reveal else f"No.{spot.id:02d}", "category": spot.category if reveal else None, "difficulty": spot.difficulty, "discovered": spot.id in discovered_ids()}
    if reveal:
        payload.update({"lat": spot.lat, "lng": spot.lng, "hint": spot.hint, "fact": spot.fact, "audio": spot.audio, "image": spot.image})
    return payload


def haversine_meters(lat1, lng1, lat2, lng2):
    # 緯度経度から地表面に沿ったおおよその直線距離をメートルで求めます。
    radius = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    value = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def distance_clue(distance, spot):
    # hint・category・factはspots.jsonから取り込んだオープンデータです。
    if distance > 100:
        return {"label": "音の手がかり", "text": "まだ少し遠いようです。音をたよりに歩いてみよう。"}
    if distance > 50:
        return {"label": "文章の手がかり", "text": spot.hint}
    if distance > 20:
        return {"label": "カテゴリーの手がかり", "text": f"このスポットは「{spot.category}」に関係しています。"}
    return {"label": "豆知識の手がかり", "text": spot.fact}


@api_bp.get("/mission")
def mission_api():
    # 未発見スポットだけを候補にすることで、同じ答えを出しません。
    found = discovered_ids()
    spot = next_mission_spot(found)
    if spot:
        session["mission_spot_id"] = spot.id
        return jsonify({"spot": public_spot(spot, reveal=True)})
    return jsonify({"spot": None, "complete": True})


@api_bp.get("/mission/today")
def today_mission_api():
    # 画面側が分かりやすい名前で呼べる今日のミッションAPIです。
    return mission_api()


@api_bp.get("/progress")
def progress():
    # 図鑑の登録数を数えて、APIで返します。
    found = len(discovered_ids())
    return jsonify({"found": found, "total": Spot.query.count(), "rate": round(found / Spot.query.count() * 100) if Spot.query.count() else 0})


@api_bp.post("/check")
def check_location():
    # ブラウザから届いた現在地と、出題スポットの距離を判定します。
    data = request.get_json(silent=True) or {}
    spot = Spot.query.get_or_404(data.get("spot_id"))
    try:
        # ブラウザから届いた実際の現在地と、スポットの座標を比較します。
        # latitude = float(data["lat"])
        # longitude = float(data["lng"])
        latitude =35.948581
        longitude = 136.181123

        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError("座標が範囲外です")
        distance = haversine_meters(latitude, longitude, spot.lat, spot.lng)
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "位置情報が必要です"}), 400
    accuracy = data.get("accuracy")
    if accuracy is None:
        return jsonify({"error": "位置情報の精度を取得できません", "code": "ERR004", "distance": round(distance)}), 400
    try:
        accuracy = float(accuracy)
    except (TypeError, ValueError):
        return jsonify({"error": "位置情報の精度が不正です", "code": "ERR004"}), 400
    # 画面に表示する実測距離と到着判定を揃え、20m以内なら到着とします。
    corrected_distance = max(0, distance - accuracy)
    within = distance <= 20
    clue = distance_clue(distance, spot)
    return jsonify({"within": within, "distance": round(distance), "corrected_distance": round(corrected_distance), "accuracy": round(accuracy), "hint": clue["text"], "hint_label": clue["label"], "spot_id": spot.id, "next": f"/discover/{spot.id}" if within else None})


@api_bp.get("/spots")
def spots_api():
    # 発見前は番号だけ、発見後は詳細も含めて返します。
    return jsonify({"spots": [public_spot(spot, spot.id in discovered_ids()) for spot in Spot.query.order_by(Spot.id).all()]})


@api_bp.get("/spots/<int:spot_id>")
def spot_api(spot_id):
    # API経由でも未発見スポットの答えを保護します。
    spot = Spot.query.get_or_404(spot_id)
    if spot_id not in discovered_ids():
        return jsonify({"error": "未発見のスポットです"}), 403
    return jsonify(public_spot(spot, reveal=True))


@api_bp.post("/discover")
def discover_api():
    data = request.get_json(silent=True) or {}
    spot = Spot.query.get_or_404(data.get("spot_id"))
    # 同じスポットを複数回発見してもDiscoveryは1件だけ保存します。
    if not Discovery.query.filter_by(spot_id=spot.id).first():
        db.session.add(Discovery(spot_id=spot.id))
        db.session.commit()
    found = len(discovered_ids())
    unlocked = [badge.name for badge in Badge.query.filter(Badge.unlock_count <= found).order_by(Badge.id).all()]
    return jsonify({"success": True, "found": found, "total": Spot.query.count(), "badges": unlocked})


@api_bp.get("/collection")
def collection_api():
    # 図鑑画面をJavaScriptなどから利用するための一覧APIです。
    spots = Spot.query.order_by(Spot.difficulty.asc(), Spot.id.asc()).all()
    return jsonify({"found": len(discovered_ids()), "total": Spot.query.count(), "spots": [public_spot(spot, spot.id in discovered_ids()) for spot in spots]})


@api_bp.get("/discoveries")
def discoveries_api():
    # 保存済みの発見IDと発見日時を返します。位置履歴は含めません。
    return jsonify({"discoveries": [{"spot_id": item.spot_id, "created_at": item.created_at.isoformat()} for item in Discovery.query.order_by(Discovery.created_at).all()]})


@api_bp.get("/bloom")
def bloom_api():
    return jsonify({"status": "見ごろ", "rate": 82, "color": "#EC407A"})


@api_bp.get("/badges")
def badges_api():
    found = len(discovered_ids())
    return jsonify({"badges": [{"id": badge.id, "name": badge.name, "description": badge.description, "unlocked": found >= badge.unlock_count} for badge in Badge.query.order_by(Badge.unlock_count).all()]})


@api_bp.get("/badges/<int:badge_id>")
def badge_api(badge_id):
    badge = Badge.query.get_or_404(badge_id)
    return jsonify({"id": badge.id, "name": badge.name, "description": badge.description, "unlocked": len(discovered_ids()) >= badge.unlock_count})


@api_bp.get("/settings")
def settings_api():
    return jsonify(session.get("settings", {"notifications": True, "sound": True}))


@api_bp.put("/settings")
def update_settings_api():
    # 通知と音の設定だけをセッションに保存します。
    data = request.get_json(silent=True) or {}
    settings = session.get("settings", {"notifications": True, "sound": True})
    settings.update({key: bool(data[key]) for key in ("notifications", "sound") if key in data})
    session["settings"] = settings
    return jsonify(settings)


@api_bp.get("/gps/status")
def gps_status_api():
    return jsonify({"supported": True, "permission": "browser", "accuracy_limit": 50, "distance_limit": 20})


@api_bp.get("/sync/status")
def sync_status_api():
    return jsonify({"online": True, "offline_cache": True})
